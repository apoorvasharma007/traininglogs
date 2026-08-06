"""Model A/B for the AI extraction pipeline — Haiku 4.5 vs Groq.

Answers one question: how well does each model extract a session on its own? The model owns
the numeric spine, so model capability is what's actually being measured.

MONEY SAFETY — the reason this script exists instead of a one-liner:
  * Every provider response is cached on disk, keyed by a hash of the exact request
    (model + system prompt + tool schema + input text). A re-run, a crash halfway, or an
    added file costs nothing for work already done. Cache lives in eval_runs/.cache/ and
    persists across runs. Delete it to force fresh calls.
  * --max-cost aborts before the next call once accumulated spend crosses the cap.
  * --dry-run shows exactly what would be called, and what is already cached, spending $0.
  * Every call is appended to calls.jsonl as it happens, so an interrupted run still leaves
    a complete record of what was paid for.

Usage:
    # See the plan and what's already cached — makes no API calls
    .venv/bin/python scripts/eval_ab.py --dry-run

    # Real run, both models, default file set, hard cap at $1.00
    .venv/bin/python scripts/eval_ab.py --max-cost 1.00 2>&1 | tee eval_out.txt

    # One model only
    .venv/bin/python scripts/eval_ab.py --models haiku
    .venv/bin/python scripts/eval_ab.py --models groq --files tests/fixtures/valid/x.md

Requires ANTHROPIC_API_KEY (haiku) and/or GROQ_API_KEY (groq) in .env.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(str(PROJECT_ROOT / ".env"))

from traininglogs.agent import extraction  # noqa: E402
from traininglogs.agent.providers import AnthropicProvider, GroqProvider  # noqa: E402
from traininglogs.agent.schemas import LLMParserError  # noqa: E402

EVAL_ROOT = PROJECT_ROOT / "eval_runs"
CACHE_DIR = EVAL_ROOT / ".cache"

# The eval set. Two classes of input on purpose:
#   - programmed_*  : strictly formatted, the easy case
#   - adhoc_*       : irregular notation, where the model has always done the whole job
DEFAULT_FILES = [
    "tests/fixtures/valid/programmed_push_pull_session_with_remarks.md",
    "tests/fixtures/valid/adhoc_calisthenics_rings_session.md",
    "tests/fixtures/valid/adhoc_movement_skills_session.md",
    "tests/fixtures/valid/adhoc_remarks_and_session_notes.md",
]

# USD per million tokens (input, output). Groq free tier is $0 but tokens are still recorded.
PRICING = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "openai/gpt-oss-120b": (0.00, 0.00),
}

MODELS = {
    "haiku": ("claude-haiku-4-5-20251001", "anthropic"),
    "groq": ("openai/gpt-oss-120b", "groq"),
}


class _Usage:
    def __init__(self) -> None:
        self.calls = 0
        self.cached_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def cost(self, model: str) -> float:
        pin, pout = PRICING.get(model, (0.0, 0.0))
        return self.input_tokens / 1e6 * pin + self.output_tokens / 1e6 * pout


class InstrumentedAnthropic(AnthropicProvider):
    def __init__(self, model: str, usage: _Usage) -> None:
        super().__init__(model=model)
        self.usage = usage
        _create = self._client.messages.create

        def wrapped(**kwargs):
            resp = _create(**kwargs)
            self.usage.calls += 1
            self.usage.input_tokens += resp.usage.input_tokens
            self.usage.output_tokens += resp.usage.output_tokens
            return resp

        self._client.messages.create = wrapped  # type: ignore[method-assign]


class InstrumentedGroq(GroqProvider):
    def __init__(self, model: str, usage: _Usage) -> None:
        super().__init__(model=model)
        self.usage = usage
        _create = self._client.chat.completions.create

        def wrapped(**kwargs):
            resp = _create(**kwargs)
            self.usage.calls += 1
            u = getattr(resp, "usage", None)
            if u is not None:
                self.usage.input_tokens += getattr(u, "prompt_tokens", 0) or 0
                self.usage.output_tokens += getattr(u, "completion_tokens", 0) or 0
            return resp

        self._client.chat.completions.create = wrapped  # type: ignore[method-assign]


class _DryRunStop(Exception):
    """Raised on the first uncached call in a dry run. The pipeline can't continue past a call
    it didn't actually make, so we stop that file and report where it would have spent."""


class CachedProvider:
    """Wraps any ExtractionProvider with an on-disk response cache.

    The cache key is the full request: model + system prompt + tool name/description/schema +
    input text. Any change to a prompt or schema produces a different key, so a stale prompt
    can never silently serve a cached answer.
    """

    def __init__(self, inner, model: str, usage: _Usage, log_path: Path, dry_run: bool,
                 max_cost: float, stage_label: str = "") -> None:
        self.inner = inner
        self.model = model
        self.usage = usage
        self.log_path = log_path
        self.dry_run = dry_run
        self.max_cost = max_cost
        self.stage_label = stage_label
        self.planned = 0
        # Everything the model returned, in call order -- so a run can be read afterwards
        # rather than reconstructed from hashed cache files.
        self.responses: list[dict] = []
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _key(self, text, tool_schema, system_prompt, tool_name, tool_description) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "system": system_prompt,
                "tool_name": tool_name,
                "tool_description": tool_description,
                "schema": tool_schema,
                "text": text,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _log(self, record: dict) -> None:
        with self.log_path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")

    def extract(self, text, tool_schema, system_prompt, tool_name, tool_description) -> dict:
        key = self._key(text, tool_schema, system_prompt, tool_name, tool_description)
        cache_file = CACHE_DIR / f"{key}.json"

        if cache_file.exists():
            self.usage.cached_calls += 1
            print(f"      [cache hit ] {tool_name}")
            cached = json.loads(cache_file.read_text())
            self.responses.append({"tool": tool_name, "cached": True, "response": cached})
            return cached

        if self.dry_run:
            self.planned += 1
            raise _DryRunStop(f"first uncached call would be '{tool_name}' (~{len(text):,} chars in)")

        # A free model never trips the cap -- otherwise `--max-cost 0` on Groq aborts before the
        # first call, since 0 >= 0. On a paid model `--max-cost 0` still correctly refuses to
        # spend anything at all.
        price_in, price_out = PRICING.get(self.model, (0.0, 0.0))
        if (price_in or price_out):
            spent = self.usage.cost(self.model)
            if spent >= self.max_cost:
                raise LLMParserError(
                    f"COST CAP: ${spent:.4f} spent, cap is ${self.max_cost:.2f}. Aborting "
                    f"before the next call. Raise --max-cost to continue; cached work is "
                    f"preserved."
                )

        before_in, before_out = self.usage.input_tokens, self.usage.output_tokens
        t0 = time.time()
        result = self.inner.extract(text, tool_schema, system_prompt, tool_name, tool_description)
        elapsed = time.time() - t0

        d_in = self.usage.input_tokens - before_in
        d_out = self.usage.output_tokens - before_out
        pin, pout = PRICING.get(self.model, (0.0, 0.0))
        call_cost = d_in / 1e6 * pin + d_out / 1e6 * pout

        print(
            f"      [called    ] {tool_name}  {d_in:,} in + {d_out:,} out tok  "
            f"${call_cost:.5f}  {elapsed:.1f}s"
        )
        self._log(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "stage": self.stage_label,
                "model": self.model,
                "tool": tool_name,
                "input_tokens": d_in,
                "output_tokens": d_out,
                "cost_usd": round(call_cost, 6),
                "seconds": round(elapsed, 2),
                "cache_key": key,
            }
        )
        cache_file.write_text(json.dumps(result, indent=2))
        self.responses.append({"tool": tool_name, "cached": False, "response": result})
        return result


def build_provider(kind: str, model: str, usage: _Usage) -> object:
    if kind == "anthropic":
        return InstrumentedAnthropic(model, usage)
    return InstrumentedGroq(model, usage)


def _reps(s) -> str:
    """Human-readable rep count. Reps live in a nested RepCount (full/partial), or in
    unilateral_rep_count for left/right work, or nowhere at all for timed/distance sets."""
    rc = getattr(s, "rep_count", None)
    if rc is not None:
        return f"{rc.full}+{rc.partial}" if rc.partial else str(rc.full)
    u = getattr(s, "unilateral_rep_count", None)
    if u is not None:
        return f"L/R {u!r}"
    if getattr(s, "duration_seconds", None) is not None:
        return f"{s.duration_seconds}s"
    if getattr(s, "distance_meters", None) is not None:
        return f"{s.distance_meters}m"
    return "-"


def summarize(extract) -> dict:
    """Compact shape summary for the side-by-side table."""
    return {
        "date": extract.date,
        "n_exercises": len(extract.exercises),
        "n_working_sets": sum(len(e.sets or []) for e in extract.exercises),
        "n_warmup_sets": sum(len(e.warmup_sets or []) for e in extract.exercises),
        "n_warnings": len(extract.warnings or []),
        "n_uncertain": len(extract.uncertain_fields or []),
        "exercises": [
            {
                "name": e.name,
                "sets": [
                    {"n": s.number, "kg": s.weight_kg, "reps": _reps(s), "rpe": s.rpe}
                    for s in (e.sets or [])
                ],
                "n_warmup": len(e.warmup_sets or []),
            }
            for e in extract.exercises
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--files", nargs="*", default=DEFAULT_FILES, help="Input .md files")
    ap.add_argument("--models", nargs="*", default=["haiku", "groq"], choices=list(MODELS))
    ap.add_argument("--max-cost", type=float, default=1.00, help="Abort once spend crosses this (USD)")
    ap.add_argument("--dry-run", action="store_true", help="Show the plan, make no API calls")
    args = ap.parse_args()

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = EVAL_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "calls.jsonl"

    print("=" * 78)
    print(f"EVAL RUN {run_id}{'  [DRY RUN — no API calls]' if args.dry_run else ''}")
    print("=" * 78)
    print(f"models      : {', '.join(args.models)}")
    print(f"files       : {len(args.files)}")
    print(f"cost cap    : ${args.max_cost:.2f}")
    print(f"output dir  : {run_dir}")
    print(f"cache dir   : {CACHE_DIR}  ({len(list(CACHE_DIR.glob('*.json'))) if CACHE_DIR.exists() else 0} entries)")
    print()

    results: dict[str, dict[str, dict]] = {}
    usages: dict[str, _Usage] = {}

    for model_key in args.models:
        model, kind = MODELS[model_key]
        usage = _Usage()
        usages[model_key] = usage
        results[model_key] = {}
        print("-" * 78)
        print(f"MODEL: {model_key}  ({model})")
        print("-" * 78)

        for rel in args.files:
            path = (PROJECT_ROOT / rel).resolve() if not Path(rel).is_absolute() else Path(rel)
            if not path.is_file():
                print(f"  ! missing file, skipping: {rel}")
                continue
            md_text = path.read_text(encoding="utf-8")
            print(f"\n  {path.name}  ({len(md_text):,} chars)")

            inner = build_provider(kind, model, usage)
            provider = CachedProvider(
                inner, model, usage, log_path, args.dry_run, args.max_cost,
                stage_label=f"{model_key}:{path.name}",
            )

            t0 = time.time()
            try:
                extract = extraction.assemble(md_text, provider=provider)
            except _DryRunStop as exc:
                print(f"      NOT CACHED — {exc}")
                continue
            except LLMParserError as exc:
                print(f"      FAILED: {exc}")
                results[model_key][path.name] = {"error": str(exc)}
                continue
            except Exception as exc:  # noqa: BLE001 — record, don't crash the whole run
                print(f"      FAILED ({type(exc).__name__}): {exc}")
                results[model_key][path.name] = {"error": f"{type(exc).__name__}: {exc}"}
                continue

            if args.dry_run:
                print("      FULLY CACHED — this file would cost $0.00")
                continue

            summary = summarize(extract)
            results[model_key][path.name] = summary
            out_file = run_dir / f"{path.stem}__{model_key}.json"
            out_file.write_text(json.dumps(extract.model_dump(mode="json"), indent=2))
            print(
                f"      -> {summary['n_exercises']} exercises, "
                f"{summary['n_working_sets']} sets, {summary['n_warnings']} warnings, "
                f"{time.time() - t0:.1f}s  ({out_file.name})"
            )
            for w in (extract.warnings or [])[:5]:
                print(f"         warn: {w}")

    if args.dry_run:
        print("\nDry run complete. No API calls were made, nothing was spent.")
        return 0

    print()
    print("=" * 78)
    print("SPEND")
    print("=" * 78)
    print(f"{'model':<8} {'calls':>7} {'cached':>7} {'in tok':>10} {'out tok':>9} {'cost':>10}")
    total = 0.0
    for k, u in usages.items():
        model = MODELS[k][0]
        c = u.cost(model)
        total += c
        print(f"{k:<8} {u.calls:>7} {u.cached_calls:>7} {u.input_tokens:>10,} "
              f"{u.output_tokens:>9,} ${c:>9.4f}")
    print(f"{'TOTAL':<8} {'':>7} {'':>7} {'':>10} {'':>9} ${total:>9.4f}")

    print()
    print("=" * 78)
    print("SIDE BY SIDE")
    print("=" * 78)
    for rel in args.files:
        name = Path(rel).name
        print(f"\n{name}")
        header = f"  {'model':<8} {'exercises':>10} {'sets':>6} {'warmups':>8} {'warns':>6} {'uncertain':>10}"
        print(header)
        for k in args.models:
            r = results.get(k, {}).get(name)
            if r is None:
                print(f"  {k:<8} {'(not run)':>10}")
            elif "error" in r:
                print(f"  {k:<8} ERROR: {r['error'][:60]}")
            else:
                print(f"  {k:<8} {r['n_exercises']:>10} {r['n_working_sets']:>6} "
                      f"{r['n_warmup_sets']:>8} {r['n_warnings']:>6} {r['n_uncertain']:>10}")

    report = run_dir / "summary.json"
    report.write_text(json.dumps({"run_id": run_id, "results": results}, indent=2))
    print(f"\nFull per-model JSON extracts + summary.json in: {run_dir}")
    print(f"Per-call log: {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
