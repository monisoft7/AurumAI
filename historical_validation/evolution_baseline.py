"""Reduce the pinned consecutive Actions artifacts; exclude old runs bundled in each ZIP."""
import argparse
import hashlib
import json
from pathlib import Path


RUNS = {
    "43253520258": "2026-11-12", "43452178743": "2026-11-13",
    "43913875674": "2026-11-16", "44130755897": "2026-11-17",
    "44347453703": "2026-11-18", "44567456431": "2026-11-19",
    "44770434959": "2026-11-20", "45246798716": "2026-11-23",
}


def extract(directory):
    def read(name):
        return json.loads((directory / name).read_bytes())

    summary = read("daily_operational_summary.json")
    status = read("summary.json")
    stages = read("stage_outputs.json")["outputs"]
    legacy = stages["build_legacy_pipeline"]
    records = {r["knowledge_id"] for r in read("artifacts/knowledge.json")["records"]}
    parents = {r["target_id"] for r in legacy["lineage_registry"]["_records"]
               if r["source_type"] == "lesson" and r["target_type"] == "knowledge_record"}
    items = stages["evidence_collection"]["items"]
    links = [i["metadata"].get("knowledge_record_id") for i in items]
    return {
        "run": summary["run_id"], "issued": status["timestamp"], "commit": summary["provenance"]["git_commit"],
        "action": status["decision"], "research": status["research_decision"],
        "reasons": status["execution_decision"]["reasons"], "score": status["decision_confidence"],
        "regime": summary["regime"], "ref_price": summary["risk"]["reference_price"],
        "bar": summary["risk"]["price_bar_date"], "source": summary["risk"]["price_source"],
        "legacy_retrieved": len(legacy["evidence"]["_items"]),
        "institutional_items": len(items), "links_with_lessons": sum(k in records & parents for k in links),
        "unresolved_claims": sum(k is not None and k not in records & parents for k in links),
        "news": summary["news"], "calibration": summary["calibration"], "outcome": summary["outcome"],
        "summary_sha256": hashlib.sha256((directory / "summary.json").read_bytes()).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("downloads", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = {}
    for run, day in RUNS.items():
        directory, = (args.downloads / run / "outputs" / day).glob("runtime_*")
        rows[run] = extract(directory)
    args.output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
