from __future__ import annotations

import re
import math
from datetime import datetime, timezone
from typing import Any

from pre_market.contracts import AnomalyFlag, NewsItem, PreMarketBriefing
from signal_assessment.breadth import BreadthChecker
from signal_assessment.classifier import NoiseSignalClassifier
from signal_assessment.contracts import ClassifiedObservation, CriterionScore, SignalAssessment
from signal_assessment.narrative import NarrativeFitScorer
from signal_assessment.persistence import PersistenceTracker
from signal_assessment.volume import ETF_FLOW_THRESHOLD_PCT, VolumeFlowConfirmator


PERSISTENCE_TYPE_BY_INSTRUMENT = {
    "XAU/USD": "COMEX",
    "XAUUSD": "COMEX",
    "GC=F": "COMEX",
    "DXY": "DXY",
    "DX-Y.NYB": "DXY",
    "US10Y Real Yield": "gold_real_yield",
    "US10Y Nominal Yield": "gold_real_yield",
    "Breakeven Inflation": "gold_real_yield",
}

GOLD_CLASS_INSTRUMENTS = frozenset(
    instrument
    for instrument, instrument_type in PERSISTENCE_TYPE_BY_INSTRUMENT.items()
    if instrument_type == "COMEX"
)


class SignalAssessmentAssembler:
    """Transforms a W3 PreMarketBriefing into a W5 SignalAssessment.

    Classifies every observation (overnight price changes, anomaly flags,
    news items, positioning data) using the Meth. §7 five-criteria system.
    """

    def __init__(
        self,
        regime: str = "",
        persistence_tracker: PersistenceTracker | None = None,
        breadth_checker: BreadthChecker | None = None,
        narrative_scorer: NarrativeFitScorer | None = None,
        volume_confirmator: VolumeFlowConfirmator | None = None,
        classifier: NoiseSignalClassifier | None = None,
    ) -> None:
        self._regime = regime
        self._persistence = persistence_tracker or PersistenceTracker()
        self._breadth = breadth_checker or BreadthChecker()
        self._narrative = narrative_scorer or NarrativeFitScorer()
        self._volume = volume_confirmator or VolumeFlowConfirmator()
        self._classifier = classifier or NoiseSignalClassifier(regime=regime)

    def assemble(self, briefing: PreMarketBriefing) -> SignalAssessment:
        observations: list[ClassifiedObservation] = []
        news_headlines = [n.headline for n in briefing.news_items]
        positional = briefing.positioning_snapshot

        for change in briefing.overnight_changes:
            changes_dict = {c.instrument: c.change_pct for c in briefing.overnight_changes}
            persistence = self._persistence.evaluate(
                deviation_days=change.persistence_days,
                instrument_type=PERSISTENCE_TYPE_BY_INSTRUMENT.get(change.instrument, "ETF"),
                change_z_score=change.change_sigma,
            )
            breadth = self._breadth.evaluate(
                instrument=change.instrument,
                changes=changes_dict,
                regime=self._regime,
            )
            magnitude_criteria = CriterionScore(
                criterion="magnitude",
                score=min(abs(change.change_sigma) / 3.0, 1.0) if math.isfinite(change.change_sigma) else 0.0,
                threshold=2.0,
                passed=math.isfinite(change.change_sigma) and abs(change.change_sigma) >= 2.0,
                detail=f"z-score={change.change_sigma:.2f}",
            )
            narrative = self._narrative.evaluate(
                instrument=change.instrument,
                change_pct=change.change_pct,
                news_headlines=news_headlines,
            )
            volume_kwargs: dict[str, Any] = {}
            if positional is not None and change.instrument in GOLD_CLASS_INSTRUMENTS:
                volume_kwargs = {
                    "etf_flow_change_pct": positional.etf_flow_change_pct,
                    "etf_flow_momentum": positional.etf_flow_momentum,
                    "open_interest_change_pct": positional.open_interest_change_pct,
                }
            volume = self._volume.evaluate(
                change_sigma=change.change_sigma,
                **volume_kwargs,
            )

            criteria = {
                "persistence": persistence,
                "breadth": breadth,
                "magnitude": magnitude_criteria,
                "narrative_fit": narrative,
                "volume_flow": volume,
            }

            label, confidence, reason = self._classifier.classify(
                criteria_scores=criteria,
            )

            observations.append(ClassifiedObservation(
                observation_id=f"obs_{change.instrument}_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
                source="overnight_price",
                classification=label,
                confidence=confidence,
                regime=self._regime,
                reason=reason,
                evidence=tuple(criteria.values()),
                instrument=change.instrument,
                value=change.current_price,
                change_pct=change.change_pct,
                change_sigma=change.change_sigma,
            ))

        if positional is not None:
            pos_criteria = CriterionScore(
                criterion="persistence",
                score=0.5,
                threshold=0.5,
                passed=abs(positional.cot_z_score) >= 1.0,
                detail=f"COT z-score={positional.cot_z_score:.2f}",
            )
            vol_criteria = self._volume.evaluate(
                etf_flow_change_pct=positional.etf_flow_change_pct,
                etf_flow_momentum=positional.etf_flow_momentum,
            )
            label, confidence, reason = self._classifier.classify(
                criteria_scores={
                    "persistence": pos_criteria,
                    "breadth": CriterionScore(
                        "breadth",
                        0.5 if abs(positional.etf_flow_change_pct) > ETF_FLOW_THRESHOLD_PCT else 0.0,
                        0.5,
                        abs(positional.etf_flow_change_pct) > ETF_FLOW_THRESHOLD_PCT,
                        f"ETF flow {positional.etf_flow_change_pct:+.2f}%",
                    ),
                    "magnitude": CriterionScore("magnitude", min(abs(positional.cot_z_score) / 3.0, 1.0), 2.0, abs(positional.cot_z_score) >= 2.0, detail=f"COT z={positional.cot_z_score:.2f}"),
                    "narrative_fit": CriterionScore("narrative_fit", 0.0, 0.3, False, "no specific narrative for positioning"),
                    "volume_flow": vol_criteria,
                },
            )
            observations.append(ClassifiedObservation(
                observation_id=f"obs_positioning_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
                source="positioning",
                classification=label,
                confidence=confidence,
                regime=self._regime,
                reason=reason,
                evidence=(pos_criteria, vol_criteria),
                instrument="Gold Positioning",
                change_pct=positional.etf_flow_change_pct,
            ))

        for flag in briefing.anomaly_flags:
            anomaly_criteria = [
                CriterionScore("persistence", 1.0, 0.5, True, f"anomaly: {flag.anomaly_type}"),
                CriterionScore("magnitude", min(abs(flag.value) / 3.0, 1.0), 2.0, abs(flag.value) >= 2.0, detail=f"value={flag.value:.2f}"),
                CriterionScore("breadth", 0.0, 0.5, False, "anomaly flag"),
                CriterionScore("narrative_fit", 0.0, 0.3, False, "anomaly flag"),
                CriterionScore("volume_flow", 0.0, 0.5, False, "anomaly flag"),
            ]
            label, confidence, reason = self._classifier.classify(
                criteria_scores={
                    "persistence": anomaly_criteria[0],
                    "breadth": anomaly_criteria[2],
                    "magnitude": anomaly_criteria[1],
                    "narrative_fit": anomaly_criteria[3],
                    "volume_flow": anomaly_criteria[4],
                },
            )
            slugged_description = re.sub(r"[^a-z0-9]+", "_", flag.description.lower()).strip("_")
            observations.append(ClassifiedObservation(
                observation_id=f"obs_anomaly_{flag.instrument}_{flag.anomaly_type}_{slugged_description}",
                source="anomaly_flag",
                classification=label,
                confidence=confidence,
                regime=self._regime,
                reason=reason,
                evidence=tuple(anomaly_criteria),
                instrument=flag.instrument,
                change_sigma=flag.value,
            ))

        for news in briefing.news_items:
            news_criteria = [
                CriterionScore("persistence", 0.0, 0.5, False, "single headline"),
                CriterionScore("narrative_fit", news.relevance_score, 0.3, news.relevance_score >= 0.3, detail=f"relevance={news.relevance_score:.2f}"),
                CriterionScore("breadth", 0.0, 0.5, False, "single source"),
                CriterionScore("magnitude", 0.0, 2.0, False, "text data"),
                CriterionScore("volume_flow", news.sentiment_confidence, 0.5, news.sentiment_confidence >= 0.5, detail=f"sentiment={news.sentiment_label} conf={news.sentiment_confidence:.2f}"),
            ]
            label, confidence, reason = self._classifier.classify(
                criteria_scores={
                    "persistence": news_criteria[0],
                    "breadth": news_criteria[2],
                    "magnitude": news_criteria[3],
                    "narrative_fit": news_criteria[1],
                    "volume_flow": news_criteria[4],
                },
            )
            observations.append(ClassifiedObservation(
                observation_id=f"obs_news_{hash(news.headline) % 10**8}",
                source="news",
                classification=label,
                confidence=confidence,
                regime=self._regime,
                reason=reason,
                evidence=tuple(news_criteria),
                instrument=news.source,
            ))

        assessment_id = f"sa_{briefing.briefing_id.replace('premarket_', '')}"
        return SignalAssessment(
            assessment_id=assessment_id,
            briefing_id=briefing.briefing_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            regime=self._regime,
            regime_confidence=briefing.regime_confidence,
            observations=tuple(observations),
        )
