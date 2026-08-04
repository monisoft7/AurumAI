# AurumAI Telegram Setup

Telegram is an **output channel only**: after a successful daily run the
institutional report is sent to a Telegram chat. Telegram failures never
affect the pipeline.

## Bot creation

1. Open Telegram and start a chat with **@BotFather**.
2. Send `/newbot`.
3. Choose a display name (e.g., `AurumAI Daily`).
4. Choose a username ending in `bot` (e.g., `aurumai_daily_bot`).
5. BotFather replies with the **bot token** — copy and keep it secret.

## Bot token

The token looks like `1234567890:AA...`. It is the bot's credential; it
must be stored in the environment, never committed to the repository.

## Chat ID

The chat ID is the destination chat that receives the reports:

- **Private chat with the bot:** send any message to the bot, then fetch
  the chat ID with the `getUpdates` endpoint:
  ```
  https://api.telegram.org/bot<TOKEN>/getUpdates
  ```
  The `chat.id` field of the latest update is the chat ID.
- **Alternative:** forward a message from the bot to @userinfobot
  (@RawDataBot) — it replies with the numeric chat ID.

## Environment variables

Add to `.env` at the repository root (the same file used by `run.py`):

```
TELEGRAM_BOT_TOKEN=<token from BotFather>
TELEGRAM_CHAT_ID=<numeric chat id>
```

The `.env` file is loaded automatically by the notifier when the variables
are not already present in the process environment.

## Verification command

Send a test message to confirm the connection:

```
python -m src.notifications.telegram_notifier --test
```

Expected output: `Telegram test message sent (message_id=...)`.

Send an already-generated report manually:

```
python -m src.notifications.telegram_notifier --send outputs/2026-08-03/institutional_report.md
```

## Behavior

- `scripts/run_daily.py` sends the report only after all verifications pass
  (pipeline exit code 0, report exists, registry record appended).
- Reports longer than Telegram's message limit are split automatically at
  line boundaries; markdown formatting (bold, code) is preserved via
  MarkdownV2, with a plain-text retry if Telegram rejects the entities.
- If Telegram is not configured or the send fails, the daily run still
  exits `0`; the summary prints the Telegram status.
- Exit code `2` from the notifier CLI means credentials are missing; `1`
  means the send failed (e.g., network, bad chat ID).
