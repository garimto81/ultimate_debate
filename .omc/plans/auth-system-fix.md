# Auth System Fix Plan

## Summary

Browser OAuth 인증 시스템의 4가지 주요 문제점(ClaudeClient 불완전 인증, 401 재인증 무한 루프, Gemini CLI 토큰 미사용, 동시 인증 경쟁 조건)을 수정하여 안정적인 Multi-AI 토론 시스템을 구현합니다.

## Acceptance Criteria

- [ ] ClaudeClient가 Claude Code 토큰을 안정적으로 획득하거나, 실패 시 명확한 에러 메시지 제공
- [ ] OpenAI/Gemini 클라이언트의 401 재인증 시 최대 1회 재시도 후 실패 처리
- [ ] Gemini 클라이언트가 Gemini CLI 토큰(~/.gemini/oauth_creds.json)을 우선 사용
- [ ] 동시 인증 요청 시 race condition 없이 안전하게 처리
- [ ] 모든 수정에 대한 단위 테스트 존재 (TDD)
- [ ] 기존 인터페이스 하위 호환성 유지

## Implementation Steps

### Phase 1: 401 재인증 무한 루프 수정 (HIGH PRIORITY)

**Files**:
- `src/ultimate_debate/clients/openai_client.py`
- `src/ultimate_debate/clients/gemini_client.py`
- `src/ultimate_debate/clients/claude_client.py`

**Problem Analysis**:
- `openai_client.py:162-165`: 401 발생 시 `ensure_authenticated()` 호출 후 재귀 호출하는데, 재인증도 401 반환하면 무한 루프
- `gemini_client.py:253-256`: 동일한 패턴
- `claude_client.py:157-164`: 동일한 패턴

**Tasks**:
1. [TEST FIRST] 401 반복 시 무한 루프 방지 테스트 작성
   - `tests/test_auth/test_retry_loop.py` 생성
   - 401 반복 응답 시 최대 1회 재시도 후 예외 발생 검증
2. `_call_api` 메서드에 `_retry_count` 인스턴스 변수 추가
3. 재인증 시도 시 카운터 증가, 성공 시 리셋
4. 카운터 >= 1 이면 `AuthenticationError` 발생

**Acceptance Criteria**:
- 401 응답 2회 연속 시 `AuthenticationError` 발생
- 정상 응답 후 카운터 리셋 확인

---

### Phase 2: Gemini CLI 토큰 재사용 (MEDIUM PRIORITY)

**Files**:
- `src/ultimate_debate/clients/gemini_client.py`
- `src/ultimate_debate/auth/providers/google_provider.py`

**Problem Analysis**:
- `google_provider.py:25-74`에 `try_import_gemini_cli_token()` 함수가 정의되어 있으나 사용되지 않음
- `gemini_client.py`는 항상 새 로그인을 시도

**Tasks**:
1. [TEST FIRST] Gemini CLI 토큰 재사용 테스트 작성
   - `tests/test_auth/test_gemini_cli_token.py` 생성
   - `~/.gemini/oauth_creds.json` 존재 시 토큰 재사용 검증
   - 토큰 만료 시 새 로그인으로 fallback 검증
2. `GeminiClient.ensure_authenticated()`에서 `try_import_gemini_cli_token()` 호출 추가
   - 저장된 토큰 확인 후, Gemini CLI 토큰 확인 순서
3. Gemini CLI 토큰 발견 시 TokenStore에 저장 (다음 세션용)

**Acceptance Criteria**:
- `~/.gemini/oauth_creds.json` 존재 시 브라우저 로그인 없이 인증 성공
- CLI 토큰 만료 시 정상적으로 브라우저 로그인 진행

---

### Phase 3: 동시 인증 경쟁 조건 수정 (MEDIUM PRIORITY)

**Files**:
- `src/ultimate_debate/auth/flows/browser_oauth.py`

**Problem Analysis**:
- `OAuthCallbackHandler` 클래스 변수(`auth_code`, `error`, `state`)가 공유됨
- 여러 인증 요청이 동시에 진행되면 데이터가 섞일 수 있음

**Tasks**:
1. [TEST FIRST] 동시 인증 요청 격리 테스트 작성
   - `tests/test_auth/test_concurrent_auth.py` 생성
   - 2개의 동시 인증 요청이 서로 간섭하지 않음 검증
2. `BrowserOAuth`에 인스턴스별 콜백 저장소 도입
   - `_callback_result: dict` 인스턴스 변수 추가
   - 각 인증 세션에 고유 ID 부여
3. `OAuthCallbackHandler`가 세션 ID로 결과 격리
   - `state` 파라미터를 세션 ID로 활용

**Acceptance Criteria**:
- 동시 2개 인증 요청이 독립적으로 완료
- 각 요청이 자신의 토큰만 수신

---

### Phase 4: ClaudeClient 인증 개선 (HIGH PRIORITY)

**Files**:
- `src/ultimate_debate/clients/claude_client.py`

**Problem Analysis**:
- `_get_claude_code_token()` (line 70-110)이 여러 경로를 추측으로 검색
- Claude Code 토큰 형식/위치가 공식 문서화되지 않아 실패 가능성 높음
- 실패 시 사용자에게 명확한 안내 없이 `False` 반환

**Tasks**:
1. [TEST FIRST] Claude 토큰 검색 실패 시 명확한 에러 메시지 테스트
   - `tests/test_auth/test_claude_token.py` 생성
   - 토큰 없을 때 의미 있는 에러 메시지 검증
2. `_get_claude_code_token()` 개선
   - 실제 Claude Code 토큰 경로 우선 확인
   - 로깅 추가 (어떤 경로를 시도했는지)
3. `ensure_authenticated()` 실패 시 명확한 안내 메시지
   - "Claude Code가 설치되어 있어야 합니다"
   - "claude /login 명령으로 먼저 로그인하세요"
4. (선택적) Claude API 대신 Claude Code MCP 연동 고려
   - Claude Code가 이미 인증된 상태이므로 직접 API 호출 대신 MCP 활용

**Acceptance Criteria**:
- Claude Code 미설치 환경에서 명확한 에러 메시지
- 토큰 검색 실패 이유가 로그에 기록됨

---

### Phase 5: 에러 타입 통합 및 문서화

**Files**:
- `src/ultimate_debate/auth/exceptions.py` (신규)
- `src/ultimate_debate/clients/base.py`

**Tasks**:
1. [TEST FIRST] 커스텀 예외 클래스 테스트 작성
2. 인증 관련 커스텀 예외 클래스 생성
   - `AuthenticationError`: 인증 실패
   - `TokenExpiredError`: 토큰 만료
   - `RetryLimitExceededError`: 재시도 한도 초과
3. 기존 `ValueError` → 커스텀 예외로 교체

**Acceptance Criteria**:
- 모든 인증 에러가 일관된 예외 타입 사용
- 에러 메시지에 해결 방법 포함

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Claude Code 토큰 경로 변경 | 버전별 경로 매핑 테이블 유지, 환경변수 오버라이드 지원 |
| Gemini CLI 토큰 형식 변경 | 스키마 검증 추가, 실패 시 graceful fallback |
| 동시 인증 시 포트 충돌 | 동적 포트 할당 (이미 구현됨), 세션 격리 추가 |
| 테스트 환경에서 실제 OAuth 불가 | httpx mock 사용, integration test는 별도 마킹 |

---

## Verification Steps

1. **Unit Tests**: `pytest tests/test_auth/ -v`
2. **401 Retry Test**: 401 2회 연속 시 `AuthenticationError` 발생 확인
3. **Gemini CLI Token Test**: mock 파일로 토큰 재사용 검증
4. **Concurrent Auth Test**: 동시 요청 격리 검증
5. **Claude Token Test**: 토큰 없을 때 명확한 에러 메시지 확인
6. **Integration Test** (수동): `/ai-login google` 후 `GeminiClient.analyze()` 호출 성공

---

## Commit Strategy

| Phase | Commit Message |
|-------|----------------|
| Phase 1 | `fix(auth): prevent infinite retry loop on 401 errors` |
| Phase 2 | `feat(gemini): reuse Gemini CLI token from ~/.gemini/` |
| Phase 3 | `fix(oauth): isolate concurrent authentication sessions` |
| Phase 4 | `fix(claude): improve token discovery with clear error messages` |
| Phase 5 | `refactor(auth): introduce custom exception classes` |

---

## Success Criteria

1. **Zero Infinite Loops**: 401 반복 시 최대 2초 내 에러 발생
2. **Token Reuse Working**: Gemini CLI 토큰 존재 시 0초 인증
3. **Concurrent Safety**: 동시 10개 요청에서 race condition 없음
4. **Clear Error Messages**: 모든 실패 케이스에서 해결 방법 제시
5. **Test Coverage**: 신규 코드 80% 이상 커버리지

---

## Dependencies

- Phase 2, 3, 4는 독립적으로 진행 가능
- Phase 5는 Phase 1-4 완료 후 진행 권장
- Phase 1은 가장 긴급 (시스템 무한 루프 위험)

## Estimated Effort

| Phase | Complexity | Time Estimate |
|-------|------------|---------------|
| Phase 1 | LOW | 30분 |
| Phase 2 | MEDIUM | 45분 |
| Phase 3 | MEDIUM | 1시간 |
| Phase 4 | MEDIUM | 45분 |
| Phase 5 | LOW | 30분 |
| **Total** | - | **~3.5시간** |
