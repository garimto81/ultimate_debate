"""Auth Providers

각 AI 서비스별 인증 Provider 구현.
GPT와 Gemini 모두 Browser OAuth 방식 사용.
"""

from ultimate_debate.auth.providers.base import AuthToken, BaseProvider
from ultimate_debate.auth.providers.google_provider import GoogleProvider
from ultimate_debate.auth.providers.openai_provider import OpenAIProvider

__all__ = [
    "AuthToken",
    "BaseProvider",
    "OpenAIProvider",
    "GoogleProvider",
]
