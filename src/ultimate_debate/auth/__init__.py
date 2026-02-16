"""Ultimate Debate Auth Module (Re-export Shim)

글로벌 ai_auth 패키지에서 re-export.
하위 호환성을 위해 유지됩니다.

실제 구현: C:\\claude\\lib\\ai_auth\\
설치: uv pip install -e C:\\claude\\lib\\ai_auth
"""

# Re-export from ai_auth package
from ai_auth import (
    AuthenticationError,
    AuthToken,
    BaseProvider,
    OAuthError,
    RetryLimitExceededError,
    TokenExpiredError,
    TokenNotFoundError,
    TokenStore,
)

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
