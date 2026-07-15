from pathlib import Path
import json
import shutil

from knowledge.brain import EconomicBrain
from knowledge.memory import Memory


def runtime_dir(name: str) -> Path:
    path = Path(__file__).resolve().parent / "_runtime" / name
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def write_memory(path: Path) -> None:
    payload = {
        "cpi_gold_summary_v1": {
            "records": [
                {
                    "knowledge_id": "CPI_GOLD_inflation_pressure_up_20D",
                    "condition": {"cpi_pressure": "inflation_pressure_up"},
                    "horizon_days": 20,
                    "sample_count": 113,
                    "bias": "mixed_or_context_dependent",
                    "confidence": 0.538963,
                    "positive_return_rate_pct": 52.212389,
                    "average_return_pct": 0.642207,
                    "explanation": "Evidence-backed CPI/gold knowledge.",
                }
            ]
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_brain_returns_evidence_backed_market_understanding() -> None:
    base_path = runtime_dir("brain")
    memory_path = base_path / "memory.json"
    write_memory(memory_path)
    brain = EconomicBrain(Memory(memory_path))

    result = brain.analyze(
        "CPI",
        {
            "cpi_pressure": "inflation_pressure_up",
            "horizon_days": 20,
        },
    )

    assert result["status"] == "knowledge_found"
    assert result["knowledge_id"] == "CPI_GOLD_inflation_pressure_up_20D"
    assert result["sample_count"] == 113
    assert result["bias"] == "mixed_or_context_dependent"
    assert result["confidence"] == 0.538963
    assert "BUY" not in str(result)
    assert "SELL" not in str(result)


def test_brain_reports_missing_context_without_guessing() -> None:
    brain = EconomicBrain(Memory(runtime_dir("missing_context") / "memory.json"))

    result = brain.analyze("CPI", {})

    assert result == {"gold": "Usually Bullish", "usd": "Usually Bearish"}

    result = brain.analyze("CPI", {"horizon_days": 20})

    assert result["status"] == "missing_context"
    assert result["missing"] == ["cpi_pressure"]
