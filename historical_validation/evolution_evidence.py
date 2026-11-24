"""Replay only the repaired CPI and evidence boundaries against archived inputs."""
import argparse
import json
import sys
from collections import Counter
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from historical_validation.evolution_baseline import RUNS
from knowledge.events.release_calendar import ReleaseCalendar
from knowledge.graph.builder import GraphBuilder
from evidence_collection.collector import EvidenceCollector
from pre_market.contracts import PreMarketBriefing
from signal_assessment.assembler import SignalAssessmentAssembler
from signal_assessment.contracts import SignalAssessment


def duplicates(ids):
    return sum(n-1 for n in Counter(ids).values() if n > 1)


def audit(downloads):
    dates = ReleaseCalendar.from_csv(ROOT / "data/calendar/cpi_releases_bls_verified.csv")
    rows = []
    for run, day in RUNS.items():
        directory, = (downloads / run / "outputs" / day).glob("runtime_*")
        stages = json.loads((directory / "stage_outputs.json").read_bytes())["outputs"]
        briefing = PreMarketBriefing.from_dict(stages["pre_market_scan"])
        snapshot = dict(briefing.metadata["cpi_release"])
        release = dates.get(snapshot["reference_period"])
        if release:
            timestamp = datetime.fromisoformat(f"{release.release_date}T{release.release_time}")
            snapshot["published_at"] = timestamp.replace(tzinfo=ZoneInfo(release.timezone)).isoformat()
        briefing = replace(briefing, metadata=dict(briefing.metadata, cpi_release=snapshot))
        repaired = SignalAssessmentAssembler(regime=briefing.regime).assemble(briefing)
        old = SignalAssessment.from_dict(stages["signal_assessment"])
        graph = GraphBuilder().build(json.loads((directory / "artifacts/knowledge.json").read_bytes())["records"])
        # Keep the original W5 observations to isolate the ID repair.
        condition = stages["build_legacy_pipeline"]["reasoning_condition"]
        new = EvidenceCollector(graph).collect(old, cpi_condition=condition)
        previous = stages["evidence_collection"]["items"]
        rows.append({"run": run, "release": snapshot.get("published_at"),
                     "old_event_signals": sum(o.source == "cpi_release" for o in old.observations),
                     "new_event_signals": sum(o.source == "cpi_release" for o in repaired.observations),
                     "old_id_collisions": duplicates(i["evidence_id"] for i in previous if i["source_label"] != "technical_research_desk"),
                     "new_id_collisions": duplicates(i.evidence_id for i in new.items)})
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("downloads", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.downloads), indent=2))
