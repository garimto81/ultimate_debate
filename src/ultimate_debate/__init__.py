"""Ultimate Debate - Multi-AI Consensus Debate Engine."""

from ultimate_debate.engine import UltimateDebate
from ultimate_debate.clients.base import BaseAIClient
from ultimate_debate.consensus.protocol import ConsensusResult

__version__ = "1.0.0"

__all__ = [
    "UltimateDebate",
    "BaseAIClient",
    "ConsensusResult",
]
