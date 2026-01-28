"""Custom authentication exceptions.

인증 관련 예외 클래스 정의.
명확한 에러 처리와 디버깅을 위한 계층 구조 제공.
"""


class AuthenticationError(Exception):
    """기본 인증 예외.

    모든 인증 관련 예외의 베이스 클래스.

    Attributes:
        provider: 인증 제공자 이름 (예: 'openai', 'google', 'claude')
    """

    def __init__(self, message: str, provider: str | None = None):
        self.provider = provider
        super().__init__(message)


class TokenExpiredError(AuthenticationError):
    """토큰 만료 예외.

    액세스 토큰이 만료되어 갱신이 필요함을 나타냄.
    """
    pass


class TokenNotFoundError(AuthenticationError):
    """토큰을 찾을 수 없음.

    저장된 토큰이 없어 새 로그인이 필요함을 나타냄.
    """
    pass


class RetryLimitExceededError(AuthenticationError):
    """재시도 한도 초과 예외.

    인증 재시도가 최대 허용 횟수를 초과함.

    Attributes:
        max_retries: 최대 재시도 횟수
        attempts: 실제 시도 횟수
        provider: 인증 제공자 이름
    """

    def __init__(
        self,
        message: str,
        max_retries: int = 1,
        attempts: int = 0,
        provider: str | None = None
    ):
        self.max_retries = max_retries
        self.attempts = attempts
        super().__init__(message, provider)


class OAuthError(AuthenticationError):
    """OAuth 플로우 에러.

    OAuth 콜백 또는 토큰 교환 실패를 나타냄.

    Attributes:
        error_code: OAuth 에러 코드 (예: 'invalid_grant', 'access_denied')
        provider: 인증 제공자 이름
    """

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        provider: str | None = None
    ):
        self.error_code = error_code
        super().__init__(message, provider)
