"""Integration test: verify all 3 blocking items are resolved."""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timezone

# Blocking Item 3: W2 detectors return RegimeDiagnosis (not ad-hoc dicts)
from knowledge.regime.contracts import RegimeDiagnosis
from knowledge.regime.institutional_regime_detector import InstitutionalRegimeDetector


def test_blocking_item_3_regime_diagnosis_contract():
    detector = InstitutionalRegimeDetector()

    # diagnose() returns RegimeDiagnosis
    diag = detector.diagnose(composite_score=1.2, gpr_value=0.0, gram_residual_value=0.0)
    assert isinstance(diag, RegimeDiagnosis)
    errors = diag.validate()
    assert not errors, f"validate errors: {errors}"
    assert 0.0 <= diag.confidence <= 1.0
    assert diag.regime == "NORMAL_GROWTH"
    assert not diag.in_transition

    # get_diagnosis() also returns RegimeDiagnosis
    diag2 = detector.get_diagnosis()
    assert isinstance(diag2, RegimeDiagnosis)
    assert diag2.regime == diag.regime

    # fit() path: backward compat
    dates = pd.date_range("2020-01-01", periods=60, freq="ME")
    composite = pd.DataFrame({
        "Date": dates,
        "composite_score": np.sin(np.linspace(0, 4 * np.pi, 60)),
    })
    detector.fit(composite)
    current = detector.get_current_regime()
    assert "regime" in current
    assert "confidence" in current
    assert "in_transition" in current

    diag3 = detector.get_diagnosis()
    assert isinstance(diag3, RegimeDiagnosis)
    assert diag3.regime == current["regime"]


# Blocking Item 2: dynamic regime-to-KR lookup via graph
from knowledge.graph.graph import KnowledgeGraph
from knowledge.graph.node import GraphNode
from knowledge.regime.indicator_hierarchy import IndicatorHierarchyGenerator


def test_blocking_item_2_dynamic_kr_lookup():
    kg = KnowledgeGraph()
    for i, regime in enumerate([
        "NORMAL_GROWTH", "INFLATIONARY", "STAGFLATIONARY",
        "DEFLATIONARY_CRISIS", "GEOPOLITICAL_STRESS", "STRUCTURAL_REGIME_CHANGE",
    ]):
        kg.add_node(GraphNode(
            node_id=f"KR_{i}",
            node_type="knowledge_record",
            properties={"title": f"{regime} record", "regimes": [regime]},
        ))

    generator = IndicatorHierarchyGenerator()
    result = generator.generate("NORMAL_GROWTH", graph=kg)
    assert isinstance(result, dict)
    assert result["regime"] == "NORMAL_GROWTH"
    assert len(result["indicators"]) > 0
    assert len(result["associated_krs"]) > 0
    assert "KR_" in result["associated_krs"][0]

    result2 = generator.generate("INFLATIONARY", graph=kg)
    assert len(result2["associated_krs"]) > 0


# Blocking Item 1: canonical regime codes from shared constants
from knowledge.regime.constants import (
    NORMAL_GROWTH,
    INSTITUTIONAL_REGIMES,
    CANONICAL_REGIME_SET,
    DEFAULT_GPR_THRESHOLD,
    DEFAULT_GRAM_RESIDUAL_THRESHOLD,
    DEFAULT_TRANSITION_THRESHOLD,
)
from knowledge.regime.regime_transition import RegimeTransitionDetector


def test_blocking_item_1_shared_constants():
    assert len(INSTITUTIONAL_REGIMES) == 6
    assert NORMAL_GROWTH in CANONICAL_REGIME_SET
    assert DEFAULT_GPR_THRESHOLD == 150.0
    assert DEFAULT_GRAM_RESIDUAL_THRESHOLD == 2.0
    assert DEFAULT_TRANSITION_THRESHOLD == 0.5


def test_regression_regime_transition_uses_constants():
    rtd = RegimeTransitionDetector()
    labels = pd.Series(
        ["NORMAL_GROWTH", "INFLATIONARY", "STAGFLATIONARY"],
        index=pd.date_range("2020-01-01", periods=3),
    )
    pdf = rtd.detect(labels)
    assert len(pdf) == 3
    assert "transition_type" in pdf.columns
