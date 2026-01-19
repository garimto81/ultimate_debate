"""AI Clients for Ultimate Debate

Multi-AI 끝장토론 엔진용 AI 클라이언트들.
각 클라이언트는 Browser OAuth 인증과 연동됩니다.
"""

from ultimate_debate.clients.base import BaseAIClient
from ultimate_debate.clients.openai_client import OpenAIClient
from ultimate_debate.clients.gemini_client import GeminiClient

__all__ = [
    "BaseAIClient",
    "OpenAIClient",
    "GeminiClient",
]
