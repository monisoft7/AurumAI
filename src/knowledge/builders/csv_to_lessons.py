import pandas as pd

from src.knowledge.models.lesson import Lesson


def dataframe_to_lessons(df: pd.DataFrame):

    lessons = []

    for _, row in df.iterrows():

        lesson = Lesson(

            event_id=str(row.get("event_id", "")),
            event_type=row.get("event_type", ""),

            event_date=pd.to_datetime(row.get("event_date")),

            event_value=row.get("event_value", 0),

            event_surprise=row.get("event_surprise"),

            gold_before=row.get("gold_before", 0),

            gold_1d=row.get("gold_1d", 0),

            gold_3d=row.get("gold_3d", 0),

            gold_7d=row.get("gold_7d", 0),

            gold_30d=row.get("gold_30d", 0),

            return_1d=row.get("return_1d", 0),

            return_3d=row.get("return_3d", 0),

            return_7d=row.get("return_7d", 0),

            return_30d=row.get("return_30d", 0),

            trend=row.get("trend", ""),

            volatility=row.get("volatility", 0),

            source=row.get("source", ""),

            confidence=row.get("confidence", 1.0),

        )

        lessons.append(lesson)

    return lessons