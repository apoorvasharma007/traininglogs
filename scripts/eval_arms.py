"""Architecture A/B/C — scores pipeline variants against the historical JSON answer key.

Answers three design questions with one run:
  1. Is the split-call architecture needed at all?  (split vs mono)
  2. What does each cost?                           (tokens/$ recorded per arm)

GROUND TRUTH is output_training_logs_json/*.json, matched to each input .md by the
session_id hash (processor.compute_session_id). Those files predate the v3 model, so only
the numeric spine is scored — set counts, weight_kg, rep_count.full/partial, rpe, warmup
counts. Classification fields (tags/modality/movement_pattern) did not exist then and are
deliberately NOT scored.

Reuses eval_ab.py's on-disk response cache, so nothing is ever paid for twice — across runs,
across arms, and after a crash.

Usage:
    # plan + cost estimate, no API calls
    .venv/bin/python -u scripts/eval_arms.py --n 6 --dry-run

    # is splitting necessary?
    .venv/bin/python -u scripts/eval_arms.py --n 6 --arms split mono --max-cost 2.00

    # re-score one arm after a prompt change (cached calls are free)
    .venv/bin/python -u scripts/eval_arms.py --n 6 --arms split
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(str(PROJECT_ROOT / ".env"))

from eval_ab import (  # noqa: E402
    CACHE_DIR,
    EVAL_ROOT,
    MODELS,
    CachedProvider,
    InstrumentedAnthropic,
    InstrumentedGroq,
    _DryRunStop,
    _Usage,
)
from traininglogs.agent import extraction  # noqa: E402
from traininglogs.agent.schemas import LLMParserError  # noqa: E402

INPUTS_DIR = PROJECT_ROOT / "inputs"
TRUTH_GLOB = str(PROJECT_ROOT / "output_training_logs_json" / "**" / "*.json")

# arm -> (entrypoint, kwargs). The `split-pf` arm (parse-first ON) was removed with
# parse_exercise_block itself on 2026-08-03 — it fired on 0 of 10 real exercises, so it was
# never distinguishable from `split` on production input anyway.
ARMS = {
    "split": (extraction.assemble, {}),
    "mono": (extraction.parse, {}),
}


def build_truth_index() -> dict[Path, Path]:
    """input .md -> newest ground-truth JSON, matched by the session_id path hash."""
    by_hash: dict[str, Path] = {}
    for p in sorted(INPUTS_DIR.rglob("*.md")):
        h = hashlib.sha256(str(p.relative_to(INPUTS_DIR)).encode()).hexdigest()[:6]
        by_hash[h] = p

    best: dict[Path, tuple[float, Path]] = {}
    for jf in glob.glob(TRUTH_GLOB, recursive=True):
        jp = Path(jf)
        try:
            sid = json.load(jp.open()).get("session_id") or ""
        except (json.JSONDecodeError, OSError):
            continue
        md = by_hash.get(sid.split("-")[-1])
        if md is None:
            continue
        mtime = jp.stat().st_mtime
        # Several JSON generations exist per input (schema migrations). Newest wins.
        if md not in best or mtime > best[md][0]:
            best[md] = (mtime, jp)
    return {md: jp for md, (_, jp) in best.items()}


def spine_from_truth(doc: dict) -> list[dict]:
    out = []
    for ex in doc.get("exercises") or []:
        sets = []
        for s in ex.get("sets") or []:
            rc = s.get("rep_count") or {}
            sets.append(
                {
                    "kg": s.get("weight_kg"),
                    "full": rc.get("full"),
                    "partial": rc.get("partial") or 0,
                    "rpe": s.get("rpe"),
                }
            )
        out.append({"name": (ex.get("name") or "").strip(), "sets": sets,
                    "n_warmup": len(ex.get("warmup_sets") or [])})
    return out


def spine_from_extract(extract) -> list[dict]:
    out = []
    for ex in extract.exercises:
        sets = []
        for s in ex.sets or []:
            rc = getattr(s, "rep_count", None)
            sets.append(
                {
                    "kg": s.weight_kg,
                    "full": rc.full if rc else None,
                    "partial": (rc.partial if rc else 0) or 0,
                    "rpe": s.rpe,
                }
            )
        out.append({"name": (ex.name or "").strip(), "sets": sets,
                    "n_warmup": len(ex.warmup_sets or [])})
    return out


def _eq(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) < 0.01
    except (TypeError, ValueError):
        return a == b


def score(truth: list[dict], got: list[dict]) -> tuple[dict[str, list[int]], list[str]]:
    """Score in two categories, because they are not equally trustworthy.

    CORE -- exercise count, set counts, weights, reps, RPE. The answer key is reliable here, so
    a drop is a real regression.

    WARMUP -- warmup set counts only. The answer key came from the rules parser, which ignored
    the `### Warmup Notes` prose where warmups are actually written ("36 x feel", "200 kgs power
    kicks"). Five of seven mismatches in the 2026-08-03 run were the model being *more* correct
    than the key. So a rise in warmup mismatches may mean the extraction improved. Adjudicate
    these by reading the source, never by the number alone.
    """
    tally = {"core": [0, 0], "warmup": [0, 0]}   # category -> [correct, total]
    diffs: list[str] = []

    def record(category: str, correct: bool, message: str) -> None:
        tally[category][1] += 1
        if correct:
            tally[category][0] += 1
        else:
            diffs.append(f"[{category}] {message}")

    record("core", len(truth) == len(got),
           f"exercise count: truth={len(truth)} got={len(got)}")

    for i, t in enumerate(truth):
        g = got[i] if i < len(got) else {"name": "<MISSING>", "sets": [], "n_warmup": 0}
        label = f"ex{i+1} {t['name'][:24]!r}"

        record("core", len(t["sets"]) == len(g["sets"]),
               f"{label}: set count truth={len(t['sets'])} got={len(g['sets'])}")
        record("warmup", t["n_warmup"] == g["n_warmup"],
               f"{label}: warmup count truth={t['n_warmup']} got={g['n_warmup']}")

        for j, ts in enumerate(t["sets"]):
            gs = g["sets"][j] if j < len(g["sets"]) else {}
            for key in ("kg", "full", "partial", "rpe"):
                record("core", _eq(ts.get(key), gs.get(key)),
                       f"{label} set{j+1} {key}: truth={ts.get(key)} got={gs.get(key)}")
    return tally, diffs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="+", default=["split", "mono"], choices=list(ARMS))
    ap.add_argument("--model", default="haiku", choices=list(MODELS))
    ap.add_argument("--n", type=int, default=6, help="How many input files to sample")
    ap.add_argument("--seed", type=int, default=7, help="Sampling seed — keep it fixed across runs")
    ap.add_argument("--files", nargs="*", help="Explicit files instead of sampling")
    ap.add_argument("--max-cost", type=float, default=2.00)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show-diffs", type=int, default=8, help="Max mismatch lines per file")
    ap.add_argument(
        "--delay", type=float, default=0.0,
        help=(
            "Seconds to pause before each uncached call. Free tiers meter tokens per minute; "
            "pacing avoids saturating the window. Try 20 for Groq. Cached calls never wait."
        ),
    )
    args = ap.parse_args()

    truth_index = build_truth_index()
    if args.files:
        chosen = [Path(f).resolve() for f in args.files]
    else:
        pool = sorted(truth_index)
        random.Random(args.seed).shuffle(pool)
        chosen = pool[: args.n]

    model, kind = MODELS[args.model]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = EVAL_ROOT / f"arms-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "calls.jsonl"

    print("=" * 78)
    print(f"ARM COMPARISON {run_id}{'  [DRY RUN]' if args.dry_run else ''}")
    print("=" * 78)
    print(f"model     : {args.model} ({model})")
    print(f"arms      : {', '.join(args.arms)}")
    print(f"files     : {len(chosen)} (of {len(truth_index)} with ground truth)")
    print(f"cost cap  : ${args.max_cost:.2f}")
    print(f"cache     : {len(list(CACHE_DIR.glob('*.json'))) if CACHE_DIR.exists() else 0} entries")
    for p in chosen:
        print(f"   - {p.relative_to(PROJECT_ROOT)}  ({p.stat().st_size:,} chars)")
    print()

    table: dict[str, dict] = {}

    for arm in args.arms:
        fn, kwargs = ARMS[arm]
        usage = _Usage()
        agg = {"core": [0, 0], "warmup": [0, 0],
               "files_perfect": 0, "files_run": 0, "errors": 0}
        table[arm] = {"usage": usage, "agg": agg}
        print("-" * 78)
        print(f"ARM: {arm}")
        print("-" * 78)

        for path in chosen:
            truth_doc = json.load(truth_index[path].open())
            truth = spine_from_truth(truth_doc)
            md_text = path.read_text(encoding="utf-8")
            print(f"\n  {path.name}  (truth: {len(truth)} ex, "
                  f"{sum(len(t['sets']) for t in truth)} sets)")

            inner = (InstrumentedAnthropic(model, usage) if kind == "anthropic"
                     else InstrumentedGroq(model, usage))
            provider = CachedProvider(inner, model, usage, log_path, args.dry_run,
                                      args.max_cost, stage_label=f"{arm}:{path.name}")
            t0 = time.time()
            try:
                extract = fn(md_text, provider=provider, **kwargs)
            except _DryRunStop as exc:
                print(f"      NOT CACHED — {exc}")
                continue
            except (LLMParserError, Exception) as exc:  # noqa: BLE001
                agg["errors"] += 1
                print(f"      FAILED ({type(exc).__name__}): {str(exc)[:120]}")
                continue

            if args.dry_run:
                print("      FULLY CACHED — $0.00")
                continue

            tally, diffs = score(truth, spine_from_extract(extract))
            for category, (ok_n, total_n) in tally.items():
                agg[category][0] += ok_n
                agg[category][1] += total_n
            agg["files_run"] += 1
            if not diffs:
                agg["files_perfect"] += 1
            core_ok, core_total = tally["core"]
            warm_ok, warm_total = tally["warmup"]
            core_pct = 100.0 * core_ok / core_total if core_total else 0.0
            print(f"      core {core_ok}/{core_total} ({core_pct:.1f}%) | "
                  f"warmup {warm_ok}/{warm_total}  {time.time()-t0:.1f}s"
                  f"{'  PERFECT' if not diffs else ''}")
            for d in diffs[: args.show_diffs]:
                print(f"         x {d}")
            if len(diffs) > args.show_diffs:
                print(f"         ... {len(diffs)-args.show_diffs} more")

            (run_dir / f"{path.stem}__{arm}.json").write_text(
                json.dumps(extract.model_dump(mode="json"), indent=2)
            )
            # What the model actually said, before assembly and projection. The assembled file
            # above has source_line and reps-as-written stripped out by to_exercise(), so this
            # is the only place the raw answer survives in readable form.
            (run_dir / f"{path.stem}__{arm}__raw.json").write_text(
                json.dumps(provider.responses, indent=2)
            )

    if args.dry_run:
        print("\nDry run complete — no API calls, $0.00 spent.")
        return 0

    print()
    print("=" * 78)
    print("VERDICT")
    print("=" * 78)
    print(f"{'arm':<12} {'CORE (trust this)':>20} {'warmup (adjudicate)':>21} "
          f"{'perfect':>9} {'calls':>7} {'re-ask':>7} {'dropped':>8} {'cost':>9} {'fails':>6}")
    for arm, d in table.items():
        a, u = d["agg"], d["usage"]
        c_ok, c_tot = a["core"]
        w_ok, w_tot = a["warmup"]
        c_pct = 100.0 * c_ok / c_tot if c_tot else 0.0
        w_pct = 100.0 * w_ok / w_tot if w_tot else 0.0
        print(f"{arm:<12} {c_ok:>6}/{c_tot:<5}{c_pct:>6.1f}% "
              f"{w_ok:>7}/{w_tot:<5}{w_pct:>6.1f}% "
              f"{a['files_perfect']:>4}/{a['files_run']:<4} {u.calls:>7} "
              f"{u.retried_calls:>7} {u.failed_calls:>8} ${u.cost(model):>8.4f} "
              f"{a['errors']:>6}")
    print()
    print("CORE is exercise/set counts, weights, reps, RPE -- the answer key is reliable, so a")
    print("drop there is a real regression. WARMUP counts are scored against a key built by the")
    print("rules parser, which ignored the `### Warmup Notes` prose where warmups are actually")
    print("written -- so more mismatches there may mean the extraction got better. Read the")
    print("source before believing that number.")
    print(f"\nArtifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
