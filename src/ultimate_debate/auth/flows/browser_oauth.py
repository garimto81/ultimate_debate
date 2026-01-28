"""Browser-based OAuth 2.0 + PKCE Authentication

Claude Code /login과 동일한 방식의 브라우저 기반 OAuth 인증.
로컬 HTTP 서버를 띄워 callback을 수신합니다.
"""

import base64
import hashlib
import secrets
import socket
import threading
import time
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from rich.console import Console
from rich.panel import Panel

console = Console()

# 세션별 콜백 결과 저장소 (state를 키로 사용)
_callback_results: dict[str, dict] = {}
_callback_lock = threading.Lock()


@dataclass
class PKCEChallenge:
    """PKCE (Proof Key for Code Exchange) 챌린지."""

    code_verifier: str
    code_challenge: str
    code_challenge_method: str = "S256"


@dataclass
class OAuthConfig:
    """OAuth 설정."""

    client_id: str
    authorization_endpoint: str
    token_endpoint: str
    redirect_uri: str
    scope: str
    client_secret: str | None = None


@dataclass
class TokenResponse:
    """토큰 응답."""

    access_token: str
    refresh_token: str | None
    token_type: str
    expires_in: int
    scope: str | None = None


class OAuthCallbackError(Exception):
    """OAuth Callback 에러."""

    pass


def generate_pkce_challenge() -> PKCEChallenge:
    """PKCE 챌린지 생성.

    Returns:
        PKCEChallenge: code_verifier와 code_challenge 포함
    """
    # code_verifier: 43-128자의 랜덤 문자열
    code_verifier = secrets.token_urlsafe(64)

    # code_challenge: code_verifier의 SHA256 해시를 base64url 인코딩
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    return PKCEChallenge(
        code_verifier=code_verifier,
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )


def find_free_port() -> int:
    """사용 가능한 포트 찾기.

    Returns:
        int: 사용 가능한 포트 번호
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """OAuth Callback 핸들러."""

    def log_message(self, format, *args):
        """로그 출력 비활성화."""
        pass

    def do_GET(self):
        """GET 요청 처리 (OAuth callback)."""
        parsed = urlparse(self.path)

        # favicon.ico 및 기타 브라우저 자동 요청 무시
        if parsed.path in ["/favicon.ico", "/robots.txt"]:
            self.send_response(204)  # No Content
            self.end_headers()
            return

        params = parse_qs(parsed.query)

        # state 추출 (세션 식별)
        state = params.get("state", [None])[0]

        # 에러 체크
        if "error" in params:
            error = params["error"][0]
            if state:
                with _callback_lock:
                    _callback_results[state] = {
                        "auth_code": None,
                        "error": error
                    }
            self._send_error_response(
                params.get("error_description", ["인증 거부됨"])[0]
            )
            return

        # 코드 추출
        if "code" in params:
            auth_code = params["code"][0]
            if state:
                with _callback_lock:
                    _callback_results[state] = {
                        "auth_code": auth_code,
                        "error": None
                    }
            self._send_success_response()
        else:
            # code가 없는 요청은 무시 (브라우저 자동 요청 등)
            self.send_response(204)
            self.end_headers()

    def _send_success_response(self):
        """성공 응답 전송."""
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>인증 성공</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                                 Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                .container {
                    text-align: center;
                    padding: 40px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 16px;
                    backdrop-filter: blur(10px);
                }
                h1 { font-size: 48px; margin-bottom: 16px; }
                p { font-size: 18px; opacity: 0.9; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>✅ 인증 성공!</h1>
                <p>이 창을 닫고 터미널로 돌아가세요.</p>
            </div>
            <script>setTimeout(() => window.close(), 3000);</script>
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def _send_error_response(self, message: str):
        """에러 응답 전송."""
        self.send_response(400)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>인증 실패</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                                 Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
                    color: white;
                }}
                .container {{
                    text-align: center;
                    padding: 40px;
                    background: rgba(255,255,255,0.1);
                    border-radius: 16px;
                    backdrop-filter: blur(10px);
                }}
                h1 {{ font-size: 48px; margin-bottom: 16px; }}
                p {{ font-size: 18px; opacity: 0.9; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>❌ 인증 실패</h1>
                <p>{message}</p>
            </div>
        </body>
        </html>
        """
        self.wfile.write(html.encode())


class BrowserOAuth:
    """Browser-based OAuth 2.0 + PKCE 인증.

    Claude Code /login과 동일한 방식:
    1. 로컬 HTTP 서버 시작
    2. 브라우저 자동 열기
    3. Callback 수신
    4. 토큰 교환

    Example:
        config = OAuthConfig(
            client_id="your-client-id",
            authorization_endpoint="https://auth.example.com/authorize",
            token_endpoint="https://auth.example.com/token",
            redirect_uri="http://localhost:{port}/callback",
            scope="openid profile"
        )
        oauth = BrowserOAuth(config)
        token = await oauth.authenticate()
    """

    def __init__(
        self,
        config: OAuthConfig,
        fixed_port: int | None = None,
        manual_callback: bool = False,
    ):
        """초기화.

        Args:
            config: OAuth 설정
            fixed_port: 고정 포트 (None이면 자동 할당)
            manual_callback: 수동 콜백 모드 (URL 직접 입력)
        """
        self.config = config
        self.pkce = generate_pkce_challenge()
        self.state = secrets.token_urlsafe(32)
        self.port = fixed_port if fixed_port else find_free_port()
        self.manual_callback = manual_callback

        # redirect_uri에 포트 적용
        if "{port}" in self.config.redirect_uri:
            self.config.redirect_uri = self.config.redirect_uri.format(port=self.port)

    def _build_authorization_url(self) -> str:
        """인증 URL 생성.

        Returns:
            str: 인증 URL
        """
        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": self.config.scope,
            "state": self.state,
            "code_challenge": self.pkce.code_challenge,
            "code_challenge_method": self.pkce.code_challenge_method,
        }

        return f"{self.config.authorization_endpoint}?{urlencode(params)}"

    async def _exchange_code_for_token(self, code: str) -> TokenResponse:
        """인증 코드를 토큰으로 교환.

        Args:
            code: 인증 코드

        Returns:
            TokenResponse: 토큰 응답
        """
        data = {
            "grant_type": "authorization_code",
            "client_id": self.config.client_id,
            "code": code,
            "redirect_uri": self.config.redirect_uri,
            "code_verifier": self.pkce.code_verifier,
        }

        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.config.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if response.status_code != 200:
                raise OAuthCallbackError(f"토큰 교환 실패: {response.text}")

            result = response.json()

            return TokenResponse(
                access_token=result["access_token"],
                refresh_token=result.get("refresh_token"),
                token_type=result.get("token_type", "Bearer"),
                expires_in=result.get("expires_in", 3600),
                scope=result.get("scope"),
            )

    def _parse_callback_url(self, callback_url: str) -> tuple[str, str]:
        """콜백 URL에서 code와 state 추출.

        Args:
            callback_url: 브라우저에서 복사한 콜백 URL

        Returns:
            tuple[str, str]: (code, state)

        Raises:
            OAuthCallbackError: 파싱 실패 시
        """
        parsed = urlparse(callback_url)
        params = parse_qs(parsed.query)

        if "error" in params:
            error_desc = params.get("error_description", ["인증 거부됨"])[0]
            raise OAuthCallbackError(f"인증 실패: {error_desc}")

        if "code" not in params:
            raise OAuthCallbackError("URL에서 code 파라미터를 찾을 수 없습니다.")

        code = params["code"][0]
        state = params.get("state", [None])[0]

        return code, state

    async def authenticate_manual(self) -> TokenResponse:
        """수동 콜백 인증 수행.

        브라우저에서 로그인 후 리디렉션된 URL을 수동으로 입력받아 처리.
        OpenAI처럼 localhost 콜백이 차단된 경우 사용.

        Returns:
            TokenResponse: 토큰 응답
        """
        # 인증 URL 생성
        auth_url = self._build_authorization_url()

        # 안내 출력
        console.print()
        console.print(
            Panel.fit(
                "[bold cyan]수동 OAuth 인증 모드[/bold cyan]\n\n"
                "1. 아래 URL을 브라우저에서 엽니다\n"
                "2. 로그인을 완료합니다\n"
                "3. 리디렉션된 URL (에러 페이지 포함)을 복사합니다\n"
                "4. 복사한 URL을 아래에 붙여넣습니다",
                title="[AUTH] Manual OAuth Login",
                border_style="yellow",
            )
        )
        console.print()
        console.print("[bold]인증 URL:[/bold]")
        console.print(f"[link={auth_url}]{auth_url}[/link]")
        console.print()

        # 브라우저 자동 열기
        webbrowser.open(auth_url)
        console.print("[dim]브라우저가 열렸습니다. 로그인 후 URL을 복사하세요.[/dim]")
        console.print()

        # 콜백 URL 입력받기
        console.print("[bold yellow]리디렉션된 URL을 붙여넣으세요:[/bold yellow]")
        console.print("[dim](localhost:1455... 또는 에러 페이지 URL 전체)[/dim]")

        try:
            callback_url = input("> ").strip()
        except (EOFError, KeyboardInterrupt) as e:
            raise OAuthCallbackError("사용자가 취소했습니다.") from e

        if not callback_url:
            raise OAuthCallbackError("URL이 입력되지 않았습니다.")

        # URL 파싱
        code, state = self._parse_callback_url(callback_url)

        # state 검증
        if state and state != self.state:
            console.print("[yellow]Warning: State 불일치 (보안 경고)[/yellow]")
            # 계속 진행 (수동 모드에서는 허용)

        console.print("[bold green][OK] 인증 코드 추출 완료![/bold green]")
        console.print("[dim]토큰 교환 중...[/dim]")

        # 토큰 교환
        token = await self._exchange_code_for_token(code)

        console.print("[bold green][OK] 인증 성공![/bold green]")

        return token

    async def authenticate(self, timeout: int = 300) -> TokenResponse:
        """인증 수행.

        Args:
            timeout: 타임아웃 (초)

        Returns:
            TokenResponse: 토큰 응답
        """
        # 수동 콜백 모드
        if self.manual_callback:
            return await self.authenticate_manual()

        # 이 세션의 state로 결과를 추적
        session_state = self.state

        # 로컬 서버 시작
        server = HTTPServer(("localhost", self.port), OAuthCallbackHandler)
        server.timeout = timeout

        # 인증 URL 생성
        auth_url = self._build_authorization_url()

        # 안내 출력
        console.print()
        console.print(
            Panel.fit(
                f"[bold cyan]브라우저가 자동으로 열립니다.[/bold cyan]\n\n"
                f"열리지 않으면 아래 URL을 직접 열어주세요:\n"
                f"[dim]{auth_url[:80]}...[/dim]",
                title="[AUTH] Login Required",
                border_style="cyan",
            )
        )
        console.print()

        # 브라우저 열기
        webbrowser.open(auth_url)

        console.print("[dim]브라우저에서 로그인 후 대기 중...[/dim]")

        # 서버를 별도 스레드에서 실행
        # 인증 코드가 수신될 때까지 반복 처리 (favicon.ico 등 무시)
        def serve():
            start_time = time.time()
            while time.time() - start_time < timeout:
                server.handle_request()
                # 이 세션의 콜백이 수신되면 종료
                with _callback_lock:
                    if session_state in _callback_results:
                        break

        thread = threading.Thread(target=serve)
        thread.start()
        thread.join(timeout=timeout)

        server.server_close()

        # 결과 확인
        with _callback_lock:
            result = _callback_results.get(session_state)
            # 결과를 가져온 후 삭제 (메모리 정리)
            if session_state in _callback_results:
                del _callback_results[session_state]

        if result is None:
            raise OAuthCallbackError("인증 시간이 초과되었습니다.")

        if result["error"]:
            raise OAuthCallbackError(f"인증 실패: {result['error']}")

        if not result["auth_code"]:
            raise OAuthCallbackError("인증 코드를 받지 못했습니다.")

        console.print("[bold green][OK] 인증 코드 수신 완료![/bold green]")
        console.print("[dim]토큰 교환 중...[/dim]")

        # 토큰 교환
        token = await self._exchange_code_for_token(result["auth_code"])

        console.print("[bold green][OK] 인증 성공![/bold green]")

        return token
