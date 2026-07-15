from abc import ABC, abstractmethod


class BaseCollector(ABC):

    @abstractmethod
    def connect(self):
        pass

    @abstractmethod
    def collect(self):
        pass

    @abstractmethod
    def validate(self, data):
        pass

    @abstractmethod
    def save(self, data):
        pass
