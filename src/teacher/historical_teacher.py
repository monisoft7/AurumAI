import yfinance as yf
from pathlib import Path


class HistoricalTeacher:

    def download_gold(self):

        df = yf.download(
            "GC=F",
            start="2015-01-01",
            end="2026-01-01",
            auto_adjust=True,
            progress=False,
        )

        # إزالة MultiIndex إذا وجد
        if hasattr(df.columns, "droplevel"):
            try:
                df.columns = df.columns.droplevel(1)
            except Exception:
                pass

        df = df.reset_index()

        Path("data/history/gold").mkdir(parents=True, exist_ok=True)

        df.to_csv(
            "data/history/gold/gold.csv",
            index=False
        )

        print(df.head())


if __name__ == "__main__":
    HistoricalTeacher().download_gold()