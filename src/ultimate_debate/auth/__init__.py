"""Ultimate Debate Auth Module

Multi-AI 인증 통합 모듈.
OpenAI, Google Gemini, Poe 등 다양한 AI 서비스 인증 지원.

Example:
    from ultimate_debate.auth import TokenStore, OpenAIProvider

    store = TokenStore()
    provider = OpenAIProvider()
    token = await provider.login()
    await store.save(token)
"""

from ultimate_debate.auth.exceptions import (
    AuthenticationError,
    OAuthError,
    RetryLimitExceededError,
    TokenExpiredError,
    TokenNotFoundError,
)
from ultimate_debate.auth.providers.base import AuthToken, BaseProvider
from ultimate_debate.auth.storage.token_store import TokenStore

__all__ = [
    # Core
    "AuthToken",
    "BaseProvider",
    "TokenStore",
    # Exceptions
    "AuthenticationError",
    "TokenExpiredError",
    "TokenNotFoundError",
    "RetryLimitExceededError",
    "OAuthError",
]
