"""Freeze and audit the registered Phase 4 gold-risk model, excluding 2025."""

import argparse
import hashlib
import json

import numpy as np
import pandas as pd
from scipy.special import expit
from threadpoolctl import threadpool_limits

from .data import write_atomic
from .predictive import gold_features, logistic_weights
from .predictive_data import HERE, MANIFEST, YEARS, load

PROTOCOL = HERE / "radar_protocol.json"
FROZEN = HERE / "radar_model.json"
AUDIT = HERE / "radar_audit.json"
FEATURES = ("r1", "r4", "r16", "v4", "v16", "range", "sin", "cos")
REFERENCES = (
    "seasonal",
    "previous_volatility",
    "threshold_distance",
    "threshold_and_hour",
)
STRENGTH = 0.001


def text_hash(path):
    return hashlib.sha256(path.read_text(encoding="utf8").encode()).hexdigest()


def design(features, distance):
    log_d = np.log(distance.clip(lower=1e-8))
    hour = np.eye(24)[features.index.hour]
    return {
        "model": features.loc[:, list(FEATURES)].to_numpy(),
        "previous_volatility": np.log(features[["v4"]].clip(lower=1e-8)).to_numpy(),
        "threshold_distance": log_d.to_numpy().reshape(-1, 1),
        "threshold_and_hour": np.column_stack((log_d, hour)),
    }


def fit(a, y):
    center = a.mean(axis=0)
    scale = a.std(axis=0)
    scale[scale < 1e-10] = 1.0
    design = np.column_stack((np.ones(len(a)), (a - center) / scale))
    penalty = np.r_[0.0, np.full(a.shape[1], STRENGTH)]
    weights = logistic_weights(design, y.to_numpy(), penalty)
    return {
        "center": center.tolist(),
        "scale": scale.tolist(),
        "weights": weights.tolist(),
    }


def fitted(a, spec):
    return expit(
        spec["weights"][0]
        + ((a - spec["center"]) / spec["scale"]) @ spec["weights"][1:]
    )


def train(features, distance, truth):
    spec = {k: fit(a, truth) for k, a in design(features, distance).items()}
    spec["seasonal"] = {
        str(k): v for k, v in truth.groupby(truth.index.hour).mean().items()
    }
    spec["incidence"] = float(truth.mean())
    return spec


def predict(spec, features, distance):
    out = {k: fitted(a, spec[k]) for k, a in design(features, distance).items()}
    out["seasonal"] = np.array(
        [spec["seasonal"].get(str(h), spec["incidence"]) for h in features.index.hour]
    )
    return out


def bootstrap(series, comparisons):
    daily = series.groupby(series.index.normalize()).mean().to_numpy()
    n = len(daily)
    rng = np.random.default_rng(1951)
    start = rng.integers(0, n, (10000, (n + 4) // 5))
    ix = ((start[:, :, None] + np.arange(5)) % n).reshape(10000, -1)[:, :n]
    samples = daily[ix].mean(axis=1)
    return {
        "mean": float(daily.mean()),
        "ci95": np.quantile(samples, [0.025, 0.975]).tolist(),
        "lower_corrected": float(np.quantile(samples, 0.05 / comparisons)),
    }


def history():
    manifest = json.loads(MANIFEST.read_bytes())
    data = pd.concat([load("XAUUSD", year, manifest) for year in YEARS]).sort_index()
    close, r, features = gold_features(data)
    end = close.shift(-4)
    ret = (1e4 * np.log(end / close)).abs()
    enough = r.rolling(4).count().shift(-4) == 4
    clock = close.index
    minutes = clock.hour * 60 + clock.minute
    use = (
        (clock.weekday < 5)
        & (minutes >= 420)
        & (minutes <= 1260)
        & enough
        & features.notna().all(axis=1)
    )
    x = features.loc[use]
    relative = 1.5 * x.v4
    sample = {
        "relative": (
            close.loc[use] * np.expm1(relative / 1e4),
            ret.loc[use] > relative,
        ),
        "fixed_5_usd": (
            pd.Series(5.0, index=x.index),
            (end - close).loc[use].abs() > 5,
        ),
        "fixed_25_bps": (close.loc[use] * np.expm1(0.0025), ret.loc[use] > 25),
    }
    return manifest, x, sample


def run():
    manifest, features, sample = history()
    results = {}
    quarters = pd.date_range("2024-01-01", "2024-10-01", freq="QS", tz="UTC")
    day = pd.Timedelta(days=1)
    with threadpool_limits(limits=1):
        for name, (distance, truth) in sample.items():
            outputs = []
            folds = []
            for start in quarters:
                stop = start + pd.DateOffset(months=3)
                fit_rows = features.index < start - day
                test_rows = (features.index >= start) & (features.index < stop - day)
                spec = train(
                    features.loc[fit_rows], distance.loc[fit_rows], truth.loc[fit_rows]
                )
                out = predict(spec, features.loc[test_rows], distance.loc[test_rows])
                losses = pd.DataFrame(
                    {
                        k: (p - truth.loc[test_rows].to_numpy()) ** 2
                        for k, p in out.items()
                    },
                    index=features.loc[test_rows].index,
                )
                outputs.append(losses)
                folds.append(
                    {
                        "quarter": str(start.date()),
                        "n": len(losses),
                        "incidence": float(truth.loc[test_rows].mean()),
                        "brier": losses.mean().to_dict(),
                    }
                )
            combined = pd.concat(outputs)
            results[name] = {
                "n": len(combined),
                "days": combined.index.normalize().nunique(),
                "brier": combined.mean().to_dict(),
                "folds": folds,
                "paired_gain": {
                    k: bootstrap(combined[k] - combined.model, 12) for k in REFERENCES
                },
            }
        distance, truth = sample["relative"]
        final = features.index < pd.Timestamp("2024-12-31", tz="UTC")
        spec = train(features.loc[final], distance.loc[final], truth.loc[final])
        spec["mean_prediction"] = float(
            predict(spec, features.loc[final], distance.loc[final])["model"].mean()
        )
    protocol_id = text_hash(PROTOCOL)
    model = {
        "version": "aurum-risk-v1",
        "protocol_sha256": protocol_id,
        "feature_code_sha256": text_hash(HERE / "predictive.py"),
        "training_code_sha256": text_hash(HERE / "radar_model.py"),
        "manifest_sha256": text_hash(MANIFEST),
        "inputs": {
            str(y): manifest["assets"]["XAUUSD"][str(y)]["sha256"] for y in YEARS
        },
        "cutoff_exclusive": "2024-12-31T00:00:00Z",
        "features": FEATURES,
        "strength": STRENGTH,
        "fitted_rows": int(final.sum()),
        "first": features.loc[final].index[0].isoformat(),
        "last": features.loc[final].index[-1].isoformat(),
        "parameters": spec,
        "versions": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": __import__("scipy").__version__,
        },
    }
    return model, {"protocol_sha256": protocol_id, "results": results}


def load_frozen():
    artifact = json.loads(FROZEN.read_bytes())
    for key, path in [
        ("protocol", PROTOCOL),
        ("feature_code", HERE / "predictive.py"),
        ("training_code", HERE / "radar_model.py"),
        ("manifest", MANIFEST),
    ]:
        if artifact[key + "_sha256"] != text_hash(path):
            raise ValueError("frozen model input changed: " + key)
    return artifact, text_hash(FROZEN)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    for path, value in zip((FROZEN, AUDIT), run()):
        content = json.dumps(value, indent=2, allow_nan=False) + "\n"
        if args.verify or path.exists():
            if path.read_text(encoding="utf8") != content:
                raise ValueError("replay differs: " + path.name)
        else:
            write_atomic(path, content.encode())
        print(path.name, "verified" if args.verify else "frozen", flush=True)
