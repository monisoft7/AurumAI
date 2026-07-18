import pandas as pd

from knowledge.features.feature import Feature, FeatureSet
from knowledge.features.extractor import FeatureExtractor


class TechnicalIndicatorExtractor(FeatureExtractor):
    """Computes standard technical indicators on OHLCV price data.

    All calculations use pure pandas — no ``pandas-ta`` dependency
    (avoids the heavy ``numba`` transitive dependency).
    """

    @property
    def feature_definitions(self) -> dict[str, Feature]:
        return {
            "rsi_14": Feature(
                name="rsi_14",
                dtype="float64",
                description="Relative Strength Index (14-period)",
                source_columns=("close",),
            ),
            "macd": Feature(
                name="macd",
                dtype="float64",
                description="MACD line (12, 26)",
                source_columns=("close",),
            ),
            "macd_signal": Feature(
                name="macd_signal",
                dtype="float64",
                description="MACD signal line (9-period EMA of MACD)",
                source_columns=("close",),
            ),
            "macd_hist": Feature(
                name="macd_hist",
                dtype="float64",
                description="MACD histogram (MACD - signal)",
                source_columns=("close",),
            ),
            "ema_20": Feature(
                name="ema_20",
                dtype="float64",
                description="20-period Exponential Moving Average",
                source_columns=("close",),
            ),
            "ema_50": Feature(
                name="ema_50",
                dtype="float64",
                description="50-period Exponential Moving Average",
                source_columns=("close",),
            ),
            "ema_200": Feature(
                name="ema_200",
                dtype="float64",
                description="200-period Exponential Moving Average",
                source_columns=("close",),
            ),
            "sma_20": Feature(
                name="sma_20",
                dtype="float64",
                description="20-period Simple Moving Average",
                source_columns=("close",),
            ),
            "sma_50": Feature(
                name="sma_50",
                dtype="float64",
                description="50-period Simple Moving Average",
                source_columns=("close",),
            ),
            "sma_200": Feature(
                name="sma_200",
                dtype="float64",
                description="200-period Simple Moving Average",
                source_columns=("close",),
            ),
            "bb_upper": Feature(
                name="bb_upper",
                dtype="float64",
                description="Bollinger Band upper (20, 2)",
                source_columns=("close",),
            ),
            "bb_middle": Feature(
                name="bb_middle",
                dtype="float64",
                description="Bollinger Band middle (20-period SMA)",
                source_columns=("close",),
            ),
            "bb_lower": Feature(
                name="bb_lower",
                dtype="float64",
                description="Bollinger Band lower (20, 2)",
                source_columns=("close",),
            ),
        }

    def extract(self, raw: pd.DataFrame) -> FeatureSet:
        df = raw.copy()

        # RSI (14-period, Wilder's smoothing)
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / 14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        rsi = 100 - (100 / (1 + rs))
        rsi[(avg_gain > 0) & (avg_loss == 0)] = 100.0
        rsi[(avg_gain == 0) & (avg_loss > 0)] = 0.0
        rsi[(avg_gain == 0) & (avg_loss == 0)] = 50.0
        df["rsi_14"] = rsi

        # MACD (12, 26, 9)
        ema_12 = df["close"].ewm(span=12, adjust=False).mean()
        ema_26 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = ema_12 - ema_26
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        # EMAs
        df["ema_20"] = df["close"].ewm(span=20, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()

        # SMAs
        df["sma_20"] = df["close"].rolling(window=20).mean()
        df["sma_50"] = df["close"].rolling(window=50).mean()
        df["sma_200"] = df["close"].rolling(window=200).mean()

        # Bollinger Bands (20, 2)
        df["bb_middle"] = df["close"].rolling(window=20).mean()
        bb_std = df["close"].rolling(window=20).std(ddof=1)
        df["bb_upper"] = df["bb_middle"] + 2 * bb_std
        df["bb_lower"] = df["bb_middle"] - 2 * bb_std

        return FeatureSet(data=df, features=self.feature_definitions)
