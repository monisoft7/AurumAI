from database.models import DataRecord
from datetime import datetime


class DataHub:

    def __init__(self):
        self._storage = {}

    def save(self, source, symbol, data):

        self._storage[source] = DataRecord(
            source=source,
            symbol=symbol,
            timestamp=datetime.utcnow(),
            data=data,
        )

    def get(self, source):

        return self._storage.get(source)

    def list_sources(self):

        return list(self._storage.keys())