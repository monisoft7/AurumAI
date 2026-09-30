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
    msg_file.write_text("TRADE ALERT BUY\n")
    
    monkeypatch.setattr(sys, "argv", ["prog", "send-telegram", "--message-file", str(msg_file), "--mode", "live-paper", "--run-url", "url"])
    assert main() == 0
    mock_send_telegram.assert_not_called()


def test_publisher_active_sends_allowed_messages(mock_send_telegram, tmp_path, monkeypatch):
    for msg in ["TRADE ALERT BUY\n", "TRADE ALERT SELL\n", "SYSTEM FAILURE\n"]:
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


def test_publisher_active_drops_market_alert(mock_send_telegram, tmp_path, monkeypatch):
    for msg in ["MARKET ALERT\n", "NO_TRADE\n", "SOMETHING ELSE\n"]:
        msg_file = tmp_path / "msg.txt"
        msg_file.write_text(msg)
        
        monkeypatch.setattr(sys, "argv", ["prog", "send-telegram", "--message-file", str(msg_file), "--mode", "live-paper", "--run-url", "url", "--active"])
        assert main() == 0
        mock_send_telegram.assert_not_called()
