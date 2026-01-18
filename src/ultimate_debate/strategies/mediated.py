"""Mediated debate strategy."""

from ultimate_debate.strategies.base import BaseStrategy, StrategyType


class MediatedStrategy(BaseStrategy):
    """Mediated debate with neutral facilitator."""

    def __init__(self):
        """Initialize mediated strategy."""
        super().__init__(StrategyType.MEDIATED)

    async def execute(self, context: dict) -> dict:
        """Execute mediated strategy.

        Args:
            context: Debate context

        Returns:
            dict with mediation instructions added to context
        """
        # Add mediation instructions
        modified_context = context.copy()
        modified_context["mediation"] = {
            "role": "neutral_facilitator",
            "instructions": (
                "Focus on finding common ground. "
                "Acknowledge valid points from all perspectives. "
                "Seek compromise where disagreements exist."
            ),
        }

        return {
            "action": "MEDIATE",
            "modified_context": modified_context,
        }
