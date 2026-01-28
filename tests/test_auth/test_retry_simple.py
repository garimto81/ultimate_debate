"""Simple test for retry counter functionality."""
import pytest
from ultimate_debate.clients.openai_client import OpenAIClient
from ultimate_debate.clients.gemini_client import GeminiClient
from ultimate_debate.clients.claude_client import ClaudeClient


class TestRetryCounterBasics:
    """Basic retry counter tests without async complexity."""

    def test_openai_client_has_retry_counter(self):
        """OpenAI 클라이언트가 재시도 카운터를 가지고 있는지 확인."""
        client = OpenAIClient("gpt-4o")
        assert hasattr(client, '_auth_retry_count')
        assert hasattr(client, '_max_auth_retries')
        assert client._auth_retry_count == 0
        assert client._max_auth_retries == 1

    def test_gemini_client_has_retry_counter(self):
        """Gemini 클라이언트가 재시도 카운터를 가지고 있는지 확인."""
        client = GeminiClient("gemini-pro")
        assert hasattr(client, '_auth_retry_count')
        assert hasattr(client, '_max_auth_retries')
        assert client._auth_retry_count == 0
        assert client._max_auth_retries == 1

    def test_claude_client_has_retry_counter(self):
        """Claude 클라이언트가 재시도 카운터를 가지고 있는지 확인."""
        client = ClaudeClient("claude-3-5-sonnet")
        assert hasattr(client, '_auth_retry_count')
        assert hasattr(client, '_max_auth_retries')
        assert client._auth_retry_count == 0
        assert client._max_auth_retries == 1

    def test_retry_counter_can_increment(self):
        """재시도 카운터를 증가시킬 수 있는지 확인."""
        client = OpenAIClient("gpt-4o")
        client._auth_retry_count += 1
        assert client._auth_retry_count == 1
        assert client._auth_retry_count >= client._max_auth_retries

    def test_retry_counter_can_reset(self):
        """재시도 카운터를 리셋할 수 있는지 확인."""
        client = OpenAIClient("gpt-4o")
        client._auth_retry_count = 5
        client._auth_retry_count = 0
        assert client._auth_retry_count == 0
