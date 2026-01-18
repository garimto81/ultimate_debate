"""Scope-reduced debate strategy."""

from ultimate_debate.strategies.base import BaseStrategy, StrategyType


class ScopeReducedStrategy(BaseStrategy):
    """Scope-reduced debate focusing on disputed items only."""

    def __init__(self):
        """Initialize scope-reduced strategy."""
        super().__init__(StrategyType.SCOPE_REDUCED)

    async def execute(self, context: dict) -> dict:
        """Execute scope-reduced strategy.

        Args:
            context: Debate context

        Returns:
            dict with scope reduced to disputed items
        """
        consensus_result = context.get("consensus_result", {})
        disputed_items = consensus_result.get("disputed_items", [])

        # Extract only disputed conclusions
        disputed_topics = [item.get("conclusion", "") for item in disputed_items]

        modified_context = context.copy()
        modified_context["scope"] = {
            "focus": "disputed_items_only",
            "disputed_topics": disputed_topics,
            "instructions": (
                "Focus only on the following disputed topics: "
                f"{', '.join(disputed_topics)}. "
                "Ignore agreed-upon items."
            ),
        }

        return {
            "action": "REDUCE_SCOPE",
            "modified_context": modified_context,
        }
