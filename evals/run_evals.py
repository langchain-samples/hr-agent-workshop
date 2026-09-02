"""CI entrypoint: run the HR agent eval experiment and gate on a threshold.

This is the script CI calls (.github/workflows/evals.yml). It:

1. (Re)builds the LangSmith dataset from evals/hr_dataset.py.
2. DISCOVERS evaluators by TAG — not a hardcoded list — via the registry in
   evals/hr_evaluators.py. Default tag is "ci".
3. Runs client.evaluate(...) over the dataset.
4. Aggregates the mean of each evaluator key and FAILS (exit 1) if any tracked
   score is below the threshold, so the job acts as a promotion gate.

Configuration (all optional, via env or flags):
  EVAL_TAG            tag to select evaluators           (default: "ci")
  EVAL_THRESHOLD      minimum mean score to pass         (default: 0.8)
  EVAL_DATASET        dataset name                       (default: hr-agent-evals)
  EVAL_GATE_KEYS      comma-sep evaluator keys to gate   (default: all numeric keys)
  EVAL_MAX_CONCURRENCY  parallelism for the experiment   (default: 4)

Usage:
    python -m evals.run_evals
    python -m evals.run_evals --tag ci --threshold 0.85
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
from collections import defaultdict

from langsmith import Client

from evals.hr_dataset import DATASET_NAME, build_dataset
from evals.hr_evaluators import get_registered_by_tag, list_tags
from evals.target import run_hr_agent


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run HR agent evals as a CI gate.")
    p.add_argument("--tag", default=os.environ.get("EVAL_TAG", "ci"))
    p.add_argument(
        "--threshold",
        type=float,
        default=float(os.environ.get("EVAL_THRESHOLD", "0.8")),
    )
    p.add_argument("--dataset", default=os.environ.get("EVAL_DATASET", DATASET_NAME))
    p.add_argument(
        "--gate-keys",
        default=os.environ.get("EVAL_GATE_KEYS", ""),
        help="Comma-separated evaluator keys to gate on. Empty = all keys.",
    )
    p.add_argument(
        "--max-concurrency",
        type=int,
        default=int(os.environ.get("EVAL_MAX_CONCURRENCY", "4")),
    )
    p.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip rebuilding the dataset (assume it already exists).",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    client = Client()

    # 1. Dataset ----------------------------------------------------------------
    if args.skip_build and client.has_dataset(dataset_name=args.dataset):
        print(f"Using existing dataset '{args.dataset}'")
    else:
        ds = build_dataset(client, dataset_name=args.dataset)
        print(f"Built dataset '{ds.name}' ({ds.url})")

    # 2. Discover evaluators BY TAG (the registry lookup) -----------------------
    print(f"\nAvailable evaluator tags: {list_tags()}")
    registered = get_registered_by_tag(args.tag)
    if not registered:
        print(f"ERROR: no evaluators registered under tag '{args.tag}'.", file=sys.stderr)
        return 1
    evaluators = [r.fn for r in registered]
    print(f"Discovered {len(evaluators)} evaluator(s) for tag '{args.tag}': "
          f"{[r.key for r in registered]}")

    # 3. Run the experiment -----------------------------------------------------
    results = client.evaluate(
        run_hr_agent,
        data=args.dataset,
        evaluators=evaluators,
        experiment_prefix=f"hr-ci-{args.tag}",
        max_concurrency=args.max_concurrency,
    )
    print(f"\nExperiment: {results.experiment_name}")

    # 4. Aggregate + gate -------------------------------------------------------
    scores: dict[str, list[float]] = defaultdict(list)
    for row in results:
        for res in row["evaluation_results"]["results"]:
            if res.score is not None and isinstance(res.score, (int, float)):
                scores[res.key].append(float(res.score))

    if not scores:
        print("ERROR: no numeric scores produced.", file=sys.stderr)
        return 1

    gate_keys = (
        [k.strip() for k in args.gate_keys.split(",") if k.strip()]
        if args.gate_keys
        else list(scores.keys())
    )

    print(f"\n{'evaluator':28s} {'mean':>6s}  gate?")
    print("-" * 46)
    failures: list[str] = []
    for key in sorted(scores):
        mean = statistics.mean(scores[key])
        gated = key in gate_keys
        flag = ""
        if gated and mean < args.threshold:
            failures.append(f"{key}={mean:.3f} < {args.threshold}")
            flag = "  <-- BELOW THRESHOLD"
        print(f"{key:28s} {mean:6.3f}  {'yes' if gated else 'no ':>3s}{flag}")

    print(f"\nThreshold: {args.threshold}  |  gated keys: {gate_keys}")

    if failures:
        print("\nPROMOTION GATE FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("\nPromotion gate PASSED — all gated scores meet the threshold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
