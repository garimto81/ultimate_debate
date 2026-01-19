"""Base Provider 추상 클래스

모든 AI Provider가 구현해야 하는 인터페이스 정의.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AuthToken:
    """인증 토큰 데이터 클래스"""

    provider: str
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    token_type: str = "Bearer"
    scopes: list[str] = field(default_factory=list)
    account_info: dict | None = None

    def is_expired(self) -> bool:
        """토큰 만료 여부 확인"""
        if self.expires_at is None:
            return False
        return datetime.now() >= self.expires_at

    def expires_in_days(self) -> int | None:
        """만료까지 남은 일수"""
        if self.expires_at is None:
            return None
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)

    def to_dict(self) -> dict:
        """딕셔너리로 변환 (저장용)"""
        return {
            "provider": self.provider,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "token_type": self.token_type,
            "scopes": self.scopes,
            "account_info": self.account_info,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuthToken":
        """딕셔너리에서 생성"""
        expires_at = None
        if data.get("expires_at"):
            expires_at = datetime.fromisoformat(data["expires_at"])
        return cls(
            provider=data["provider"],
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
            token_type=data.get("token_type", "Bearer"),
            scopes=data.get("scopes", []),
            account_info=data.get("account_info"),
        )


class BaseProvider(ABC):
    """AI Provider 추상 베이스 클래스

    모든 Provider는 이 클래스를 상속해야 함.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 이름"""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """표시용 이름"""
        pass

    @abstractmethod
    async def login(self, **kwargs) -> AuthToken:
        """로그인 수행

        Returns:
            AuthToken: 인증 토큰
        """
        pass

    @abstractmethod
    async def refresh(self, token: AuthToken) -> AuthToken:
        """토큰 갱신

        Args:
            token: 기존 토큰

        Returns:
            AuthToken: 갱신된 토큰
        """
        pass

    @abstractmethod
    async def logout(self, token: AuthToken) -> bool:
        """로그아웃

        Args:
            token: 현재 토큰

        Returns:
            bool: 성공 여부
        """
        pass

    @abstractmethod
    async def validate(self, token: AuthToken) -> bool:
        """토큰 유효성 검증

        Args:
            token: 검증할 토큰

        Returns:
            bool: 유효 여부
        """
        pass

    async def get_account_info(self, token: AuthToken) -> dict | None:
        """계정 정보 조회 (선택적 구현)"""
        return token.account_info

    def is_token_valid(self, token: AuthToken) -> bool:
        """토큰 유효성 빠른 확인 (만료 시간 기반)"""
        if token.is_expired():
            return False
        return True
