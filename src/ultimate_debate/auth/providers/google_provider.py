"""Google Provider

Gemini API용 Browser OAuth 2.0 + PKCE 인증.
"""

import os
from datetime import datetime, timedelta

import httpx

from ultimate_debate.auth.flows.browser_oauth import (
    BrowserOAuth,
    OAuthCallbackError,
    OAuthConfig,
)
from ultimate_debate.auth.providers.base import AuthToken, BaseProvider


class GoogleProvider(BaseProvider):
    """Google Gemini API용 Provider

    OAuth 2.0 Authorization Code + PKCE 사용.
    Browser OAuth 방식으로 인증.

    Example:
        provider = GoogleProvider(client_id="your-client-id")
        token = await provider.login()
    """

    # Google OAuth 설정
    AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
    # Gemini API 스코프
    SCOPE = "https://www.googleapis.com/auth/generative-language.retriever openid email"
    # 로컬 콜백 포트
    REDIRECT_PORT = 8080

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None
    ):
        self.client_id = client_id or os.getenv("GOOGLE_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("GOOGLE_CLIENT_SECRET")

    @property
    def name(self) -> str:
        return "google"

    @property
    def display_name(self) -> str:
        return "Google Gemini"

    async def login(self, **kwargs) -> AuthToken:
        """Browser OAuth로 로그인"""
        if not self.client_id:
            raise ValueError(
                "Google Client ID가 필요합니다.\n"
                "1. Google Cloud Console에서 OAuth 클라이언트 생성\n"
                "2. GOOGLE_CLIENT_ID 환경변수 설정"
            )

        config = OAuthConfig(
            client_id=self.client_id,
            client_secret=self.client_secret,
            authorization_endpoint=self.AUTHORIZATION_ENDPOINT,
            token_endpoint=self.TOKEN_ENDPOINT,
            redirect_uri=f"http://localhost:{self.REDIRECT_PORT}/callback",
            scope=self.SCOPE
        )

        oauth = BrowserOAuth(config, fixed_port=self.REDIRECT_PORT)

        try:
            token_response = await oauth.authenticate(timeout=300)
        except OAuthCallbackError as e:
            raise ValueError(f"Google 인증 실패: {e}")

        # 만료 시간 계산
        expires_at = datetime.now() + timedelta(seconds=token_response.expires_in)

        return AuthToken(
            provider=self.name,
            access_token=token_response.access_token,
            refresh_token=token_response.refresh_token,
            expires_at=expires_at,
            token_type=token_response.token_type,
            scopes=token_response.scope.split() if token_response.scope else []
        )

    async def refresh(self, token: AuthToken) -> AuthToken:
        """Refresh token으로 갱신"""
        if not token.refresh_token:
            raise ValueError("No refresh token available")

        async with httpx.AsyncClient() as client:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": token.refresh_token,
                "client_id": self.client_id,
            }
            if self.client_secret:
                data["client_secret"] = self.client_secret

            response = await client.post(
                self.TOKEN_ENDPOINT,
                data=data
            )

            if response.status_code != 200:
                raise ValueError(f"Token refresh failed: {response.text}")

            result = response.json()
            expires_at = datetime.now() + timedelta(seconds=result.get("expires_in", 3600))

            return AuthToken(
                provider=self.name,
                access_token=result["access_token"],
                refresh_token=result.get("refresh_token", token.refresh_token),
                expires_at=expires_at,
                token_type=result.get("token_type", "Bearer"),
                scopes=result.get("scope", "").split() if result.get("scope") else token.scopes
            )

    async def logout(self, token: AuthToken) -> bool:
        """토큰 폐기"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/revoke",
                data={"token": token.access_token}
            )
            return response.status_code == 200

    async def validate(self, token: AuthToken) -> bool:
        """토큰 유효성 검증"""
        if token.is_expired():
            return False

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v3/tokeninfo",
                params={"access_token": token.access_token}
            )
            return response.status_code == 200

    async def get_account_info(self, token: AuthToken) -> dict | None:
        """계정 정보 조회"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {token.access_token}"}
            )
            if response.status_code == 200:
                return response.json()
        return None
