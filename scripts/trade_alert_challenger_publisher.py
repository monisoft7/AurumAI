"""Command-line entry point for Trade Alert Challenger publisher."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paper_trading.automation import (
    AutomationFailure,
    format_failure_message,
    send_telegram_message,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AurumAI Trade Alert Challenger publisher")
    commands = parser.add_subparsers(dest="command", required=True)

    send = commands.add_parser("send-telegram")
    send.add_argument("--message-file", type=Path, required=True)
    send.add_argument("--mode", choices=("dry-run", "live-paper"), required=True)
    send.add_argument("--run-url", required=True)
    # The publisher is currently inactive by default unless overridden.
    send.add_argument("--active", action="store_true", help="Activate the publisher")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "send-telegram":
        if args.mode == "dry-run" or not args.active:
            return 0
        try:
            message = (
                args.message_file.read_text(encoding="utf-8")
                if args.message_file.is_file()
                else format_failure_message(
                    stage="workflow",
                    reason="workflow stopped before its summary was created",
                    run_url=args.run_url,
                )
            )

            # Challenger only sends canonical TRADE ALERT or SYSTEM FAILURE
            lines = message.strip().split("\n")
            is_valid_alert = (
                len(lines) >= 2 and
                lines[0].strip() == "🚨 TRADE ALERT — XAU/USD" and
                lines[1].strip() in ("ACTION: BUY", "ACTION: SELL")
            )
            is_system_failure = message.strip().startswith("SYSTEM FAILURE") or message.strip().startswith("🚨 SYSTEM FAILURE")

            if not (is_valid_alert or is_system_failure):
                return 0

            send_telegram_message(
                message,
                token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
                chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
            )
        except (AutomationFailure, OSError) as exc:
            print(f"Telegram notification failed: {type(exc).__name__}", file=sys.stderr)
            return 1
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
