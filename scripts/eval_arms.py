"""Architecture A/B/C — scores pipeline variants against the historical JSON answer key.

Answers three design questions with one run:
  1. Is the deterministic parse-first path still needed?   (split-pf vs split-nopf)
  2. Is the split-call architecture needed at all?         (split-nopf vs mono)
  3. What does each cost?                                  (tokens/$ recorded per arm)

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

    # the decisive run: is splitting necessary?
    .venv/bin/python -u scripts/eval_arms.py --n 6 --arms split-nopf mono --max-cost 2.00

    # add the current production baseline
    .venv/bin/python -u scripts/eval_arms.py --n 6 --arms split-pf split-nopf mono
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

# arm -> (entrypoint, kwargs). "mono" is the single-call path; it has no parse-first concept.
ARMS = {
    "split-pf": (extraction.assemble, {"use_parse_first": True}),
    "split-nopf": (extraction.assemble, {"use_parse_first": False}),
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


def score(truth: list[dict], got: list[dict]) -> tuple[int, int, list[str]]:
    ok = total = 0
    diffs: list[str] = []

    total += 1
    if len(truth) == len(got):
        ok += 1
    else:
        diffs.append(f"exercise count: truth={len(truth)} got={len(got)}")

    for i, t in enumerate(truth):
        g = got[i] if i < len(got) else {"name": "<MISSING>", "sets": [], "n_warmup": 0}
        label = f"ex{i+1} {t['name'][:24]!r}"

        for field, tv, gv in (
            ("set count", len(t["sets"]), len(g["sets"])),
            ("warmup count", t["n_warmup"], g["n_warmup"]),
        ):
            total += 1
            if tv == gv:
                ok += 1
            else:
                diffs.append(f"{label}: {field} truth={tv} got={gv}")

        for j, ts in enumerate(t["sets"]):
            gs = g["sets"][j] if j < len(g["sets"]) else {}
            for key in ("kg", "full", "partial", "rpe"):
                total += 1
                if _eq(ts.get(key), gs.get(key)):
                    ok += 1
                else:
                    diffs.append(f"{label} set{j+1} {key}: truth={ts.get(key)} got={gs.get(key)}")
    return ok, total, diffs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="+", default=["split-nopf", "mono"], choices=list(ARMS))
    ap.add_argument("--model", default="haiku", choices=list(MODELS))
    ap.add_argument("--n", type=int, default=6, help="How many input files to sample")
    ap.add_argument("--seed", type=int, default=7, help="Sampling seed — keep it fixed across runs")
    ap.add_argument("--files", nargs="*", help="Explicit files instead of sampling")
    ap.add_argument("--max-cost", type=float, default=2.00)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show-diffs", type=int, default=8, help="Max mismatch lines per file")
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
        agg = {"ok": 0, "total": 0, "files_perfect": 0, "files_run": 0, "errors": 0}
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

            ok, total, diffs = score(truth, spine_from_extract(extract))
            agg["ok"] += ok
            agg["total"] += total
            agg["files_run"] += 1
            if not diffs:
                agg["files_perfect"] += 1
            pct = 100.0 * ok / total if total else 0.0
            print(f"      {ok}/{total} fields ({pct:.1f}%)  {time.time()-t0:.1f}s"
                  f"{'  PERFECT' if not diffs else ''}")
            for d in diffs[: args.show_diffs]:
                print(f"         x {d}")
            if len(diffs) > args.show_diffs:
                print(f"         ... {len(diffs)-args.show_diffs} more")

            (run_dir / f"{path.stem}__{arm}.json").write_text(
                json.dumps(extract.model_dump(mode="json"), indent=2)
            )

    if args.dry_run:
        print("\nDry run complete — no API calls, $0.00 spent.")
        return 0

    print()
    print("=" * 78)
    print("VERDICT")
    print("=" * 78)
    print(f"{'arm':<12} {'accuracy':>14} {'perfect files':>14} {'calls':>7} {'cost':>9} {'fails':>6}")
    for arm, d in table.items():
        a, u = d["agg"], d["usage"]
        pct = 100.0 * a["ok"] / a["total"] if a["total"] else 0.0
        print(f"{arm:<12} {a['ok']:>5}/{a['total']:<5}{pct:>5.1f}% "
              f"{a['files_perfect']:>7}/{a['files_run']:<6} {u.calls:>7} "
              f"${u.cost(model):>8.4f} {a['errors']:>6}")
    print(f"\nArtifacts: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
