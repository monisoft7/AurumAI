"""Immutable, private data cache for the gold lab. No production or macro inputs."""

import hashlib
import io
import json
import os
import re
import tempfile
import zipfile
from datetime import timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "runtime/gold_shadow/phase2"
PROTOCOL = Path(__file__).with_name("protocol.json")
EST = timezone(timedelta(hours=-5))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_hash(year, month=None):
    manifest = json.loads(Path(__file__).with_name("data_manifest.json").read_bytes())
    if month is None:
        return manifest[str(year)]["sha256"]
    if (year, month) == (2023, 4):
        return manifest["tick_execution_audit"]["tick_sha256"]
    raise ValueError("archive outside the registered cohort")


def write_atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        f.write(content)
        tmp = f.name
    try:
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def acquire(year, month=None, root=CACHE):
    period = f"{year}{month:02d}" if month else str(year)
    kind, slug = ("T", "tick-data-quotes") if month else ("M1", "1-minute-bar-quotes")
    path = root / f"histdata-{kind}-{period}.zip"
    meta = path.with_suffix(".json")
    expected = pinned_hash(year, month)
    if path.exists() and meta.exists():
        if (
            digest(path) != expected
            or json.loads(meta.read_bytes())["sha256"] != expected
        ):
            raise ValueError("cache fingerprint mismatch")
        return path
    url = f"https://www.histdata.com/download-free-forex-data/?/ascii/{slug}/xauusd/{year}"
    if month:
        url += f"/{month}"
    with requests.Session() as session:
        page = session.get(url, timeout=30)
        page.raise_for_status()
        form = re.search(r'<form id="file_down".*?</form>', page.text, re.S)
        if not form:
            raise ValueError("download form unavailable")
        fields = dict(
            re.findall(r'name="(\w+)" id="\w+" value="([^"]*)"', form.group())
        )
        if (fields.get("fxpair"), fields.get("timeframe"), fields.get("datemonth")) != (
            "XAUUSD",
            kind,
            period,
        ):
            raise ValueError("archive does not match requested sample")
        response = session.post(
            "https://www.histdata.com/get.php",
            data=fields,
            headers={"Referer": url},
            timeout=90,
        )
        response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if (
            len(names) != 1
            or "XAUUSD" not in names[0].upper()
            or period not in names[0]
            or z.testzip()
        ):
            raise ValueError("invalid archive contents")
    if hashlib.sha256(response.content).hexdigest() != expected:
        raise ValueError("provider archive differs from the registered data version")
    write_atomic(path, response.content)
    write_atomic(
        meta,
        json.dumps(
            {
                "url": url,
                "member": names[0],
                "sha256": digest(path),
                "period": period,
                "source_time": "fixed UTC-05:00",
            }
        ).encode(),
    )
    return path


def minute_data(path):
    with zipfile.ZipFile(path) as z:
        (name,) = [n for n in z.namelist() if n.lower().endswith(".csv")]
        with z.open(name) as f:
            data = pd.read_csv(
                f, sep=";", names=["time", "open", "high", "low", "close", "volume"]
            )
    data.index = (
        pd.to_datetime(data.pop("time"), format="%Y%m%d %H%M%S")
        .dt.tz_localize(EST)
        .dt.tz_convert("UTC")
    )
    return clean(data)


def clean(data):
    if data.index.tz is None:
        raise ValueError("expected timezone-aware minute quotes")
    raw = len(data)
    backwards = int((data.index.to_series().diff() < pd.Timedelta(0)).sum())
    ambiguous = data.index.duplicated(keep=False)
    data = data.loc[~ambiguous].sort_index()
    cols = ["open", "high", "low", "close"]
    x = data[cols]
    if (
        not np.isfinite(x).all().all()
        or (x <= 0).any().any()
        or (x.low > x[["open", "close"]].min(axis=1)).any()
        or (x.high < x[["open", "close"]].max(axis=1)).any()
    ):
        raise ValueError("invalid bid candles")
    # OTC XAU/USD maintenance and holiday closures are preserved as missing bars.
    ny = data.index.tz_convert("America/New_York")
    closed = (
        (ny.weekday == 5)
        | ((ny.weekday == 4) & (ny.hour >= 17))
        | ((ny.weekday == 6) & (ny.hour < 18))
    )
    closed |= ny.hour == 17
    valid = data.loc[~closed, cols].copy()
    if valid.empty:
        raise ValueError("no usable trading minutes")
    valid.index = valid.index.tz_convert("UTC")
    delta = valid.index.to_series().diff().dt.total_seconds()
    return valid, {
        "raw": raw,
        "out_of_order": backwards,
        "ambiguous_rows": int(ambiguous.sum()),
        "kept": len(valid),
        "excluded_closed": int(closed.sum()),
        "first": valid.index[0].isoformat(),
        "last": valid.index[-1].isoformat(),
        "gaps_over_one_minute": int((delta > 60).sum()),
        "max_gap_hours": round(delta.max() / 3600, 2),
    }


def tick_audit(path):
    with zipfile.ZipFile(path) as z:
        (name,) = [n for n in z.namelist() if n.lower().endswith(".csv")]
        with z.open(name) as f:
            ticks = pd.read_csv(
                f, names=["time", "bid", "ask", "volume"], dtype={"time": str}
            )
    idx = (
        pd.to_datetime(ticks.time, format="%Y%m%d %H%M%S%f")
        .dt.tz_localize(EST)
        .dt.tz_convert("UTC")
    )
    spread = ticks.ask - ticks.bid
    if (
        not idx.is_monotonic_increasing
        or not np.isfinite(spread).all()
        or (spread < 0).any()
    ):
        raise ValueError("invalid chronological bid/ask")
    return {
        "ticks": len(ticks),
        "first": idx.iloc[0].isoformat(),
        "last": idx.iloc[-1].isoformat(),
        "spread_median": round(float(spread.median()), 4),
        "spread_p95": round(float(spread.quantile(0.95)), 4),
    }
