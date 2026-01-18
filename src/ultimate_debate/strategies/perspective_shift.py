"""Perspective-shift debate strategy."""

from ultimate_debate.strategies.base import BaseStrategy, StrategyType


class PerspectiveShiftStrategy(BaseStrategy):
    """Perspective-shift strategy forcing models to argue opposing views."""

    def __init__(self):
        """Initialize perspective-shift strategy."""
        super().__init__(StrategyType.PERSPECTIVE_SHIFT)

    async def execute(self, context: dict) -> dict:
        """Execute perspective-shift strategy.

        Args:
            context: Debate context

        Returns:
            dict with perspective-shift instructions
        """
        current_analyses = context.get("current_analyses", {})

        # Build perspective shift assignments
        model_names = list(current_analyses.keys())
        if len(model_names) < 2:
            # Not enough models to shift perspectives
            return {
                "action": "SKIP",
                "modified_context": context,
            }

        # Rotate perspectives: each model argues the next model's position
        shift_map = {}
        for i, model in enumerate(model_names):
            next_model = model_names[(i + 1) % len(model_names)]
            shift_map[model] = {
                "original_position": current_analyses[model].get("conclusion", ""),
                "assigned_position": current_analyses[next_model].get("conclusion", ""),
            }

        modified_context = context.copy()
        modified_context["perspective_shift"] = {
            "enabled": True,
            "shift_map": shift_map,
            "instructions": (
                "Argue from the assigned perspective, not your original position. "
                "This exercise helps identify weaknesses in opposing views."
            ),
        }

        return {
            "action": "SHIFT_PERSPECTIVES",
            "modified_context": modified_context,
        }
