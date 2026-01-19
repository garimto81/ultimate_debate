"""Device Code OAuth Flow (RFC 8628)

localhost 콜백 없이 인증을 완료하는 Device Authorization Grant 구현.
OpenAI와 같이 localhost 콜백이 차단된 환경에서 사용.

플로우:
1. 앱이 device_code, user_code 요청
2. 사용자에게 verification_uri + user_code 표시
3. 사용자가 브라우저에서 URL 접속 → 코드 입력 → 로그인
4. 앱이 백그라운드에서 토큰 폴링
5. 인증 완료 시 access_token 수신
"""

import asyncio
import time
from dataclasses import dataclass

import httpx
from rich.console import Console
from rich.panel import Panel

from ultimate_debate.auth.flows.browser_oauth import TokenResponse

console = Console()


class DeviceCodeError(Exception):
    """Device Code Flow 관련 에러."""

    pass


@dataclass
class DeviceCodeResponse:
    """Device Code 응답.

    Attributes:
        device_code: 토큰 교환에 사용되는 device code
        user_code: 사용자가 입력해야 하는 코드
        verification_uri: 사용자가 접속해야 하는 URL
        verification_uri_complete: user_code가 포함된 완전한 URL (선택)
        expires_in: device_code 만료 시간 (초)
        interval: 폴링 간격 (초)
    """

    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int
    verification_uri_complete: str | None = None


@dataclass
class DeviceCodeConfig:
    """Device Code Flow 설정.

    Attributes:
        client_id: OAuth Client ID
        device_authorization_endpoint: Device Authorization Endpoint
        token_endpoint: Token Endpoint
        scope: 요청할 scope
    """

    client_id: str
    device_authorization_endpoint: str
    token_endpoint: str
    scope: str


class DeviceCodeOAuth:
    """Device Code OAuth Flow 구현.

    RFC 8628 Device Authorization Grant.
    localhost 콜백 없이 인증을 완료합니다.

    Example:
        config = DeviceCodeConfig(
            client_id="your-client-id",
            device_authorization_endpoint="https://auth.example.com/device/code",
            token_endpoint="https://auth.example.com/token",
            scope="openid profile"
        )
        oauth = DeviceCodeOAuth(config)
        token = await oauth.authenticate()
    """

    # 폴링 에러 코드 (RFC 8628)
    ERROR_AUTHORIZATION_PENDING = "authorization_pending"
    ERROR_SLOW_DOWN = "slow_down"
    ERROR_EXPIRED_TOKEN = "expired_token"
    ERROR_ACCESS_DENIED = "access_denied"

    def __init__(self, config: DeviceCodeConfig):
        """초기화.

        Args:
            config: Device Code Flow 설정
        """
        self.config = config

    async def request_device_code(self) -> DeviceCodeResponse:
        """Device Code 요청.

        Device Authorization Endpoint에 요청하여 device_code와 user_code를 받습니다.

        Returns:
            DeviceCodeResponse: device_code, user_code, verification_uri 등

        Raises:
            DeviceCodeError: 요청 실패 시
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.config.device_authorization_endpoint,
                data={
                    "client_id": self.config.client_id,
                    "scope": self.config.scope,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                msg = f"device code 요청 실패: {response.status_code}"
                raise DeviceCodeError(msg)

            data = response.json()

            return DeviceCodeResponse(
                device_code=data["device_code"],
                user_code=data["user_code"],
                verification_uri=data["verification_uri"],
                verification_uri_complete=data.get("verification_uri_complete"),
                expires_in=data.get("expires_in", 900),  # 기본 15분
                interval=data.get("interval", 5),  # 기본 5초
            )

    async def poll_for_token(
        self,
        device_code: str,
        interval: int,
        timeout: int,
    ) -> TokenResponse:
        """토큰 폴링.

        device_code로 토큰 엔드포인트를 폴링하여 access_token을 받습니다.

        Args:
            device_code: request_device_code에서 받은 device_code
            interval: 폴링 간격 (초)
            timeout: 최대 대기 시간 (초)

        Returns:
            TokenResponse: access_token, refresh_token 등

        Raises:
            DeviceCodeError: 인증 실패, 만료, 거부 시
        """
        start_time = time.time()
        current_interval = interval

        async with httpx.AsyncClient() as client:
            while True:
                # 타임아웃 체크
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    raise DeviceCodeError("인증 시간 초과 (timeout)")

                # 토큰 요청
                response = await client.post(
                    self.config.token_endpoint,
                    data={
                        "client_id": self.config.client_id,
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                if response.status_code == 200:
                    # 성공
                    data = response.json()
                    return TokenResponse(
                        access_token=data["access_token"],
                        refresh_token=data.get("refresh_token"),
                        token_type=data.get("token_type", "Bearer"),
                        expires_in=data.get("expires_in", 3600),
                        scope=data.get("scope"),
                    )

                # 에러 응답 처리
                try:
                    error_data = response.json()
                    error = error_data.get("error", "")
                    error_description = error_data.get("error_description", "")
                except Exception as e:
                    msg = f"토큰 요청 실패: {response.status_code}"
                    raise DeviceCodeError(msg) from e

                if error == self.ERROR_AUTHORIZATION_PENDING:
                    # 아직 사용자가 인증하지 않음 - 계속 폴링
                    await asyncio.sleep(current_interval)
                    continue

                elif error == self.ERROR_SLOW_DOWN:
                    # 폴링 속도 감소 요청
                    current_interval += 5  # RFC 8628: 5초 추가
                    await asyncio.sleep(current_interval)
                    continue

                elif error == self.ERROR_EXPIRED_TOKEN:
                    # device_code 만료
                    raise DeviceCodeError(f"Device code expired: {error_description}")

                elif error == self.ERROR_ACCESS_DENIED:
                    # 사용자가 거부
                    raise DeviceCodeError(f"Access denied: {error_description}")

                else:
                    # 기타 에러
                    msg = f"토큰 요청 실패: {error} - {error_description}"
                    raise DeviceCodeError(msg)

    def display_instructions(self, device_response: DeviceCodeResponse) -> None:
        """사용자 안내 메시지 출력.

        Args:
            device_response: device code 응답
        """
        verification_url = (
            device_response.verification_uri_complete
            or device_response.verification_uri
        )

        user_code = device_response.user_code
        expires_min = device_response.expires_in // 60

        console.print()
        console.print(
            Panel.fit(
                f"[bold cyan]OpenAI Device Code 인증[/bold cyan]\n\n"
                f"다음 URL을 브라우저에서 열고 코드를 입력하세요:\n\n"
                f"[bold]URL:[/bold] [link={verification_url}]{verification_url}[/link]\n"
                f"[bold]코드:[/bold] [bold yellow]{user_code}[/bold yellow]\n\n"
                f"[dim]만료: {expires_min}분[/dim]",
                title="[AUTH] Device Code Login",
                border_style="cyan",
            )
        )
        console.print()

    async def authenticate(
        self,
        timeout: int = 900,
        poll_interval: int | None = None,
        auto_open_browser: bool = True,
    ) -> TokenResponse:
        """전체 인증 플로우 실행.

        1. Device code 요청
        2. 사용자 안내 출력
        3. 토큰 폴링

        Args:
            timeout: 최대 대기 시간 (초, 기본 15분)
            poll_interval: 폴링 간격 (None이면 서버 응답 사용)
            auto_open_browser: 자동으로 브라우저 열기

        Returns:
            TokenResponse: 인증 토큰

        Raises:
            DeviceCodeError: 인증 실패 시
        """
        # 1. Device code 요청
        device_response = await self.request_device_code()

        # 2. 사용자 안내 출력
        self.display_instructions(device_response)

        # 3. 브라우저 자동 열기 (선택)
        if auto_open_browser:
            import webbrowser

            url = (
                device_response.verification_uri_complete
                or device_response.verification_uri
            )
            webbrowser.open(url)
            console.print("[dim]브라우저가 열렸습니다. 로그인 후 대기 중...[/dim]")

        # 4. 토큰 폴링
        interval = poll_interval or device_response.interval
        effective_timeout = min(timeout, device_response.expires_in)

        console.print("[dim]인증 대기 중...[/dim]")

        token = await self.poll_for_token(
            device_code=device_response.device_code,
            interval=interval,
            timeout=effective_timeout,
        )

        console.print("[bold green][OK] 인증 성공![/bold green]")

        return token
