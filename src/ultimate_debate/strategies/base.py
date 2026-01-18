"""Base strategy interface and types."""

from abc import ABC, abstractmethod
from enum import Enum


class StrategyType(Enum):
    """Debate strategy types."""

    NORMAL = "normal"
    MEDIATED = "mediated"
    SCOPE_REDUCED = "scope_reduced"
    PERSPECTIVE_SHIFT = "perspective_shift"


class BaseStrategy(ABC):
    """Base class for debate strategies."""

    def __init__(self, strategy_type: StrategyType):
        """Initialize strategy.

        Args:
            strategy_type: Type of strategy
        """
        self.strategy_type = strategy_type

    @abstractmethod
    async def execute(self, context: dict) -> dict:
        """Execute strategy.

        Args:
            context: Debate context containing:
                - task: Original task description
                - current_analyses: Current AI analyses
                - consensus_result: Latest consensus result
                - round: Current round number

        Returns:
            dict with keys:
                - action: Next action to take
                - modified_context: Updated context
        """
        pass
