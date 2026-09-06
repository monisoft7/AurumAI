"""Offline CLI for the immutable AurumAI paper-trading ledger."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_trading.ledger import (  # noqa: E402
    PaperTradingError,
    create_prediction_manifest,
    evaluate_prediction,
    summarize_cohort,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline paper-trading ledger")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="freeze a completed runtime")
    create.add_argument("--runtime-dir", type=Path, required=True)
    create.add_argument("--registry-dir", type=Path, required=True)
    create.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "paper_trading_baseline.json",
    )
    create.add_argument("--baseline-commit", required=True)

    evaluate = commands.add_parser("evaluate", help="evaluate one session horizon")
    evaluate.add_argument("--prediction", type=Path, required=True)
    evaluate.add_argument("--outcomes-dir", type=Path, required=True)
    evaluate.add_argument("--prices", type=Path, required=True)
    evaluate.add_argument("--horizon", type=int, choices=(1, 3, 5), required=True)
    evaluate.add_argument("--as-of-utc", required=True)
    evaluate.add_argument(
        "--freshness-status",
        choices=("fresh", "current", "stale", "unavailable", "missing"),
        default="fresh",
    )

    summary = commands.add_parser("summarize", help="summarize one frozen cohort")
    summary.add_argument("--registry-dir", type=Path, required=True)
    summary.add_argument("--evaluation-id", required=True)
    summary.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "create":
            path = create_prediction_manifest(
                args.runtime_dir,
                args.registry_dir,
                args.config,
                baseline_commit=args.baseline_commit,
            )
            print(path)
        elif args.command == "evaluate":
            path = evaluate_prediction(
                args.prediction,
                args.outcomes_dir,
                args.prices,
                horizon_sessions=args.horizon,
                as_of_utc=args.as_of_utc,
                freshness_status=args.freshness_status,
            )
            print(path)
        else:
            payload = summarize_cohort(args.registry_dir, args.evaluation_id)
            rendered = json.dumps(payload, indent=2, sort_keys=True)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(rendered + "\n", encoding="utf-8")
            print(rendered)
    except PaperTradingError as exc:
        print(f"paper-trading integrity error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
