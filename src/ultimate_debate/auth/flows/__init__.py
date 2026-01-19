"""OAuth Flows

Browser OAuth 인증 플로우 구현.
GPT와 Gemini 모두 Browser-based OAuth 2.0 + PKCE 사용.
Device Code Flow는 localhost 콜백이 차단된 환경에서 사용.
"""

from ultimate_debate.auth.flows.browser_oauth import (
    BrowserOAuth,
    OAuthCallbackError,
    OAuthConfig,
    PKCEChallenge,
    TokenResponse,
    find_free_port,
    generate_pkce_challenge,
)
from ultimate_debate.auth.flows.device_code import (
    DeviceCodeConfig,
    DeviceCodeError,
    DeviceCodeOAuth,
    DeviceCodeResponse,
)

__all__ = [
    # Browser OAuth
    "BrowserOAuth",
    "OAuthConfig",
    "OAuthCallbackError",
    "PKCEChallenge",
    "TokenResponse",
    "generate_pkce_challenge",
    "find_free_port",
    # Device Code Flow
    "DeviceCodeOAuth",
    "DeviceCodeConfig",
    "DeviceCodeResponse",
    "DeviceCodeError",
]
