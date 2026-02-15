"""AI Clients for Ultimate Debate

Multi-AI 끝장토론 엔진용 외부 AI 클라이언트들.
각 클라이언트는 Browser OAuth 인증과 연동됩니다.

Note:
    ClaudeClient는 더 이상 제공하지 않습니다.
    Claude Code 자체가 Claude이므로, UltimateDebate의
    include_claude_self=True 옵션으로 직접 참여합니다.
"""

from ultimate_debate.clients.base import BaseAIClient
from ultimate_debate.clients.gemini_client import GeminiClient
from ultimate_debate.clients.openai_client import OpenAIClient

__all__ = [
    "BaseAIClient",
    "OpenAIClient",
    "GeminiClient",
]
