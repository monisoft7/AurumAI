import numpy as np
import pandas as pd

def calculate_trend(prices: pd.Series) -> str:
    if len(prices) < 2:
        return "SIDEWAYS"
    x = np.arange(len(prices))
    y = prices.values if isinstance(prices, pd.Series) else prices
    slope = np.polyfit(x, y, 1)[0]
    if slope > 0:
        return "UP"
    elif slope < 0:
        return "DOWN"
    else:
        return "SIDEWAYS"

def calculate_return(before_price, after_price):

    if before_price == 0:
        return 0.0

    return ((after_price - before_price) / before_price) * 100

import numpy as np
import pandas as pd

def calculate_volatility(prices: pd.Series) -> float:
    if len(prices) < 2:
        return np.nan
    log_returns = np.log(prices / prices.shift(1)).dropna()
    if len(log_returns) == 0:
        return np.nan
    daily_vol = log_returns.std()
    annual_vol = daily_vol * np.sqrt(252)
    return annual_vol * 100.0