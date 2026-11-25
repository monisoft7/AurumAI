"""Prequential predictive experiment on the two explicitly registered research years."""

import argparse
import hashlib
import json
import sys
import time

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from threadpoolctl import threadpool_limits

from .data import ROOT, write_atomic
from .predictive_data import HERE, MANIFEST, YEARS, load
from .strategies import completed

RESULT = HERE / "predictive_results.json"
PROTOCOL = HERE / "predictive_protocol.json"
CALENDAR = ROOT / "data/calendar/cpi_releases_bls_verified.csv"
HORIZONS = (15, 30, 60, 240, 1440)
CONTINUOUS = {"absolute_return_bps", "realized_vol_bps"}
GROUPS = ("gold", "cross", "event")
DAY = pd.Timedelta(days=1)


def shifted_return(close, steps):
    return 1e4 * (np.log(close) - np.log(close.shift(steps)))


def first_touch(minutes, index, prices, distance):
    # Timestamp t is the end of a completed bar. Minute t is the first future bar.
    pos = minutes.index.get_indexer(index)
    end = minutes.index.get_indexer(index + pd.Timedelta(minutes=59))
    available = (pos >= 0) & (end == pos + 59) & np.isfinite(distance) & (distance > 0)
    out = np.full(len(index), np.nan)
    loc = np.flatnonzero(available)
    hi, lo = minutes.high.to_numpy(), minutes.low.to_numpy()
    upper = prices * np.exp(distance / 1e4)
    lower = prices * np.exp(-distance / 1e4)
    for chunk in np.array_split(loc, max(1, len(loc) // 2000)):
        if not len(chunk):
            continue
        offsets = pos[chunk, None] + np.arange(60)
        up = hi[offsets] >= upper[chunk, None]
        down = lo[offsets] <= lower[chunk, None]
        u = np.where(up.any(axis=1), up.argmax(axis=1), 60)
        d = np.where(down.any(axis=1), down.argmax(axis=1), 60)
        out[chunk] = np.where((u == d) & (u < 60), np.nan, (u < d).astype(float))
    return pd.Series(out, index=index)


def gold_features(gold):
    bars = completed(gold, 15).asfreq("15min")
    close = bars.close
    r = shifted_return(close, 1)
    features = pd.DataFrame(index=close.index)
    for n in (1, 4, 16):
        features[f"r{n}"] = shifted_return(close, n).where(r.rolling(n).count() == n)
    for n in (4, 16):
        features[f"v{n}"] = np.sqrt(r.pow(2).rolling(n).sum())
    features["range"] = 1e4 * np.log(bars.high / bars.low)
    angle = 2 * np.pi * (close.index.hour + close.index.minute / 60) / 24
    features["sin"], features["cos"] = np.sin(angle), np.cos(angle)
    return close, r, features


def panel(manifest):
    def minutes(symbol):
        return pd.concat([load(symbol, year, manifest) for year in YEARS]).sort_index()

    gold = minutes("XAUUSD")
    close, r, features = gold_features(gold)
    groups = {"gold": list(features.columns)}
    for symbol in manifest["assets"]:
        if symbol == "XAUUSD":
            continue
        # Extra quarter lag and exact UTC joins tolerate non-simultaneous feed publication.
        x = completed(minutes(symbol), 15).close.reindex(close.index)
        one = shifted_return(x, 1)
        for n in (1, 4):
            features[f"{symbol}_{n}"] = (
                shifted_return(x, n).where(one.rolling(n).count() == n).shift(1)
            )
    usd = [
        sign * features[f"{s}_4"]
        for s, sign in (("EURUSD", -1), ("USDJPY", 1))
        if f"{s}_4" in features
    ]
    if usd:
        features["dollar_gold"] = sum(usd) / len(usd) * features["r4"]
    groups["cross"] = list(features.columns)
    calendar = pd.read_csv(CALENDAR)
    dates = (
        pd.DatetimeIndex(pd.to_datetime(calendar.release_timestamp))
        .tz_localize("America/New_York")
        .tz_convert("UTC")
    )
    lag = np.searchsorted(dates.asi8, close.index.asi8, side="left") - 1
    since = close.index.asi8 - dates.asi8[lag.clip(0)]
    features["post_cpi"] = ((lag >= 0) & (since >= 60e9) & (since <= 3600e9)).astype(
        float
    )
    features["cpi_vol"] = features.post_cpi * features.v4
    groups["event"] = list(features.columns)
    labels = {}
    for h in HORIZONS:
        n = h // 15
        future = 1e4 * np.log(close.shift(-n) / close)
        if h == 1440:
            valid = (close.notna().rolling(n).sum().shift(-n) >= 88) & (
                (close.index + DAY).weekday < 5
            )
        else:
            valid = r.notna().rolling(n).sum().shift(-n) == n
        labels[f"up_{h}"] = (future > 0).astype(float).where(future.notna() & valid)
    ret = (1e4 * np.log(close.shift(-4) / close)).where(labels["up_60"].notna())
    labels["absolute_return_bps"] = ret.abs()
    labels["realized_vol_bps"] = np.sqrt(r.pow(2).rolling(4).sum().shift(-4))
    labels["large_move"] = (
        (ret.abs() > 1.5 * features.v4)
        .astype(float)
        .where(ret.notna() & features.v4.notna())
    )
    labels["upper_first"] = first_touch(
        gold, close.index, close.to_numpy(), features.v4.to_numpy()
    ).where(ret.notna())
    clock = close.index
    mask = (
        (clock.weekday < 5)
        & ((clock.hour * 60 + clock.minute) >= 420)
        & ((clock.hour * 60 + clock.minute) <= 1260)
    )
    x = features.loc[mask].dropna()
    return x, pd.DataFrame(labels).reindex(x.index), groups, gold


def logistic_weights(a, y, penalty):
    def objective(w):
        z = a @ w
        return (
            np.mean(np.logaddexp(0, z) - y * z) + 0.5 * np.dot(penalty, w * w),
            a.T @ (expit(z) - y) / len(y) + penalty * w,
        )

    sol = minimize(
        objective,
        np.zeros(a.shape[1]),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 250, "ftol": 1e-11},
    )
    if not sol.success:
        raise ValueError(sol.message)
    return sol.x


def fit_predict(train, y, test, strength, binary):
    mean, std = train.mean(0), train.std(0)
    std[std < 1e-10] = 1.0
    a = np.column_stack([np.ones(len(train)), (train - mean) / std])
    b = np.column_stack([np.ones(len(test)), (test - mean) / std])
    penalty = np.full(a.shape[1], strength)
    penalty[0] = 0
    if binary:
        return expit(b @ logistic_weights(a, y, penalty))
    w = np.linalg.solve(
        a.T @ a / len(y) + np.diag(penalty), a.T @ np.log(y + 0.05) / len(y)
    )
    return np.maximum(0, np.exp(b @ w) - 0.05)


def loss(y, p, binary):
    return (y - p) ** 2 if binary else np.abs(y - p)


def refs(train, y, test, target):
    binary = target not in CONTINUOUS
    center = float(y.mean() if binary else y.median())
    refs = {"climatology": np.full(len(test), center)}
    if target.startswith("up_"):
        key, query = train.r1.gt(0), test.r1.gt(0)
        refs["fair_coin"] = np.full(len(test), 0.5)
    else:
        key, query = train.index.hour, test.index.hour
    grouped = y.groupby(np.asarray(key))
    by = grouped.mean() if binary else grouped.median()
    refs["conditional"] = pd.Series(np.asarray(query)).map(by).fillna(center).to_numpy()
    if not binary:
        refs["persistence"] = test.v4.to_numpy()
    return refs


def bounds(gains):
    a = np.asarray(gains)
    rng = np.random.default_rng(1951)
    n = len(a)
    starts = rng.integers(0, n, (5000, (n + 4) // 5))
    idx = ((starts[:, :, None] + np.arange(5)) % n).reshape(5000, -1)[:, :n]
    sample = a[idx].mean(1)
    return {
        "mean": float(a.mean()),
        "ci95": np.quantile(sample, [0.025, 0.975]).tolist(),
        "lower_corrected": float(np.quantile(sample, 0.05 / 135)),
    }


def economic(series, minutes, delay, mult):
    last = None
    pnl = []
    offered = missing = overlap = 0
    for stamp, p in series.items():
        if abs(p - 0.5) < 0.10:
            continue
        offered += 1
        a = stamp + pd.Timedelta(minutes=delay)
        b = a + pd.Timedelta(hours=1)
        if last is not None and a < last:
            overlap += 1
            continue
        i, j = minutes.index.get_indexer([a, b])
        if i < 0 or j != i + 60:
            missing += 1
            continue
        side = 1 if p > 0.5 else -1
        net = side * (minutes.open.iat[j] - minutes.open.iat[i]) - 0.70 * mult
        pnl.append(net)
        last = b
    return {
        "opportunities": len(series),
        "above_threshold": offered,
        "overlap": overlap,
        "missing": missing,
        "trades": len(pnl),
        "net_usd_per_oz": sum(pnl),
        "per_opportunity": sum(pnl) / len(series),
    }


def evaluate(x, labels, groups, minutes):
    results = {}
    economic_results = {}
    for target in labels:
        y = labels[target].dropna()
        binary = target not in CONTINUOUS
        blocks = {g: [] for g in GROUPS}
        folds = {g: [] for g in GROUPS}
        for start in pd.date_range("2024-01-01", "2024-10-01", freq="QS", tz="UTC"):
            stop = start + pd.DateOffset(months=3)
            train = y[y.index < start - DAY]
            inner = start - pd.Timedelta(days=90)
            fit = train[train.index < inner - DAY]
            tune = train[train.index >= inner]
            test = y[(y.index >= start) & (y.index < stop - DAY)]
            reference = refs(x.loc[train.index], train, x.loc[test.index], target)
            previous = None
            for group in GROUPS:
                columns = groups[group]

                def predict(a, b, s):
                    return fit_predict(
                        x.loc[a.index, columns].to_numpy(),
                        a.to_numpy(),
                        x.loc[b.index, columns].to_numpy(),
                        s,
                        binary,
                    )

                strengths = (0.001, 0.1)
                chosen = min(
                    strengths,
                    key=lambda s: loss(
                        tune.to_numpy(), predict(fit, tune, s), binary
                    ).mean(),
                )
                p = predict(train, test, chosen)
                loss_p = loss(test.to_numpy(), p, binary)
                frame = pd.DataFrame(
                    {"prediction": p, "truth": test, "loss": loss_p}, index=test.index
                )
                for name, b in reference.items():
                    frame[name] = loss(test.to_numpy(), b, binary) - loss_p
                if previous is not None:
                    frame["incremental"] = previous - loss_p
                previous = loss_p
                blocks[group].append(frame)
                folds[group].append(
                    {
                        "start": str(start.date()),
                        "n": len(test),
                        "inner_strength": chosen,
                        "loss": float(loss_p.mean()),
                        "gains": {
                            k: float(
                                frame[k].groupby(frame.index.normalize()).mean().mean()
                            )
                            for k in frame.columns[3:]
                        },
                    }
                )
        table = {}
        for group in GROUPS:
            df = pd.concat(blocks[group])
            comparisons = {
                k: bounds(df[k].groupby(df.index.normalize()).mean())
                for k in df.columns[3:]
            }
            robust = {
                k: (
                    v["lower_corrected"] > 0
                    and all(f["gains"][k] > 0 for f in folds[group])
                )
                for k, v in comparisons.items()
            }
            row = {
                "rows": len(df),
                "loss": float(df.loss.mean()),
                "comparisons": comparisons,
                "folds": folds[group],
                "passes_references": all(
                    v for k, v in robust.items() if k != "incremental"
                ),
                "passes_incremental": robust.get("incremental"),
                "common_days": df.index.normalize().nunique(),
            }
            # Descriptive fixed partitions only. A quarter's features never set a decision threshold.
            state = x.loc[df.index]
            regimes = {
                "recent_vol_above_4h_rate": state.v4 > state.v16 / 2,
                "recent_vol_below_or_equal": state.v4 <= state.v16 / 2,
                "post_cpi_hour": state.post_cpi == 1,
            }
            row["conditions"] = {
                name: {
                    "n": int(mask.sum()),
                    "loss": float(df.loc[mask, "loss"].mean()),
                    "gain_vs_climatology": float(df.loc[mask, "climatology"].mean()),
                }
                for name, mask in regimes.items()
                if mask.any()
            }
            if binary:
                row.update(
                    hit_rate=float(((df.prediction >= 0.5) == df.truth).mean()),
                    mean_prediction=float(df.prediction.mean()),
                    prevalence=float(df.truth.mean()),
                )
                row["calibration"] = [
                    {
                        "n": len(d),
                        "p": float(d.prediction.mean()),
                        "actual": float(d.truth.mean()),
                    }
                    for _, d in df.groupby(
                        pd.cut(
                            df.prediction, [0, 0.4, 0.5, 0.6, 1], include_lowest=True
                        ),
                        observed=True,
                    )
                ]
            if target == "up_60" and group == "event":
                economic_results = {
                    k: economic(df.prediction, minutes, d, m)
                    for k, d, m in [("base", 1, 1), ("double", 1, 2), ("delay", 5, 1)]
                }
            table[group] = row
        results[target] = table
        print(target, len(df), flush=True)
    return results, economic_results


def peak_mb():
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
                (k, ctypes.c_size_t)
                for k in ("peak", "ws", "a", "b", "c", "d", "e", "f")
            ]

        c = Counters()
        c.cb = ctypes.sizeof(c)
        query = ctypes.windll.psapi.GetProcessMemoryInfo
        query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if query(wintypes.HANDLE(-1), ctypes.byref(c), c.cb):
            return round(c.peak / 2**20, 2)
        return None
    import resource

    return round(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / (2**20 if sys.platform == "darwin" else 1024),
        2,
    )


def run():
    start, cpu = time.monotonic(), time.process_time()
    manifest = json.loads(MANIFEST.read_bytes())
    x, y, groups, minutes = panel(manifest)
    with threadpool_limits(limits=1):
        table, money = evaluate(x, y, groups, minutes)

    def fingerprint(p):
        return hashlib.sha256(p.read_text(encoding="utf8").encode()).hexdigest()

    return {
        "protocol_sha256": fingerprint(PROTOCOL),
        "manifest_sha256": fingerprint(MANIFEST),
        "calendar_sha256": fingerprint(CALENDAR),
        "eligible_feature_rows": len(x),
        "features": groups,
        "targets": table,
        "economic": money,
        "post_cpi_rows_2024": int(x.loc["2024"].post_cpi.sum()),
        "resources": {
            "seconds": round(time.monotonic() - start, 2),
            "cpu_seconds": round(time.process_time() - cpu, 2),
            "peak_process_mib": peak_mb(),
            "blas_threads": 1,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = run()
    if args.verify or RESULT.exists():
        old = json.loads(RESULT.read_bytes())
        if {k: v for k, v in old.items() if k != "resources"} != {
            k: v for k, v in result.items() if k != "resources"
        }:
            raise ValueError("replay differs")
        print("replay matched")
    else:
        write_atomic(
            RESULT, (json.dumps(result, indent=2, allow_nan=False) + "\n").encode()
        )
