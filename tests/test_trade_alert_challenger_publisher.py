import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

spec = importlib.util.spec_from_file_location("trade_alert_challenger_publisher", str(Path(__file__).resolve().parent.parent / "scripts/trade_alert_challenger_publisher.py"))
publisher = importlib.util.module_from_spec(spec)
sys.modules["trade_alert_challenger_publisher"] = publisher
spec.loader.exec_module(publisher)
main = publisher.main

@pytest.fixture
def mock_send_telegram():
    with patch("trade_alert_challenger_publisher.send_telegram_message") as mock:
        yield mock


def test_publisher_inactive_by_default(mock_send_telegram, tmp_path, monkeypatch):
    msg_file = tmp_path / "msg.txt"
    msg_file.write_text("🚨 TRADE ALERT — XAU/USD\nACTION: BUY")

    monkeypatch.setattr(sys, "argv", ["prog", "send-telegram", "--message-file", str(msg_file), "--mode", "live-paper", "--run-url", "url"])
    assert main() == 0
    mock_send_telegram.assert_not_called()


def test_publisher_active_sends_allowed_messages(mock_send_telegram, tmp_path, monkeypatch):
    allowed = [
        "🚨 TRADE ALERT — XAU/USD\nACTION: BUY",
        "🚨 TRADE ALERT — XAU/USD\nACTION: SELL",
        "SYSTEM FAILURE\nSomething went wrong",
        "🚨 SYSTEM FAILURE\nOh no"
    ]
    for msg in allowed:
        msg_file = tmp_path / "msg.txt"
        msg_file.write_text(msg)

        monkeypatch.setattr(sys, "argv", ["prog", "send-telegram", "--message-file", str(msg_file), "--mode", "live-paper", "--run-url", "url", "--active"])
        assert main() == 0
        mock_send_telegram.assert_called_once_with(
            msg,
            token="",
            chat_id=""
        )
        mock_send_telegram.reset_mock()


def test_publisher_active_drops_invalid_format(mock_send_telegram, tmp_path, monkeypatch):
    disallowed = [
        "MARKET ALERT\n",
        "NO_TRADE\n",
        "SOMETHING ELSE\n",
        "TRADE ALERT BUY\n", # incomplete format
        "🚨 TRADE ALERT — XAU/USD\nACTION: HOLD"
    ]
    for msg in disallowed:
        msg_file = tmp_path / "msg.txt"
        msg_file.write_text(msg)

        monkeypatch.setattr(sys, "argv", ["prog", "send-telegram", "--message-file", str(msg_file), "--mode", "live-paper", "--run-url", "url", "--active"])
        assert main() == 0
        mock_send_telegram.assert_not_called()
