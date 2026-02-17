"""Consensus checking protocol with semantic similarity comparison."""

import hashlib
from dataclasses import dataclass, field
from typing import Any

from ultimate_debate.comparison.semantic import SemanticComparator


@dataclass
class ConsensusResult:
    """Result of consensus checking."""

    status: str  # FULL_CONSENSUS | PARTIAL_CONSENSUS | NO_CONSENSUS
    agreed_items: list[dict[str, Any]] = field(default_factory=list)
    disputed_items: list[dict[str, Any]] = field(default_factory=list)
    consensus_percentage: float = 0.0
    next_action: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ConsensusChecker:
    """Check consensus across multiple AI analyses."""

    def __init__(self, threshold: float = 0.8, similarity_threshold: float = 0.3):
        """Initialize consensus checker.

        Args:
            threshold: Minimum agreement ratio for FULL_CONSENSUS (default: 0.8)
            similarity_threshold: Minimum TF-IDF similarity for
                semantic clustering (default: 0.3)
        """
        self.threshold = threshold
        self.semantic = SemanticComparator(threshold=similarity_threshold)

    def check_consensus(self, analyses: list[dict[str, Any]]) -> ConsensusResult:
        """Check consensus by semantic similarity clustering.

        Args:
            analyses: List of AI analyses with 'conclusion' field

        Returns:
            ConsensusResult with status and detailed breakdown
        """
        if len(analyses) < 2:
            return ConsensusResult(
                status="NO_CONSENSUS",
                next_action="NEED_MORE_ANALYSES",
                details={"reason": "Not enough analyses to compare"},
            )

        # Extract and normalize conclusions
        conclusions = [
            self._normalize_conclusion(a.get("conclusion", "")) for a in analyses
        ]
        models = [a.get("model", "unknown") for a in analyses]

        # Handle edge case: empty conclusions
        if all(not c for c in conclusions):
            return ConsensusResult(
                status="NO_CONSENSUS",
                next_action="NEED_MORE_ANALYSES",
                details={"reason": "All conclusions are empty"},
            )

        # Semantic similarity clustering
        comparison = self.semantic.compare(conclusions)
        clusters = comparison["clusters"]

        # Find largest cluster
        largest_cluster = max(clusters, key=len)
        consensus_percentage = len(largest_cluster) / len(analyses)

        # Build agreed/disputed items from clusters
        agreed_items = []
        disputed_items = []

        for cluster in clusters:
            item = {
                "conclusion": conclusions[cluster[0]],
                "models": [models[i] for i in cluster],
                "count": len(cluster),
            }
            if cluster == largest_cluster:
                agreed_items.append(item)
            else:
                disputed_items.append(item)

        # Determine status and next action
        if consensus_percentage >= self.threshold:
            status = "FULL_CONSENSUS"
            next_action = None
        elif consensus_percentage >= 0.5:
            status = "PARTIAL_CONSENSUS"
            next_action = "CROSS_REVIEW"
        else:
            status = "NO_CONSENSUS"
            next_action = "DEBATE"

        return ConsensusResult(
            status=status,
            agreed_items=agreed_items,
            disputed_items=disputed_items,
            consensus_percentage=consensus_percentage,
            next_action=next_action,
            details={
                "total_analyses": len(analyses),
                "unique_clusters": len(clusters),
                "max_similarity": comparison["max_similarity"],
            },
        )

    def _normalize_conclusion(self, conclusion: str) -> str:
        """Normalize conclusion text for comparison.

        Args:
            conclusion: Raw conclusion text

        Returns:
            Normalized conclusion string
        """
        # Remove extra whitespace, convert to lowercase
        normalized = " ".join(conclusion.lower().strip().split())
        return normalized

    def _compute_hash(self, text: str) -> str:
        """Compute hash of text for comparison.

        Args:
            text: Text to hash

        Returns:
            SHA-256 hash string
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def check_cross_review_consensus(
        self, reviews: list[dict[str, Any]]
    ) -> ConsensusResult:
        """Check consensus from cross-review feedback.

        Args:
            reviews: List of cross-review results

        Returns:
            ConsensusResult based on agreement/disagreement points
        """
        if not reviews:
            return ConsensusResult(
                status="NO_CONSENSUS",
                next_action="NEED_REVIEWS",
            )

        # Count agreement and disagreement points
        total_agreement_points = 0
        total_disagreement_points = 0

        for review in reviews:
            total_agreement_points += len(review.get("agreement_points", []))
            total_disagreement_points += len(review.get("disagreement_points", []))

        total_points = total_agreement_points + total_disagreement_points
        if total_points == 0:
            agreement_ratio = 0.0
        else:
            agreement_ratio = total_agreement_points / total_points

        # Determine status
        if agreement_ratio >= self.threshold:
            status = "FULL_CONSENSUS"
            next_action = None
        elif agreement_ratio >= 0.5:
            status = "PARTIAL_CONSENSUS"
            next_action = "DEBATE"
        else:
            status = "NO_CONSENSUS"
            next_action = "DEBATE"

        return ConsensusResult(
            status=status,
            consensus_percentage=agreement_ratio,
            next_action=next_action,
            details={
                "total_reviews": len(reviews),
                "agreement_points": total_agreement_points,
                "disagreement_points": total_disagreement_points,
            },
        )
