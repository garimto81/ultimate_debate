"""Token Store 테스트"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from ultimate_debate.auth.providers.base import AuthToken
from ultimate_debate.auth.storage.token_store import TokenStore


@pytest.fixture
def temp_store():
    """임시 저장소"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield TokenStore(storage_dir=Path(tmpdir))


@pytest.fixture
def sample_token():
    """샘플 토큰"""
    return AuthToken(
        provider="test",
        access_token="test-access-token",
        refresh_token="test-refresh-token",
        expires_at=datetime.now() + timedelta(days=30),
        scopes=["chat", "models"],
    )


class TestTokenStore:
    """TokenStore 테스트"""

    @pytest.mark.asyncio
    async def test_save_and_load(self, temp_store, sample_token):
        """저장 및 로드"""
        # 저장
        result = await temp_store.save(sample_token)
        assert result is True

        # 로드
        loaded = await temp_store.load("test")
        assert loaded is not None
        assert loaded.provider == "test"
        assert loaded.access_token == "test-access-token"

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, temp_store):
        """존재하지 않는 토큰 로드"""
        loaded = await temp_store.load("nonexistent")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_delete(self, temp_store, sample_token):
        """토큰 삭제"""
        # 저장
        await temp_store.save(sample_token)

        # 삭제
        result = await temp_store.delete("test")
        assert result is True

        # 확인
        loaded = await temp_store.load("test")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_list_providers(self, temp_store, sample_token):
        """Provider 목록"""
        # 여러 토큰 저장
        await temp_store.save(sample_token)

        token2 = AuthToken(provider="test2", access_token="token2")
        await temp_store.save(token2)

        # 목록 확인
        providers = await temp_store.list_providers()
        assert "test" in providers
        assert "test2" in providers

    @pytest.mark.asyncio
    async def test_clear_all(self, temp_store, sample_token):
        """모든 토큰 삭제"""
        # 저장
        await temp_store.save(sample_token)

        token2 = AuthToken(provider="test2", access_token="token2")
        await temp_store.save(token2)

        # 모두 삭제
        result = await temp_store.clear_all()
        assert result is True

        # 확인
        providers = await temp_store.list_providers()
        assert len(providers) == 0

    def test_get_valid_token_sync(self, temp_store, sample_token):
        """동기 버전: 유효한 토큰 조회"""
        import asyncio

        asyncio.run(temp_store.save(sample_token))

        # 유효한 토큰
        token = temp_store.get_valid_token("test")
        assert token is not None
        assert token.access_token == "test-access-token"

    def test_get_valid_token_expired(self, temp_store):
        """동기 버전: 만료된 토큰은 None 반환"""
        import asyncio

        expired_token = AuthToken(
            provider="expired",
            access_token="expired-token",
            expires_at=datetime.now() - timedelta(days=1),
        )
        asyncio.run(temp_store.save(expired_token))

        # 만료된 토큰은 None
        token = temp_store.get_valid_token("expired")
        assert token is None

    def test_has_valid_token(self, temp_store, sample_token):
        """동기 버전: 유효한 토큰 존재 여부"""
        import asyncio

        asyncio.run(temp_store.save(sample_token))

        assert temp_store.has_valid_token("test") is True
        assert temp_store.has_valid_token("nonexistent") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
