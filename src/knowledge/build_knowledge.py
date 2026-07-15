from pathlib import Path
import sys


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from knowledge.lesson_summary import LessonSummaryAggregator


def main() -> None:
    summary = LessonSummaryAggregator().build_save_and_ingest_memory()
    print("knowledge_version:", summary["knowledge_version"])
    print("record_count:", summary["record_count"])
    for record in summary["records"]:
        print(
            record["knowledge_id"],
            "samples=",
            record["sample_count"],
            "bias=",
            record["bias"],
            "confidence=",
            record["confidence"],
        )


if __name__ == "__main__":
    main()
