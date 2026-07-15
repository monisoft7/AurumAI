from pathlib import Path
import pandas as pd

from src.knowledge.models.lesson import Lesson


class LessonRepository:

    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)

    def load_dataframe(self):

        return pd.read_csv(self.csv_path)

    def count(self):

        return len(self.load_dataframe())