"""Normal debate strategy."""

from ultimate_debate.strategies.base import BaseStrategy, StrategyType


class NormalStrategy(BaseStrategy):
    """Standard debate strategy with no modifications."""

    def __init__(self):
        """Initialize normal strategy."""
        super().__init__(StrategyType.NORMAL)

    async def execute(self, context: dict) -> dict:
        """Execute normal strategy (pass-through).

        Args:
            context: Debate context

        Returns:
            dict with unmodified context and standard action
        """
        return {
            "action": "CONTINUE",
            "modified_context": context,
        }
