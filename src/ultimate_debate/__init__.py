"""Ultimate Debate - Multi-AI Consensus Debate Engine."""

from ultimate_debate.clients.base import BaseAIClient
from ultimate_debate.consensus.protocol import ConsensusResult
from ultimate_debate.engine import NoAvailableClientsError, UltimateDebate

__version__ = "1.0.0"

__all__ = [
    "UltimateDebate",
    "BaseAIClient",
    "ConsensusResult",
    "NoAvailableClientsError",
]
