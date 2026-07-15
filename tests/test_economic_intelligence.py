import json
from pathlib import Path

import pytest

from knowledge.economics.regime import (
    EconomicRegime,
    REGIME_HIGH_INFLATION,
    REGIME_LOW_INFLATION,
    REGIME_DEFLATION,
    REGIME_DISINFLATION,
    REGIME_TIGHT_MONETARY,
    REGIME_LOOSE_MONETARY,
    REGIME_RISK_ON,
    REGIME_RISK_OFF,
    REGIME_RECESSION,
    REGIME_EXPANSION,
    REGIME_STAGFLATION,
    VALID_REGIME_TYPES,
)
from knowledge.economics.state import EconomicState
from knowledge.economics.cycle import EconomicCycle
from knowledge.economics.classifier import EconomicClassifier
from knowledge.economics.repository import EconomicRepository


# ── EconomicRegime ───────────────────────────────────────────────────────────

def test_regime_creation() -> None:
    r = EconomicRegime(
        regime_id="reg_001",
        regime_type=REGIME_HIGH_INFLATION,
        label="High Inflation",
        description="CPI YoY above 3%",
        start_date="2021-03-01",
        confidence=0.85,
    )
    assert r.regime_id == "reg_001"
    assert r.regime_type == REGIME_HIGH_INFLATION
    assert r.label == "High Inflation"
    assert r.confidence == 0.85
    assert r.end_date is None


def test_regime_with_end_date() -> None:
    r = EconomicRegime(
        regime_id="reg_002",
        regime_type=REGIME_DEFLATION,
        label="Deflation",
        description="Negative CPI YoY",
        start_date="2020-01-01",
        end_date="2020-12-31",
        confidence=0.9,
    )
    assert r.end_date == "2020-12-31"


def test_regime_with_indicators() -> None:
    r = EconomicRegime(
        regime_id="reg_003",
        regime_type=REGIME_STAGFLATION,
        label="Stagflation",
        description="High inflation + low growth",
        start_date="2022-01-01",
        confidence=0.75,
        indicators={"inflation_cpi_yoy": 5.5, "gdp_growth": 0.5},
        metadata={"source": "BLS", "notes": "Preliminary"},
    )
    assert r.indicators["inflation_cpi_yoy"] == 5.5
    assert r.metadata["source"] == "BLS"


def test_valid_regime_types() -> None:
    expected = {
        REGIME_HIGH_INFLATION,
        REGIME_LOW_INFLATION,
        REGIME_DEFLATION,
        REGIME_DISINFLATION,
        REGIME_TIGHT_MONETARY,
        REGIME_LOOSE_MONETARY,
        REGIME_RISK_ON,
        REGIME_RISK_OFF,
        REGIME_RECESSION,
        REGIME_EXPANSION,
        REGIME_STAGFLATION,
    }
    assert VALID_REGIME_TYPES == expected


# ── EconomicState ────────────────────────────────────────────────────────────

def test_state_creation() -> None:
    s = EconomicState(
        state_id="st_001",
        date="2022-06-01",
        indicators={"inflation_cpi_yoy": 8.5, "gdp_growth": 1.8},
        regime_ids=("HIGH_INFLATION", "LOOSE_MONETARY"),
    )
    assert s.state_id == "st_001"
    assert s.date == "2022-06-01"
    assert s.indicators["inflation_cpi_yoy"] == 8.5
    assert len(s.regime_ids) == 2


def test_state_defaults() -> None:
    s = EconomicState(state_id="st_empty", date="2020-01-01")
    assert s.indicators == {}
    assert s.regime_ids == ()
    assert s.metadata == {}


# ── EconomicCycle ────────────────────────────────────────────────────────────

def test_cycle_creation() -> None:
    s1 = EconomicState(state_id="s1", date="2020-Q1", indicators={"gdp_growth": 2.5})
    s2 = EconomicState(state_id="s2", date="2020-Q2", indicators={"gdp_growth": -0.5})
    c = EconomicCycle(
        cycle_id="cyc_001",
        states=(s1, s2),
        start_date="2020-01-01",
        regime_ids=(REGIME_EXPANSION,),
    )
    assert c.cycle_id == "cyc_001"
    assert len(c.states) == 2
    assert c.regime_ids == (REGIME_EXPANSION,)


def test_cycle_with_transitions() -> None:
    c = EconomicCycle(
        cycle_id="cyc_002",
        states=(),
        start_date="2020-01-01",
        end_date="2020-12-31",
        regime_ids=(REGIME_EXPANSION, REGIME_RECESSION),
        transitions=(("2020-03-01", REGIME_RECESSION),),
    )
    assert c.end_date == "2020-12-31"
    assert len(c.transitions) == 1
    assert c.transitions[0] == ("2020-03-01", REGIME_RECESSION)


# ── EconomicClassifier: Point-in-time ────────────────────────────────────────

def test_classify_high_inflation() -> None:
    state = EconomicState(
        state_id="s1",
        date="2022-06-01",
        indicators={"inflation_cpi_yoy": 5.5},
    )
    regimes = EconomicClassifier().classify(state)
    assert REGIME_HIGH_INFLATION in regimes
    assert REGIME_LOW_INFLATION not in regimes
    assert REGIME_DEFLATION not in regimes


def test_classify_low_inflation() -> None:
    state = EconomicState(
        state_id="s2",
        date="2019-06-01",
        indicators={"inflation_cpi_yoy": 2.0},
    )
    regimes = EconomicClassifier().classify(state)
    assert REGIME_LOW_INFLATION in regimes
    assert REGIME_HIGH_INFLATION not in regimes
    assert REGIME_DEFLATION not in regimes


def test_classify_deflation() -> None:
    state = EconomicState(
        state_id="s3",
        date="2009-03-01",
        indicators={"inflation_cpi_yoy": -1.0},
    )
    regimes = EconomicClassifier().classify(state)
    assert REGIME_DEFLATION in regimes
    assert REGIME_HIGH_INFLATION not in regimes
    assert REGIME_LOW_INFLATION not in regimes


def test_classify_tight_monetary() -> None:
    state = EconomicState(
        state_id="s4",
        date="2023-07-01",
        indicators={"interest_rate": 5.5},
    )
    regimes = EconomicClassifier().classify(state)
    assert REGIME_TIGHT_MONETARY in regimes


def test_classify_loose_monetary() -> None:
    state = EconomicState(
        state_id="s5",
        date="2020-04-01",
        indicators={"interest_rate": 0.25},
    )
    regimes = EconomicClassifier().classify(state)
    assert REGIME_LOOSE_MONETARY in regimes


def test_classify_expansion() -> None:
    state = EconomicState(
        state_id="s6",
        date="2018-06-01",
        indicators={"gdp_growth": 3.5},
    )
    regimes = EconomicClassifier().classify(state)
    assert REGIME_EXPANSION in regimes


def test_classify_stagflation() -> None:
    state = EconomicState(
        state_id="s7",
        date="2022-06-01",
        indicators={"inflation_cpi_yoy": 5.5, "gdp_growth": 0.3},
    )
    regimes = EconomicClassifier().classify(state)
    assert REGIME_STAGFLATION in regimes
    assert REGIME_HIGH_INFLATION in regimes


def test_classify_risk_on_via_vix() -> None:
    state = EconomicState(
        state_id="s8",
        date="2017-06-01",
        indicators={"vix": 12.0},
    )
    regimes = EconomicClassifier().classify(state)
    assert REGIME_RISK_ON in regimes


def test_classify_risk_off_via_vix() -> None:
    state = EconomicState(
        state_id="s9",
        date="2008-10-01",
        indicators={"vix": 40.0},
    )
    regimes = EconomicClassifier().classify(state)
    assert REGIME_RISK_OFF in regimes


def test_classify_risk_on_via_sentiment() -> None:
    state = EconomicState(
        state_id="s10",
        date="2021-03-01",
        indicators={"consumer_sentiment": 90.0},
    )
    regimes = EconomicClassifier().classify(state)
    assert REGIME_RISK_ON in regimes


def test_classify_risk_off_via_sentiment() -> None:
    state = EconomicState(
        state_id="s11",
        date="2020-03-01",
        indicators={"consumer_sentiment": 50.0},
    )
    regimes = EconomicClassifier().classify(state)
    assert REGIME_RISK_OFF in regimes


def test_classify_empty_indicators() -> None:
    state = EconomicState(state_id="s_empty", date="2020-01-01")
    regimes = EconomicClassifier().classify(state)
    assert regimes == ()


def test_classify_partial_indicators() -> None:
    state = EconomicState(
        state_id="s_partial",
        date="2020-01-01",
        indicators={"inflation_cpi_yoy": 2.5},
    )
    regimes = EconomicClassifier().classify(state)
    assert REGIME_LOW_INFLATION in regimes
    assert REGIME_TIGHT_MONETARY not in regimes
    assert REGIME_LOOSE_MONETARY not in regimes
    assert REGIME_EXPANSION not in regimes


# ── EconomicClassifier: Sequence ─────────────────────────────────────────────

def test_classify_sequence_recession() -> None:
    states = [
        EconomicState(state_id="q1", date="2008-Q1", indicators={"gdp_growth": 2.0}),
        EconomicState(state_id="q2", date="2008-Q2", indicators={"gdp_growth": -0.5}),
        EconomicState(state_id="q3", date="2008-Q3", indicators={"gdp_growth": -1.5}),
        EconomicState(state_id="q4", date="2008-Q4", indicators={"gdp_growth": -2.0}),
    ]
    results = EconomicClassifier().classify_sequence(states)
    assert REGIME_RECESSION not in results[0]
    assert REGIME_RECESSION not in results[1]
    assert REGIME_RECESSION in results[2]
    assert REGIME_RECESSION in results[3]


def test_classify_sequence_disinflation() -> None:
    states = [
        EconomicState(state_id="m1", date="2022-06-01", indicators={"inflation_cpi_yoy": 8.5}),
        EconomicState(state_id="m2", date="2022-09-01", indicators={"inflation_cpi_yoy": 7.0}),
        EconomicState(state_id="m3", date="2022-12-01", indicators={"inflation_cpi_yoy": 6.0}),
    ]
    results = EconomicClassifier().classify_sequence(states)
    assert REGIME_DISINFLATION not in results[0]
    assert REGIME_DISINFLATION in results[1]
    assert REGIME_DISINFLATION in results[2]


def test_classify_sequence_single_state() -> None:
    states = [
        EconomicState(state_id="s1", date="2020-01-01", indicators={"gdp_growth": 2.0}),
    ]
    results = EconomicClassifier().classify_sequence(states)
    assert len(results) == 1
    assert REGIME_RECESSION not in results[0]
    assert REGIME_DISINFLATION not in results[0]


# ── EconomicClassifier: Custom config ────────────────────────────────────────

def test_classifier_custom_thresholds() -> None:
    config = {
        "inflation": {
            "indicator_key": "inflation_cpi_yoy",
            "high_threshold": 6.0,
            "low_positive_threshold": -0.5,
        },
    }
    classifier = EconomicClassifier(config)

    state_high = EconomicState(
        state_id="s_high",
        date="2022-06-01",
        indicators={"inflation_cpi_yoy": 4.5},
    )
    regimes_high = classifier.classify(state_high)
    assert REGIME_HIGH_INFLATION not in regimes_high
    assert REGIME_LOW_INFLATION in regimes_high

    state_deflation = EconomicState(
        state_id="s_def",
        date="2009-01-01",
        indicators={"inflation_cpi_yoy": 0.2},
    )
    regimes_def = classifier.classify(state_deflation)
    assert REGIME_DEFLATION not in regimes_def
    assert REGIME_LOW_INFLATION in regimes_def


# ── EconomicClassifier: Config property ──────────────────────────────────────

def test_classifier_default_config() -> None:
    classifier = EconomicClassifier()
    cfg = classifier.config
    assert "inflation" in cfg
    assert cfg["inflation"]["high_threshold"] == 3.0
    assert cfg["monetary"]["neutral_rate"] == 2.5


# ── EconomicEvidenceAdapter ──────────────────────────────────────────────────

def test_adapter_regime_to_evidence() -> None:
    regime = EconomicRegime(
        regime_id="reg_ev",
        regime_type=REGIME_HIGH_INFLATION,
        label="High Inflation Period",
        description="CPI YoY sustained above 5%",
        start_date="2021-06-01",
        end_date="2022-12-01",
        confidence=0.88,
        indicators={"inflation_cpi_yoy": 6.2},
    )
    from knowledge.economics.adapter import EconomicEvidenceAdapter
    ev = EconomicEvidenceAdapter().regime_to_evidence(regime)
    assert ev.evidence_id == "econ_reg_ev"
    assert ev.event_type == "ECONOMIC"
    assert ev.condition == {"regime": REGIME_HIGH_INFLATION}
    assert ev.confidence == 0.88
    assert "High Inflation Period" in ev.explanation
    assert ev.metadata["regime_type"] == REGIME_HIGH_INFLATION


def test_adapter_regimes_at_date() -> None:
    states = [
        EconomicState(
            state_id="st1",
            date="2022-06-01",
            regime_ids=(REGIME_HIGH_INFLATION, REGIME_TIGHT_MONETARY),
        ),
        EconomicState(
            state_id="st2",
            date="2022-07-01",
            regime_ids=(REGIME_HIGH_INFLATION,),
        ),
    ]
    from knowledge.economics.adapter import EconomicEvidenceAdapter
    regimes = EconomicEvidenceAdapter().regimes_at_date("2022-06-01", states)
    types = {r.regime_type for r in regimes}
    assert REGIME_HIGH_INFLATION in types
    assert REGIME_TIGHT_MONETARY in types
    assert len(regimes) == 2


def test_adapter_regimes_at_date_no_match() -> None:
    from knowledge.economics.adapter import EconomicEvidenceAdapter
    regimes = EconomicEvidenceAdapter().regimes_at_date("2020-01-01", [])
    assert regimes == []


def test_adapter_nearest_state() -> None:
    states = [
        EconomicState(state_id="s1", date="2022-01-15", indicators={}),
        EconomicState(state_id="s2", date="2022-06-15", indicators={}),
    ]
    from knowledge.economics.adapter import EconomicEvidenceAdapter
    nearest = EconomicEvidenceAdapter().nearest_state("2022-06-01", states)
    assert nearest is not None
    assert nearest.state_id == "s2"


def test_adapter_nearest_state_empty() -> None:
    from knowledge.economics.adapter import EconomicEvidenceAdapter
    assert EconomicEvidenceAdapter().nearest_state("2022-06-01", []) is None


# ── EconomicRepository: Regime ───────────────────────────────────────────────

def test_repository_save_and_load_regime(tmp_path: Path) -> None:
    regime = EconomicRegime(
        regime_id="reg_save",
        regime_type=REGIME_RECESSION,
        label="Great Recession",
        description="Global financial crisis recession",
        start_date="2007-12-01",
        end_date="2009-06-01",
        confidence=0.95,
        indicators={"gdp_growth": -3.0},
        metadata={"source": "NBER"},
    )
    path = tmp_path / "regime.json"
    EconomicRepository().save_regime(regime, path)
    assert path.exists()

    loaded = EconomicRepository().load_regime(path)
    assert loaded.regime_id == "reg_save"
    assert loaded.regime_type == REGIME_RECESSION
    assert loaded.end_date == "2009-06-01"
    assert loaded.confidence == 0.95
    assert loaded.metadata["source"] == "NBER"


def test_repository_regime_roundtrip_preserves_all_fields(tmp_path: Path) -> None:
    original = EconomicRegime(
        regime_id="reg_rt",
        regime_type=REGIME_EXPANSION,
        label="Expansion",
        description="Economic expansion period",
        start_date="2010-01-01",
        confidence=0.8,
        indicators={"gdp_growth": 3.2, "unemployment": 5.0},
        metadata={"analyst": "test"},
    )
    path = tmp_path / "regime_rt.json"
    EconomicRepository().save_regime(original, path)
    loaded = EconomicRepository().load_regime(path)
    assert loaded.regime_id == original.regime_id
    assert loaded.regime_type == original.regime_type
    assert loaded.label == original.label
    assert loaded.description == original.description
    assert loaded.start_date == original.start_date
    assert loaded.end_date == original.end_date
    assert loaded.confidence == original.confidence
    assert loaded.indicators == original.indicators
    assert loaded.metadata == original.metadata


# ── EconomicRepository: State ────────────────────────────────────────────────

def test_repository_save_and_load_state(tmp_path: Path) -> None:
    state = EconomicState(
        state_id="st_save",
        date="2022-06-01",
        indicators={"inflation_cpi_yoy": 8.5, "gdp_growth": 1.8},
        regime_ids=(REGIME_HIGH_INFLATION, REGIME_LOOSE_MONETARY),
        metadata={"source": "BLS"},
    )
    path = tmp_path / "state.json"
    EconomicRepository().save_state(state, path)
    assert path.exists()

    loaded = EconomicRepository().load_state(path)
    assert loaded.state_id == "st_save"
    assert loaded.date == "2022-06-01"
    assert loaded.indicators["inflation_cpi_yoy"] == 8.5
    assert REGIME_HIGH_INFLATION in loaded.regime_ids
    assert loaded.metadata["source"] == "BLS"


# ── EconomicRepository: Cycle ────────────────────────────────────────────────

def test_repository_save_and_load_cycle(tmp_path: Path) -> None:
    s1 = EconomicState(state_id="s1", date="2020-Q1", indicators={"gdp_growth": 2.5})
    s2 = EconomicState(state_id="s2", date="2020-Q2", indicators={"gdp_growth": -0.5})
    cycle = EconomicCycle(
        cycle_id="cyc_save",
        states=(s1, s2),
        start_date="2020-01-01",
        end_date="2020-06-30",
        regime_ids=(REGIME_EXPANSION, REGIME_RECESSION),
        transitions=(("2020-04-01", REGIME_RECESSION),),
    )
    path = tmp_path / "cycle.json"
    EconomicRepository().save_cycle(cycle, path)
    assert path.exists()

    loaded = EconomicRepository().load_cycle(path)
    assert loaded.cycle_id == "cyc_save"
    assert len(loaded.states) == 2
    assert loaded.states[0].state_id == "s1"
    assert loaded.states[1].indicators["gdp_growth"] == -0.5
    assert loaded.regime_ids == (REGIME_EXPANSION, REGIME_RECESSION)
    assert len(loaded.transitions) == 1
    assert loaded.transitions[0][0] == "2020-04-01"


# ── EconomicRepository: Empty cycle ──────────────────────────────────────────

def test_repository_empty_cycle(tmp_path: Path) -> None:
    cycle = EconomicCycle(
        cycle_id="cyc_empty",
        states=(),
        start_date="2020-01-01",
    )
    path = tmp_path / "cycle_empty.json"
    EconomicRepository().save_cycle(cycle, path)
    loaded = EconomicRepository().load_cycle(path)
    assert loaded.cycle_id == "cyc_empty"
    assert loaded.states == ()
    assert loaded.end_date is None
