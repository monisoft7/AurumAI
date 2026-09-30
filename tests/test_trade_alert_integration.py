import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

from trade_alert.engine import Alert, format_alert

import importlib.util
spec = importlib.util.spec_from_file_location("trade_alert_challenger_publisher", str(Path(__file__).resolve().parent.parent / "scripts/trade_alert_challenger_publisher.py"))
publisher = importlib.util.module_from_spec(spec)
sys.modules["trade_alert_challenger_publisher"] = publisher
spec.loader.exec_module(publisher)


def test_format_alert_accepted_by_publisher(tmp_path, monkeypatch):
    alert = Alert(
        action="TRADE_ALERT BUY",
        setup="trend_pullback",
        entry_low=1998.0,
        entry_high=2002.0,
        current_price=2000.0,
        sl=1990.0,
        tp1=2015.0,
        tp2=2020.0,
        tp3=2030.0,
        rr1=1.5,
        rr2=2.0,
        rr3=3.0,
        directional_conviction=0.8,
        execution_quality=0.7,
        strongest_counterargument="H1 trend can reverse before TP1",
        invalidation="M15 closes beyond 1990.00",
        valid_until=datetime(2026, 9, 30, 12, 15, tzinfo=timezone.utc),
        reason="trend_pullback: H1 EMA alignment and confirmed structure with M15 price trigger",
        initial_allocation=0.25,
        risk_budget_pct=0.25
    )
    msg = format_alert(alert)
    
    msg_file = tmp_path / "msg.txt"
    msg_file.write_text(msg, encoding="utf-8")
    
    with patch("trade_alert_challenger_publisher.send_telegram_message") as mock_send:
        monkeypatch.setattr(sys, "argv", ["prog", "send-telegram", "--message-file", str(msg_file), "--mode", "live-paper", "--run-url", "url", "--active"])
        assert publisher.main() == 0
        mock_send.assert_called_once_with(msg, token="", chat_id="")
