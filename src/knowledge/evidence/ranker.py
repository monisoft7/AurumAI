from __future__ import annotations

from knowledge.evidence.collection import EvidenceCollection


class EvidenceRanker:
    @staticmethod
    def by_confidence(
        items: EvidenceCollection, reverse: bool = True
    ) -> EvidenceCollection:
        sorted_items = sorted(
            list(items), key=lambda e: e.confidence, reverse=reverse
        )
        return EvidenceCollection(sorted_items)

    @staticmethod
    def by_sample_count(
        items: EvidenceCollection, reverse: bool = True
    ) -> EvidenceCollection:
        sorted_items = sorted(
            list(items), key=lambda e: e.sample_count, reverse=reverse
        )
        return EvidenceCollection(sorted_items)

    @staticmethod
    def by_return_magnitude(
        items: EvidenceCollection, reverse: bool = True
    ) -> EvidenceCollection:
        sorted_items = sorted(
            list(items),
            key=lambda e: abs(e.average_return_pct),
            reverse=reverse,
        )
        return EvidenceCollection(sorted_items)

    @staticmethod
    def combined(
        items: EvidenceCollection,
        confidence_weight: float = 0.4,
        sample_weight: float = 0.3,
        magnitude_weight: float = 0.3,
    ) -> EvidenceCollection:
        if not items:
            return EvidenceCollection()

        max_conf = max(e.confidence for e in items) or 1.0
        max_samples = max(e.sample_count for e in items) or 1
        max_mag = max(abs(e.average_return_pct) for e in items) or 1.0

        def score(item):
            return (
                confidence_weight * (item.confidence / max_conf)
                + sample_weight * (item.sample_count / max_samples)
                + magnitude_weight * (abs(item.average_return_pct) / max_mag)
            )

        sorted_items = sorted(list(items), key=score, reverse=True)
        return EvidenceCollection(sorted_items)
