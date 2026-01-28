"""Test custom authentication exceptions."""
import pytest

from ultimate_debate.auth.exceptions import (
    AuthenticationError,
    TokenExpiredError,
    TokenNotFoundError,
    RetryLimitExceededError,
    OAuthError,
)


class TestAuthExceptions:
    """인증 예외 클래스 테스트."""

    def test_authentication_error_is_exception(self):
        """AuthenticationError가 Exception 상속."""
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("Test error")

    def test_authentication_error_message(self):
        """에러 메시지 포함 확인."""
        try:
            raise AuthenticationError("Custom message")
        except AuthenticationError as e:
            assert "Custom message" in str(e)

    def test_authentication_error_with_provider(self):
        """provider 정보 포함 확인."""
        err = AuthenticationError("Test", provider="openai")
        assert err.provider == "openai"

    def test_token_expired_error_inherits_auth_error(self):
        """TokenExpiredError가 AuthenticationError 상속."""
        with pytest.raises(AuthenticationError):
            raise TokenExpiredError("Token expired")

    def test_token_not_found_error_inherits_auth_error(self):
        """TokenNotFoundError가 AuthenticationError 상속."""
        with pytest.raises(AuthenticationError):
            raise TokenNotFoundError("Token not found")

    def test_retry_limit_exceeded_error_inherits_auth_error(self):
        """RetryLimitExceededError가 AuthenticationError 상속."""
        with pytest.raises(AuthenticationError):
            raise RetryLimitExceededError("Retry limit")

    def test_retry_limit_exceeded_has_retry_info(self):
        """RetryLimitExceededError에 재시도 정보 포함."""
        err = RetryLimitExceededError("Failed", max_retries=3, attempts=3)
        assert err.max_retries == 3
        assert err.attempts == 3

    def test_retry_limit_exceeded_with_provider(self):
        """RetryLimitExceededError에 provider 정보 포함."""
        err = RetryLimitExceededError(
            "Failed",
            max_retries=2,
            attempts=2,
            provider="google"
        )
        assert err.provider == "google"

    def test_oauth_error_inherits_auth_error(self):
        """OAuthError가 AuthenticationError 상속."""
        with pytest.raises(AuthenticationError):
            raise OAuthError("OAuth failed")

    def test_oauth_error_with_error_code(self):
        """OAuthError에 error_code 정보 포함."""
        err = OAuthError("OAuth failed", error_code="invalid_grant")
        assert err.error_code == "invalid_grant"

    def test_oauth_error_with_provider(self):
        """OAuthError에 provider 정보 포함."""
        err = OAuthError("OAuth failed", provider="openai")
        assert err.provider == "openai"

    def test_exception_hierarchy(self):
        """예외 계층 구조 확인."""
        # 모든 커스텀 예외는 AuthenticationError 상속
        assert issubclass(TokenExpiredError, AuthenticationError)
        assert issubclass(TokenNotFoundError, AuthenticationError)
        assert issubclass(RetryLimitExceededError, AuthenticationError)
        assert issubclass(OAuthError, AuthenticationError)

        # AuthenticationError는 Exception 상속
        assert issubclass(AuthenticationError, Exception)
