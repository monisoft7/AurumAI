import yfinance as yf

from database.hub import DataHub


class YahooCollector:

    def __init__(self):
        self.hub = DataHub()

    def gold(self):

        df = yf.download(
            "GC=F",
            period="1mo",
            interval="1h",
            auto_adjust=True,
        )

        self.hub.save(
            source="Yahoo",
            symbol="XAUUSD",
            data=df,
        )

        return self.hub.get("Yahoo")


if __name__ == "__main__":

    c = YahooCollector()

    gold = c.gold()

    print(gold.source)
    print(gold.symbol)
    print(gold.timestamp)
    print(gold.data.tail())