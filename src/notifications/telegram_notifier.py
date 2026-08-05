"""AurumAI Telegram notification output channel.

Reads an already-generated institutional report
(``outputs/YYYY-MM-DD/<pipeline_id>/institutional_report.md``) and sends it
to a Telegram chat. The report is split into chunks within Telegram's message
size limit while preserving its markdown formatting.

This module is an output channel only. It never computes or alters pipeline
outputs, and every failure is contained here: a Telegram failure must never
affect the pipeline.

Configuration (environment variables, e.g. via ``.env``):

    TELEGRAM_BOT_TOKEN  bot token from @BotFather
    TELEGRAM_CHAT_ID    target chat id

Usage:

    python -m src.notifications.telegram_notifier --test
    python -m src.notifications.telegram_notifier --send outputs/YYYY-MM-DD/<pipeline_id>/institutional_report.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent

API_BASE = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_CHARS = 4096
REQUEST_TIMEOUT_SECONDS = 30

_MD2_SPECIAL = re.compile(r"([_*\[\]()~`>#+\-=|{}.!\\])")


class TelegramConfigurationError(RuntimeError):
    """Raised when Telegram credentials are missing or incomplete."""


class TelegramSendError(RuntimeError):
    """Raised when a message could not be delivered to Telegram."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def load_credentials(root: Path = ROOT) -> tuple[str, str]:
    """Return (bot_token, chat_id) from the environment.

    If the environment is missing the credentials and a ``.env`` file exists
    at the repository root, it is loaded first.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        env_file = root / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == "TELEGRAM_BOT_TOKEN" and not token:
                    token = value
                elif key == "TELEGRAM_CHAT_ID" and not chat_id:
                    chat_id = value
    if not token or not chat_id:
        raise TelegramConfigurationError(
            "Telegram credentials missing: set TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHAT_ID in the environment or .env"
        )
    return token, chat_id


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def escape_markdown_v2(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters.

    Bold spans (``**...**``), inline code (``...``) and fenced code blocks
    are preserved; special characters inside bold text are escaped so the
    bold rendering stays valid.
    """
    token_re = re.compile(
        r"(```[\s\S]*?```|`[^`\n]*`|\*\*[^*]+\*\*)",
        re.DOTALL,
    )
    parts: list[str] = []
    position = 0
    for match in token_re.finditer(text):
        parts.append(_MD2_SPECIAL.sub(r"\\\1", text[position:match.start()]))
        token = match.group(0)
        if token.startswith("```"):
            parts.append(token)
        elif token.startswith("`"):
            parts.append(token)
        else:
            parts.append("**" + _MD2_SPECIAL.sub(r"\\\1", token[2:-2]) + "**")
        position = match.end()
    parts.append(_MD2_SPECIAL.sub(r"\\\1", text[position:]))
    return "".join(parts)


def split_report(text: str, max_chars: int = MAX_MESSAGE_CHARS) -> list[str]:
    """Split a report into message-sized chunks without breaking lines."""
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in text.splitlines(keepends=True):
        if current_len + len(line) <= max_chars:
            current.append(line)
            current_len += len(line)
            continue
        if current:
            chunks.append("".join(current))
            current = []
            current_len = 0
        if len(line) > max_chars:
            for start in range(0, len(line), max_chars):
                chunks.append(line[start : start + max_chars])
        else:
            current.append(line)
            current_len = len(line)
    if current:
        chunks.append("".join(current))
    return chunks


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def _api_payload(token: str, chat_id: str, text: str,
                 parse_mode: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return payload


def send_message(token: str, chat_id: str, text: str) -> int:
    """Send one message; returns the Telegram message id.

    Uses MarkdownV2 parsing; if Telegram rejects the markdown entities the
    message is retried once as plain text.
    """
    url = API_BASE.format(token=token)
    body = json.dumps(_api_payload(token, chat_id, text, "MarkdownV2")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        response = urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS)
        data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = ""
        try:
            error_data = json.loads(exc.read().decode("utf-8"))
            message = str(error_data.get("description", ""))
        except (ValueError, OSError):
            message = ""
        if exc.code == 400 and "parse" in message.lower():
            plain_body = json.dumps(
                _api_payload(token, chat_id, text, None)
            ).encode("utf-8")
            plain_request = urllib.request.Request(
                url,
                data=plain_body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            response = urllib.request.urlopen(
                plain_request, timeout=REQUEST_TIMEOUT_SECONDS
            )
            data = json.loads(response.read().decode("utf-8"))
        else:
            raise TelegramSendError(
                f"Telegram API error {exc.code}: {message or str(exc)}"
            ) from exc
    except urllib.error.URLError as exc:
        raise TelegramSendError(f"Telegram unreachable: {exc}") from exc
    if not data.get("ok"):
        raise TelegramSendError(
            f"Telegram API rejected the message: {data.get('description', data)}"
        )
    result = data.get("result", {})
    message_id = result.get("message_id")
    return int(message_id) if message_id is not None else 0


def send_report(
    report_path: Path,
    token: str | None = None,
    chat_id: str | None = None,
    root: Path = ROOT,
) -> int:
    """Send an already-generated report to Telegram. Returns message count.

    Credentials come from the environment (or ``.env``) when not provided.
    """
    if not report_path.exists():
        raise FileNotFoundError(f"report not found: {report_path}")
    if token is None or chat_id is None:
        token, chat_id = load_credentials(root)
    text = report_path.read_text(encoding="utf-8")
    chunks = split_report(text)
    message_count = 0
    for chunk in chunks:
        send_message(token, chat_id, escape_markdown_v2(chunk))
        message_count += 1
    return message_count


def verify_connection(token: str | None = None, chat_id: str | None = None,
                      root: Path = ROOT) -> int:
    """Send a test message; returns the Telegram message id."""
    if token is None or chat_id is None:
        token, chat_id = load_credentials(root)
    return send_message(token, chat_id, "AurumAI notification test: connection OK")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.notifications.telegram_notifier",
        description="AurumAI Telegram output channel.",
    )
    parser.add_argument("--test", action="store_true",
                        help="Send a test message to verify the connection.")
    parser.add_argument("--send", metavar="REPORT_PATH",
                        help="Send an already-generated report markdown file.")
    args = parser.parse_args(argv)

    try:
        if args.test:
            message_id = verify_connection()
            print(f"Telegram test message sent (message_id={message_id})")
            return 0
        if args.send:
            message_count = send_report(Path(args.send))
            print(f"Report sent to Telegram in {message_count} message(s)")
            return 0
    except TelegramConfigurationError as exc:
        print(f"telegram_notifier: {exc}", file=sys.stderr)
        return 2
    except (FileNotFoundError, TelegramSendError) as exc:
        print(f"telegram_notifier: {exc}", file=sys.stderr)
        return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
