from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge.evidence.collection import EvidenceCollection
from knowledge.evidence.evidence import Evidence


@dataclass(frozen=True)
class AgreementPair:
    event_type_a: str
    event_type_b: str
    agreement: str
    agreement_score: float
    a_avg_confidence: float
    b_avg_confidence: float
    a_positive_ratio: float
    b_positive_ratio: float
    a_negative_ratio: float
    b_negative_ratio: float


@dataclass(frozen=True)
class CrossEventResult:
    event_type_groups: dict[str, EvidenceCollection]
    pairwise_agreements: list[AgreementPair] = field(default_factory=list)
    overall_consensus: str = "insufficient"
    consensus_confidence: float = 0.0
    conflicts: list[str] = field(default_factory=list)


_BIAS_POSITIVE = "gold_positive_bias"
_BIAS_NEGATIVE = "gold_negative_bias"
_BIAS_MIXED = "mixed_or_context_dependent"


class CrossEventAnalyzer:
    def analyze(self, collection: EvidenceCollection) -> CrossEventResult:
        groups = self._group_by_event_type(collection)
        if len(groups) < 2:
            single_type = next(iter(groups)) if groups else "unknown"
            return CrossEventResult(
                event_type_groups=groups,
                overall_consensus="insufficient",
                consensus_confidence=0.0,
                conflicts=[f"Only one event type present: {single_type}"],
            )

        pairs = self._compute_pairs(groups)
        consensus, confidence, conflicts = self._aggregate(pairs)

        return CrossEventResult(
            event_type_groups=groups,
            pairwise_agreements=pairs,
            overall_consensus=consensus,
            consensus_confidence=confidence,
            conflicts=conflicts,
        )

    def _group_by_event_type(
        self, collection: EvidenceCollection
    ) -> dict[str, EvidenceCollection]:
        groups: dict[str, list[Evidence]] = {}
        for ev in collection:
            et = ev.event_type
            if et not in groups:
                groups[et] = []
            groups[et].append(ev)
        return {k: EvidenceCollection(v) for k, v in groups.items()}

    def _compute_pairs(
        self, groups: dict[str, EvidenceCollection]
    ) -> list[AgreementPair]:
        types = sorted(groups.keys())
        pairs: list[AgreementPair] = []
        for i in range(len(types)):
            for j in range(i + 1, len(types)):
                a_type, b_type = types[i], types[j]
                pair = self._analyze_pair(
                    a_type, groups[a_type], b_type, groups[b_type]
                )
                pairs.append(pair)
        return pairs

    def _analyze_pair(
        self,
        a_type: str,
        a_coll: EvidenceCollection,
        b_type: str,
        b_coll: EvidenceCollection,
    ) -> AgreementPair:
        a_pos, a_neg, a_conf = self._bias_stats(a_coll)
        b_pos, b_neg, b_conf = self._bias_stats(b_coll)
        score = self._agreement_score(a_pos, a_neg, b_pos, b_neg)
        label = self._agreement_label(score, a_pos, a_neg, b_pos, b_neg)
        return AgreementPair(
            event_type_a=a_type,
            event_type_b=b_type,
            agreement=label,
            agreement_score=score,
            a_avg_confidence=a_conf,
            b_avg_confidence=b_conf,
            a_positive_ratio=a_pos,
            b_positive_ratio=b_pos,
            a_negative_ratio=a_neg,
            b_negative_ratio=b_neg,
        )

    def _bias_stats(
        self, coll: EvidenceCollection
    ) -> tuple[float, float, float]:
        if not coll:
            return 0.0, 0.0, 0.0
        n = len(coll)
        pos = sum(1 for ev in coll if ev.bias == _BIAS_POSITIVE)
        neg = sum(1 for ev in coll if ev.bias == _BIAS_NEGATIVE)
        avg_conf = sum(ev.confidence for ev in coll) / n
        return pos / n, neg / n, avg_conf

    def _agreement_score(
        self, a_pos: float, a_neg: float, b_pos: float, b_neg: float
    ) -> float:
        a_dir = a_pos - a_neg
        b_dir = b_pos - b_neg
        return 1.0 - abs(a_dir - b_dir) / 2.0

    def _agreement_label(
        self, score: float, a_pos: float, a_neg: float, b_pos: float, b_neg: float
    ) -> str:
        a_dir = "positive" if a_pos > a_neg else "negative" if a_neg > a_pos else "mixed"
        b_dir = "positive" if b_pos > b_neg else "negative" if b_neg > b_pos else "mixed"
        if a_dir == b_dir and score >= 0.8:
            return "agreement"
        if a_dir == b_dir:
            return "weak_agreement"
        if a_dir != b_dir and a_dir != "mixed" and b_dir != "mixed":
            return "conflict"
        return "mixed"

    def _aggregate(
        self, pairs: list[AgreementPair]
    ) -> tuple[str, float, list[str]]:
        if not pairs:
            return "insufficient", 0.0, ["No pairwise comparisons available"]

        conflicts_list: list[str] = []
        agree_count = sum(1 for p in pairs if p.agreement in ("agreement", "weak_agreement"))
        conflict_count = sum(1 for p in pairs if p.agreement == "conflict")
        mixed_count = sum(1 for p in pairs if p.agreement == "mixed")
        total = len(pairs)

        avg_score = sum(p.agreement_score for p in pairs) / total
        avg_conf_a = sum(p.a_avg_confidence for p in pairs) / total
        avg_conf_b = sum(p.b_avg_confidence for p in pairs) / total
        combined_conf = (avg_conf_a + avg_conf_b) / 2.0

        for p in pairs:
            if p.agreement == "conflict":
                conflicts_list.append(
                    f"{p.event_type_a} ({p.a_positive_ratio:.0%}+/{p.a_negative_ratio:.0%}-) vs "
                    f"{p.event_type_b} ({p.b_positive_ratio:.0%}+/{p.b_negative_ratio:.0%}-)"
                )

        if agree_count == total:
            consensus = "strong_agreement"
        elif conflict_count == total:
            consensus = "conflict"
        elif agree_count > conflict_count + mixed_count:
            consensus = "agreement"
        elif conflict_count > agree_count + mixed_count:
            consensus = "conflict"
        else:
            consensus = "mixed"

        return consensus, combined_conf * avg_score, conflicts_list
