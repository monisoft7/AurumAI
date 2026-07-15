import pandas as pd


def find_nearest_trading_day(gold_dataframe, target_date):

    target = pd.Timestamp(target_date)

    if "Date" in gold_dataframe.columns:
        df = gold_dataframe.copy()
        df["Date"] = pd.to_datetime(df["Date"])
        rows = df[df["Date"] <= target]

        if rows.empty:
            return None

        return rows.iloc[-1]

    raise ValueError("Date column not found.")