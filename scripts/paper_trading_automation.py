"""Command-line entry point for daily Paper Trading automation."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_trading.automation import (  # noqa: E402
    AutomationFailure,
    execute_automation,
    send_telegram_message,
    write_failure_artifacts,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AurumAI daily paper automation")
    commands = parser.add_subparsers(dest="command", required=True)
    execute = commands.add_parser("execute")
    execute.add_argument("--mode", choices=("dry-run", "live-paper"), required=True)
    execute.add_argument("--strategy-dir", type=Path, required=True)
    execute.add_argument("--harness-dir", type=Path, required=True)
    execute.add_argument("--ledger-dir", type=Path, required=True)
    execute.add_argument("--output-dir", type=Path, required=True)
    execute.add_argument("--market-date", required=True)
    execute.add_argument("--ledger-repository", required=True)
    execute.add_argument("--run-id", required=True)
    execute.add_argument("--run-url", required=True)

    send = commands.add_parser("send-telegram")
    send.add_argument("--message-file", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "send-telegram":
        try:
            send_telegram_message(
                args.message_file.read_text(encoding="utf-8"),
                token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
            )
        except (AutomationFailure, OSError) as exc:
            print(f"Telegram notification failed: {type(exc).__name__}", file=sys.stderr)
            return 1
        return 0

    try:
        execute_automation(
            mode=args.mode,
            strategy_dir=args.strategy_dir,
            harness_dir=args.harness_dir,
            ledger_dir=args.ledger_dir,
            output_dir=args.output_dir,
            market_date=args.market_date,
            ledger_repository=args.ledger_repository,
            run_id=args.run_id,
            run_url=args.run_url,
            environment=os.environ,
        )
    except AutomationFailure as exc:
        write_failure_artifacts(
            args.output_dir,
            exc,
            run_url=args.run_url,
            environment=os.environ,
        )
        print(f"Paper automation stopped safely at {exc.stage}", file=sys.stderr)
        return 1
    except Exception as exc:
        failure = AutomationFailure(
            "automation", "unexpected safe stop", error_type=type(exc).__name__
        )
        write_failure_artifacts(
            args.output_dir,
            failure,
            run_url=args.run_url,
            environment=os.environ,
        )
        print("Paper automation stopped safely at automation", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
