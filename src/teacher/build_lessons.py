from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from teacher.lesson_builder import LessonBuilder


def main() -> None:
    lessons = LessonBuilder().build_and_save()
    print(lessons.head())
    print()
    print("Lessons:", len(lessons))


if __name__ == "__main__":
    main()
