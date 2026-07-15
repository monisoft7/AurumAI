from fredapi import Fred
from core.config import settings



class FredCollector:

    def __init__(self):

        self.fred = Fred(api_key=settings.FRED_API_KEY)

    def get_series(self, series):

        return self.fred.get_series(series)


if __name__ == "__main__":

    collector = FredCollector()

    data = collector.get_series("FEDFUNDS")

    print(data.tail())