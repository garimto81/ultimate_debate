"""Token Store

OS 자격증명 저장소를 사용한 토큰 관리.
"""

import json
import os
import platform
from pathlib import Path

from ultimate_debate.auth.providers.base import AuthToken

# keyring이 없으면 파일 기반 저장소 사용
try:
    import keyring

    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False


class TokenStore:
    """토큰 저장소

    OS별 최적의 저장 방식 사용:
    - Windows: DPAPI (keyring) 또는 파일
    - macOS: Keychain (keyring) 또는 파일
    - Linux: libsecret (keyring) 또는 파일

    Example:
        store = TokenStore()
        await store.save(token)
        token = await store.load("openai")
        await store.delete("openai")
    """

    SERVICE_NAME = "claude-code-ai-auth"

    def __init__(self, storage_dir: Path | None = None):
        self.storage_dir = storage_dir or self._default_storage_dir()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _default_storage_dir(self) -> Path:
        """OS별 기본 저장 디렉토리"""
        system = platform.system()
        if system == "Windows":
            base = Path(os.environ.get("APPDATA", Path.home()))
        elif system == "Darwin":  # macOS
            base = Path.home() / "Library" / "Application Support"
        else:  # Linux
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / "claude-code" / "ai-auth"

    def _token_file_path(self, provider: str) -> Path:
        """토큰 파일 경로"""
        return self.storage_dir / f"{provider}.json"

    async def save(self, token: AuthToken) -> bool:
        """토큰 저장

        Args:
            token: 저장할 토큰

        Returns:
            bool: 성공 여부
        """
        try:
            if HAS_KEYRING:
                # keyring 사용 (암호화 저장)
                token_data = json.dumps(token.to_dict())
                keyring.set_password(self.SERVICE_NAME, token.provider, token_data)
            else:
                # 파일 기반 저장 (권한 제한)
                file_path = self._token_file_path(token.provider)
                with open(file_path, "w") as f:
                    json.dump(token.to_dict(), f, indent=2)
                # 보안: 사용자만 읽기/쓰기
                file_path.chmod(0o600)
            return True
        except Exception as e:
            print(f"Token save error: {e}")
            return False

    async def load(self, provider: str) -> AuthToken | None:
        """토큰 로드

        Args:
            provider: Provider 이름

        Returns:
            AuthToken 또는 None
        """
        try:
            if HAS_KEYRING:
                token_data = keyring.get_password(self.SERVICE_NAME, provider)
                if token_data:
                    return AuthToken.from_dict(json.loads(token_data))
            else:
                file_path = self._token_file_path(provider)
                if file_path.exists():
                    with open(file_path) as f:
                        return AuthToken.from_dict(json.load(f))
        except Exception as e:
            print(f"Token load error: {e}")
        return None

    async def delete(self, provider: str) -> bool:
        """토큰 삭제

        Args:
            provider: Provider 이름

        Returns:
            bool: 성공 여부
        """
        try:
            if HAS_KEYRING:
                keyring.delete_password(self.SERVICE_NAME, provider)
            file_path = self._token_file_path(provider)
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception as e:
            print(f"Token delete error: {e}")
            return False

    async def list_providers(self) -> list[str]:
        """저장된 모든 provider 목록

        Returns:
            list[str]: Provider 이름 목록
        """
        providers = []

        # 파일 기반 검색
        for file_path in self.storage_dir.glob("*.json"):
            providers.append(file_path.stem)

        # keyring은 목록 조회가 어려우므로 알려진 provider만 확인
        known_providers = ["openai", "google", "poe", "anthropic"]
        if HAS_KEYRING:
            for provider in known_providers:
                if provider not in providers:
                    try:
                        if keyring.get_password(self.SERVICE_NAME, provider):
                            providers.append(provider)
                    except Exception:
                        pass

        return list(set(providers))

    async def clear_all(self) -> bool:
        """모든 토큰 삭제

        Returns:
            bool: 성공 여부
        """
        success = True
        for provider in await self.list_providers():
            if not await self.delete(provider):
                success = False
        return success

    # Sync 버전 메서드 (cross-ai-verifier 호환용)

    def load_sync(self, provider: str) -> AuthToken | None:
        """토큰 로드 (동기 버전)

        Args:
            provider: Provider 이름

        Returns:
            AuthToken 또는 None
        """
        try:
            if HAS_KEYRING:
                token_data = keyring.get_password(self.SERVICE_NAME, provider)
                if token_data:
                    return AuthToken.from_dict(json.loads(token_data))
            else:
                file_path = self._token_file_path(provider)
                if file_path.exists():
                    with open(file_path) as f:
                        return AuthToken.from_dict(json.load(f))
        except Exception as e:
            print(f"Token load error: {e}")
        return None

    def get_valid_token(self, provider: str) -> AuthToken | None:
        """유효한 토큰만 반환 (동기 버전)

        만료된 토큰은 None 반환.

        Args:
            provider: Provider 이름

        Returns:
            AuthToken: 유효한 토큰 또는 None
        """
        token = self.load_sync(provider)
        if token and not token.is_expired():
            return token
        return None

    def has_valid_token(self, provider: str) -> bool:
        """유효한 토큰 존재 여부

        Args:
            provider: Provider 이름

        Returns:
            bool: 유효한 토큰 존재 여부
        """
        return self.get_valid_token(provider) is not None
