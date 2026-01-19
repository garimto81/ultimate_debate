"""Provider 테스트"""

import pytest
from datetime import datetime, timedelta

from ultimate_debate.auth.providers.base import AuthToken


class TestAuthToken:
    """AuthToken 테스트"""

    def test_is_expired_false(self):
        """만료되지 않은 토큰"""
        token = AuthToken(
            provider="test",
            access_token="test-token",
            expires_at=datetime.now() + timedelta(days=30)
        )
        assert token.is_expired() is False

    def test_is_expired_true(self):
        """만료된 토큰"""
        token = AuthToken(
            provider="test",
            access_token="test-token",
            expires_at=datetime.now() - timedelta(days=1)
        )
        assert token.is_expired() is True

    def test_is_expired_no_expiry(self):
        """만료 시간 없는 토큰 (무기한)"""
        token = AuthToken(
            provider="test",
            access_token="test-token",
            expires_at=None
        )
        assert token.is_expired() is False

    def test_expires_in_days(self):
        """만료까지 남은 일수"""
        token = AuthToken(
            provider="test",
            access_token="test-token",
            expires_at=datetime.now() + timedelta(days=7, hours=12)
        )
        # 7일 또는 8일 (시간대에 따라)
        days = token.expires_in_days()
        assert days in [7, 8]

    def test_to_dict(self):
        """딕셔너리 변환"""
        token = AuthToken(
            provider="openai",
            access_token="test-token",
            refresh_token="refresh-token",
            expires_at=datetime(2026, 1, 25, 12, 0, 0),
            scopes=["chat", "models"]
        )
        data = token.to_dict()

        assert data["provider"] == "openai"
        assert data["access_token"] == "test-token"
        assert data["refresh_token"] == "refresh-token"
        assert data["scopes"] == ["chat", "models"]

    def test_from_dict(self):
        """딕셔너리에서 생성"""
        data = {
            "provider": "google",
            "access_token": "google-token",
            "refresh_token": "google-refresh",
            "expires_at": "2026-01-25T12:00:00",
            "scopes": ["email"]
        }
        token = AuthToken.from_dict(data)

        assert token.provider == "google"
        assert token.access_token == "google-token"
        assert token.expires_at == datetime(2026, 1, 25, 12, 0, 0)

    def test_roundtrip(self):
        """to_dict → from_dict 왕복 테스트"""
        original = AuthToken(
            provider="test",
            access_token="token123",
            refresh_token="refresh456",
            expires_at=datetime(2026, 2, 1, 10, 30, 0),
            scopes=["read", "write"]
        )

        data = original.to_dict()
        restored = AuthToken.from_dict(data)

        assert restored.provider == original.provider
        assert restored.access_token == original.access_token
        assert restored.refresh_token == original.refresh_token
        assert restored.expires_at == original.expires_at
        assert restored.scopes == original.scopes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
