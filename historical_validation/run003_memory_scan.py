"""Run-003 supplementary memory scan -- per-case memory-desk reading.

For every canonical case, rebuilds the as-of analogue payload and existing
adjudication (Correction-028 machinery, strictly pre-D corpus) and records
the bounded HISTORICAL_MEMORY evidence reading (bias + transfer confidence)
that the repaired W6 injects.  Read-only; provenance-preserving.

Output: historical_validation/run003/memory_bias_scan.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
SRC = _ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from evidence_collection.desk_evidence import build_memory_evidence  # noqa: E402
from evidence_reasoning.historical_adjudication import (  # noqa: E402
    build_historical_adjudication,
)

RUN003_DIR = Path(__file__).resolve().parent / "run003"


def main() -> None:
    from historical_validation.baseline_manifest_loader import load_manifest_cohort
    from historical_validation.enriched_path import build_enriched_analogue_payload
    from historical_validation.run003_driver import _build_cases, _verify_inputs
    from historical_validation.snapshot import SnapshotConfig, build_snapshot

    manifest = json.loads(
        (_ROOT / "historical_validation" / "baseline_manifest_run003.json").read_text(
            encoding="utf-8"
        )
    )
    _verify_inputs(manifest)
    cases = _build_cases(manifest)
    cfg = SnapshotConfig()

    rows = []
    bias_counts: Counter[str] = Counter()
    confidences: list[float] = []
    for idx, case in enumerate(cases, 1):
        snap = build_snapshot(case, cfg)
        payload, info = build_enriched_analogue_payload(snap)
        adjudication = (
            build_historical_adjudication(payload) if payload else None
        )
        item = build_memory_evidence(adjudication, payload)
        entry = {
            "lesson_id": case.lesson_id,
            "evaluation_date": case.evaluation_date.isoformat(),
            "match_ids": list(info.get("match_ids") or []),
            "memory_bias": item.bias if item is not None else None,
            "memory_base_confidence": (
                item.base_confidence if item is not None else None
            ),
            "adjudication_present": adjudication is not None,
        }
        rows.append(entry)
        if item is not None:
            bias_counts[item.bias] += 1
            if item.base_confidence is not None:
                confidences.append(float(item.base_confidence))
        if idx % 20 == 0 or idx == len(cases):
            print(f"scanned {idx}/{len(cases)}", flush=True)

    directional = bias_counts.get("bullish", 0) + bias_counts.get("bearish", 0)
    out = {
        "cases": len(rows),
        "bias_counts": dict(bias_counts),
        "directional": directional,
        "uninformative": bias_counts.get("neutral", 0),
        "mean_base_confidence": (
            round(sum(confidences) / len(confidences), 6) if confidences else None
        ),
        "rows": rows,
    }
    out_path = RUN003_DIR / "memory_bias_scan.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(
        f"memory scan -> {out_path}: directional={directional} "
        f"uninformative={bias_counts.get('neutral', 0)}"
    )


if __name__ == "__main__":
    main()
