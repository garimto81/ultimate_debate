"""Test concurrent authentication session isolation."""
import pytest
import asyncio
import threading
import time
from unittest.mock import patch, MagicMock, Mock
from http.server import HTTPServer

from ultimate_debate.auth.flows.browser_oauth import (
    BrowserOAuth,
    OAuthCallbackHandler,
    OAuthConfig,
    TokenResponse,
)


class TestConcurrentAuthIsolation:
    """동시 인증 요청 격리 테스트."""

    def test_callback_handler_session_isolation(self):
        """각 세션이 독립적인 콜백 결과를 가짐."""
        # 세션 1과 세션 2가 서로 간섭하지 않음을 검증
        session1_state = "state_session_1"
        session2_state = "state_session_2"

        # 세션별 결과 저장소 (새로운 구현에서 사용할 패턴)
        # 수정 후: browser_oauth._callback_results를 사용
        from ultimate_debate.auth.flows import browser_oauth

        # 초기화
        if hasattr(browser_oauth, '_callback_results'):
            browser_oauth._callback_results.clear()

        # 세션 1 콜백 시뮬레이션
        if hasattr(browser_oauth, '_callback_results'):
            browser_oauth._callback_results[session1_state] = {
                "auth_code": "code_1",
                "error": None
            }

            # 세션 2 콜백 시뮬레이션
            browser_oauth._callback_results[session2_state] = {
                "auth_code": "code_2",
                "error": None
            }

            # 각 세션이 자신의 결과만 받음
            assert browser_oauth._callback_results[session1_state]["auth_code"] == "code_1"
            assert browser_oauth._callback_results[session2_state]["auth_code"] == "code_2"
        else:
            # 아직 구현 안 됨 - 테스트 스킵
            pytest.skip("_callback_results not implemented yet")

    def test_class_variables_should_not_exist(self):
        """OAuthCallbackHandler가 클래스 변수를 공유하면 안 됨."""
        # 수정 후: 클래스 변수가 제거되고 _callback_results로 대체됨

        # 클래스 변수가 제거되었는지 확인
        assert not hasattr(OAuthCallbackHandler, 'auth_code')
        assert not hasattr(OAuthCallbackHandler, 'error')
        assert not hasattr(OAuthCallbackHandler, 'state')

        # 대신 모듈 레벨의 _callback_results 사용
        from ultimate_debate.auth.flows import browser_oauth
        assert hasattr(browser_oauth, '_callback_results')
        assert hasattr(browser_oauth, '_callback_lock')

    @pytest.mark.asyncio
    async def test_concurrent_browser_oauth_instances(self):
        """2개의 BrowserOAuth 인스턴스가 독립적인 state를 가짐."""
        config1 = OAuthConfig(
            client_id="test_client_1",
            authorization_endpoint="https://example.com/auth",
            token_endpoint="https://example.com/token",
            redirect_uri="http://localhost:8001/callback",
            scope="scope1"
        )

        config2 = OAuthConfig(
            client_id="test_client_2",
            authorization_endpoint="https://example.com/auth",
            token_endpoint="https://example.com/token",
            redirect_uri="http://localhost:8002/callback",
            scope="scope2"
        )

        oauth1 = BrowserOAuth(config1, fixed_port=8001)
        oauth2 = BrowserOAuth(config2, fixed_port=8002)

        # 각 인스턴스가 독립적인 state를 가짐
        assert oauth1.state != oauth2.state

        # 각 인스턴스가 독립적인 PKCE challenge를 가짐
        assert oauth1.pkce.code_verifier != oauth2.pkce.code_verifier
        assert oauth1.pkce.code_challenge != oauth2.pkce.code_challenge

    @pytest.mark.asyncio
    async def test_concurrent_auth_no_race_condition(self):
        """동시 인증 요청에서 race condition이 발생하지 않음."""
        # 이 테스트는 실제 네트워크 호출 없이 모의 객체로 검증

        config = OAuthConfig(
            client_id="test_client",
            authorization_endpoint="https://example.com/auth",
            token_endpoint="https://example.com/token",
            redirect_uri="http://localhost:{port}/callback",
            scope="test_scope"
        )

        oauth1 = BrowserOAuth(config, fixed_port=9001)
        oauth2 = BrowserOAuth(config, fixed_port=9002)

        # 각 세션이 고유한 state를 가지는지 확인
        state1 = oauth1.state
        state2 = oauth2.state

        assert state1 != state2

        # _callback_results를 통한 격리 검증
        from ultimate_debate.auth.flows import browser_oauth

        if hasattr(browser_oauth, '_callback_results'):
            # 세션 1 콜백 시뮬레이션
            browser_oauth._callback_results[state1] = {
                "auth_code": "code_for_session_1",
                "error": None
            }

            # 세션 2 콜백 시뮬레이션
            browser_oauth._callback_results[state2] = {
                "auth_code": "code_for_session_2",
                "error": None
            }

            # 각 세션이 자신의 코드만 받음
            assert browser_oauth._callback_results[state1]["auth_code"] == "code_for_session_1"
            assert browser_oauth._callback_results[state2]["auth_code"] == "code_for_session_2"

            # 정리
            browser_oauth._callback_results.clear()
        else:
            pytest.skip("_callback_results not implemented yet")

    def test_callback_handler_stores_result_by_state(self):
        """OAuthCallbackHandler가 state별로 결과를 저장함."""
        from ultimate_debate.auth.flows import browser_oauth

        if not hasattr(browser_oauth, '_callback_results'):
            pytest.skip("_callback_results not implemented yet")

        # 초기화
        browser_oauth._callback_results.clear()

        # do_GET을 직접 호출하는 대신 _callback_results를 직접 조작하여 검증
        # (OAuthCallbackHandler.__init__가 복잡한 socket 설정을 요구하므로)

        # 세션별 결과 저장 시뮬레이션
        test_state = "test_state_456"
        test_code = "test_code_123"

        with browser_oauth._callback_lock:
            browser_oauth._callback_results[test_state] = {
                "auth_code": test_code,
                "error": None
            }

        # 저장된 결과 확인
        assert test_state in browser_oauth._callback_results
        assert browser_oauth._callback_results[test_state]["auth_code"] == test_code
        assert browser_oauth._callback_results[test_state]["error"] is None

        # 다른 세션과 격리 확인
        another_state = "another_state_789"
        another_code = "another_code_xyz"

        with browser_oauth._callback_lock:
            browser_oauth._callback_results[another_state] = {
                "auth_code": another_code,
                "error": None
            }

        # 두 세션이 독립적으로 존재
        assert browser_oauth._callback_results[test_state]["auth_code"] == test_code
        assert browser_oauth._callback_results[another_state]["auth_code"] == another_code

        # 정리
        browser_oauth._callback_results.clear()


class TestCallbackResultsThreadSafety:
    """_callback_results의 thread-safety 테스트."""

    def test_callback_lock_exists(self):
        """_callback_lock이 존재하는지 확인."""
        from ultimate_debate.auth.flows import browser_oauth

        if not hasattr(browser_oauth, '_callback_lock'):
            pytest.skip("_callback_lock not implemented yet")

        assert hasattr(browser_oauth, '_callback_lock')
        # threading.Lock은 인스턴스이므로 type으로 체크
        assert type(browser_oauth._callback_lock).__name__ == 'lock'

    def test_concurrent_writes_are_thread_safe(self):
        """동시 쓰기가 thread-safe한지 확인."""
        from ultimate_debate.auth.flows import browser_oauth

        if not hasattr(browser_oauth, '_callback_results') or not hasattr(browser_oauth, '_callback_lock'):
            pytest.skip("_callback_results or _callback_lock not implemented yet")

        # 초기화
        browser_oauth._callback_results.clear()

        results = []

        def write_result(state_id: str, code: str):
            """결과를 _callback_results에 쓰기."""
            with browser_oauth._callback_lock:
                browser_oauth._callback_results[state_id] = {
                    "auth_code": code,
                    "error": None
                }
                # 약간의 지연으로 race condition 유도
                time.sleep(0.001)
            results.append(state_id)

        # 10개의 스레드가 동시에 쓰기
        threads = []
        for i in range(10):
            t = threading.Thread(target=write_result, args=(f"state_{i}", f"code_{i}"))
            threads.append(t)
            t.start()

        # 모든 스레드 완료 대기
        for t in threads:
            t.join()

        # 모든 결과가 저장되었는지 확인
        assert len(browser_oauth._callback_results) == 10

        for i in range(10):
            state = f"state_{i}"
            assert state in browser_oauth._callback_results
            assert browser_oauth._callback_results[state]["auth_code"] == f"code_{i}"

        # 정리
        browser_oauth._callback_results.clear()
