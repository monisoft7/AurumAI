"""Bounded, read-only multi-asset acquisition for the predictive round."""

import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

import requests

from .data import CACHE, digest, minute_data, pinned_hash, write_atomic

HERE = Path(__file__).parent
PRIVATE = CACHE.parent / "phase3"
YEARS = (2023, 2024)
CROSS = ("EURUSD", "USDJPY", "XAGUSD")
MANIFEST = HERE / "predictive_data.json"


def archive(symbol, year):
    if year not in YEARS or symbol not in ("XAUUSD", *CROSS):
        raise ValueError("outside registered research population")
    if symbol == "XAUUSD":
        return CACHE / f"histdata-M1-{year}.zip"
    return PRIVATE / f"{symbol}-{year}.zip"


def download(symbol, year):
    path = archive(symbol, year)
    url = f"https://www.histdata.com/download-free-forex-data/?/ascii/1-minute-bar-quotes/{symbol.lower()}/{year}"
    if path.exists():
        return path
    if symbol == "XAUUSD":
        from .data import acquire

        return acquire(year)
    with requests.Session() as session:
        page = session.get(url, timeout=35)
        page.raise_for_status()
        form = re.search(r'<form id="file_down".*?</form>', page.text, re.S)
        if not form:
            raise ValueError("provider form unavailable")
        fields = dict(
            re.findall(r'name="(\w+)" id="\w+" value="([^"]*)"', form.group())
        )
        if (fields.get("fxpair"), fields.get("timeframe"), fields.get("datemonth")) != (
            symbol,
            "M1",
            str(year),
        ):
            raise ValueError("provider form disagrees with requested archive")
        response = session.post(
            "https://www.histdata.com/get.php",
            data=fields,
            headers={"Referer": url},
            timeout=90,
        )
        response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        members = [n.upper() for n in z.namelist() if n.lower().endswith(".csv")]
        if len(members) != 1 or f"{symbol}_M1_{year}" not in members[0] or z.testzip():
            raise ValueError("unexpected archive")
    if MANIFEST.exists():
        want = json.loads(MANIFEST.read_bytes())["assets"][symbol][str(year)]["sha256"]
        if hashlib.sha256(response.content).hexdigest() != want:
            raise ValueError("revised provider archive")
    write_atomic(path, response.content)
    return path


def load(symbol, year, manifest):
    path = archive(symbol, year)
    if digest(path) != manifest["assets"][symbol][str(year)]["sha256"]:
        raise ValueError("research data fingerprint mismatch")
    return minute_data(path)[0]


def collect():
    old = json.loads(MANIFEST.read_bytes()) if MANIFEST.exists() else None
    evidence = {"assets": {}, "unavailable": {}}
    for symbol in ("XAUUSD", *CROSS):
        rows = {}
        for year in YEARS:
            try:
                path = download(symbol, year)
                sha = digest(path)
                if symbol == "XAUUSD" and sha != pinned_hash(year):
                    raise ValueError("gold version changed")
                if old and sha != old["assets"][symbol][str(year)]["sha256"]:
                    raise ValueError("archive differs from frozen manifest")
                _, quality = minute_data(path)
                rows[str(year)] = {**quality, "sha256": sha}
                print(symbol, year, quality["kept"], flush=True)
            except (requests.RequestException, ValueError, zipfile.BadZipFile) as exc:
                if old or symbol == "XAUUSD":
                    raise
                evidence["unavailable"][symbol] = (
                    type(exc).__name__ + ": " + str(exc)[:180]
                )
                print(symbol, year, evidence["unavailable"][symbol], flush=True)
                break
        if len(rows) == len(YEARS):
            evidence["assets"][symbol] = rows
    if old and old != evidence:
        raise ValueError("manifest disagrees")
    if not old:
        write_atomic(MANIFEST, (json.dumps(evidence, indent=2) + "\n").encode())


if __name__ == "__main__":
    collect()
