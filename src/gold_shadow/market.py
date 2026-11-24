"""Twelve Data observations. All bar timestamps denote the UTC interval open."""
import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
STEP = timedelta(minutes=15)
SOURCE = "Twelve Data XAU/USD"


@dataclass(frozen=True)
class Bar:
    start: datetime
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self):
        if self.start.utcoffset() != timedelta(0) or self.start.timestamp() % 900:
            raise ValueError("expected an aligned UTC M15 bar")
        prices = (self.open, self.high, self.low, self.close)
        if not all(math.isfinite(n) and n > 0 for n in prices):
            raise ValueError("invalid spot price")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("invalid OHLC envelope")

    def snapshot(self):
        return dict(asdict(self), start=self.start.isoformat())


def request(endpoint, **params):
    key = os.environ.get("TWELVE_DATA_API_KEY")
    if not key:
        raise ValueError("TWELVE_DATA_API_KEY unavailable")
    url = "https://api.twelvedata.com/" + endpoint + "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"Authorization": "apikey " + key})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.load(response)
    except (OSError, ValueError) as exc:
        raise RuntimeError("Twelve Data request failed: " + type(exc).__name__) from None
    if not isinstance(data, dict) or data.get("status") == "error":
        raise RuntimeError("Twelve Data rejected request, code " + str(data.get("code") if isinstance(data, dict) else "unknown"))
    return data


def fetch_bars(asof, size):
    data = request("time_series", symbol="XAU/USD", interval="15min", timezone="UTC",
                   end_date=asof.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S"), outputsize=size)
    meta = data["meta"]
    if meta["symbol"] != "XAU/USD" or meta["interval"] != "15min" or meta.get("timezone", meta.get("exchange_timezone", "UTC")) not in ("UTC", "Etc/UTC"):
        raise ValueError("unexpected symbol, interval or timezone")
    bars = sorted((Bar(datetime.fromisoformat(r["datetime"]).replace(tzinfo=UTC),
                       *(float(r[k]) for k in ("open", "high", "low", "close"))) for r in data["values"]),
                  key=lambda b: b.start)
    if len({b.start for b in bars}) != len(bars):
        raise ValueError("duplicate provider bars")
    return [b for b in bars if b.start + STEP <= asof]


def fetch_quote():
    data = request("exchange_rate", symbol="XAU/USD")
    if data.get("symbol") != "XAU/USD":
        raise ValueError("unexpected quote instrument")
    price = float(data["rate"])
    if not math.isfinite(price) or price <= 0:
        raise ValueError("invalid spot quote")
    return price, datetime.fromtimestamp(int(data["timestamp"]), UTC)
