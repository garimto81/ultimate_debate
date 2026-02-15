# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 개요

Ultimate Debate는 여러 AI 모델(Claude, GPT, Gemini) 간의 토론을 통해 합의를 도출하는 Multi-AI Consensus Engine. Claude Code 자체가 오케스트레이터이자 참여자로 동작하며, 외부 AI(GPT, Gemini)는 Browser OAuth로 인증하여 API 호출.

## 빌드 및 테스트

```bash
# 설치
uv pip install -e C:\claude\ultimate-debate
uv pip install -e "C:\claude\ultimate-debate[dev]"       # pytest, ruff
uv pip install -e "C:\claude\ultimate-debate[secure]"     # keyring (토큰 저장)

# 린트
ruff check C:\claude\ultimate-debate\src\ --fix

# 테스트 (개별 파일 권장 - 전체 실행 시 120초 초과 위험)
pytest C:\claude\ultimate-debate\tests\test_engine.py -v
pytest C:\claude\ultimate-debate\tests\test_auth\test_token_store.py -v
pytest C:\claude\ultimate-debate\tests\test_engine.py::test_debate_run -v
```

## 아키텍처

### 핵심 설계 원칙: Claude는 클라이언트가 아닌 오케스트레이터

```
Claude Code ← 이미 Claude → API 호출 불필요 (순환 방지)
    │
    ├─ set_claude_analysis()  → 직접 분석 참여 (include_claude_self=True)
    ├─ register_ai_client("gpt", ...)   → 외부 GPT 등록
    └─ register_ai_client("gemini", ...) → 외부 Gemini 등록

❌ register_ai_client("claude", ...) → ValueError!
```

ClaudeClient는 의도적으로 제거됨. Claude Code 자체가 Claude이므로 API 호출 대신 직접 분석 수행.

### 5-Phase 토론 워크플로우

```
Phase 1: Parallel Analysis    → asyncio.gather()로 모든 AI 병렬 분석
Phase 2: Consensus Check      → SHA-256 해시 비교 (정규화 후)
    ├─ ≥80% → FULL_CONSENSUS → Phase 5 (종료)
    ├─ 50~80% → PARTIAL_CONSENSUS → Phase 3
    └─ <50% → NO_CONSENSUS → Phase 4
Phase 3: Cross Review         → 상호 리뷰 (agreement/disagreement 점수)
Phase 4: Debate Round         → 반박/양보 기반 토론 (max_rounds까지 반복)
Phase 5: Final Strategy       → FINAL.md 생성
```

### 핵심 모듈

| 모듈 | 역할 |
|------|------|
| `engine.py` | 메인 오케스트레이터, 5-Phase 실행, 모델 버전 보존 |
| `clients/base.py` | BaseAIClient ABC (analyze/review/debate) |
| `clients/openai_client.py` | Codex CLI API (`chatgpt.com/backend-api/codex`), 스트리밍 필수 |
| `clients/gemini_client.py` | Code Assist / Vertex AI / Google AI 3-mode 지원 |
| `consensus/protocol.py` | SHA-256 해시 기반 합의 체커, ConsensusResult dataclass |
| `consensus/tracker.py` | 수렴 추적기 (CONVERGING/DIVERGING/STABLE 트렌드) |
| `comparison/semantic.py` | TF-IDF cosine similarity 비교 |
| `comparison/hash.py` | SHA-256 해시 비교 |
| `storage/context_manager.py` | MD 파일 기반 토론 결과 저장 |
| `storage/chunker.py` | LoadLevel 기반 점진적 로딩 (METADATA→SUMMARY→CONCLUSION→FULL) |
| `strategies/base.py` | 전략 패턴 인터페이스 (Normal만 구현, 나머지 stub) |

### AI 클라이언트 인터페이스 (BaseAIClient)

모든 메서드는 async:
- `analyze(task, context)` → `{analysis, conclusion, confidence, model_version}`
- `review(task, peer_analysis, own_analysis)` → `{feedback, agreement_points, disagreement_points}`
- `debate(task, own_position, opposing_views)` → `{updated_position, rebuttals, concessions}`

### OpenAI Codex API 주의사항

- `stream=True` 필수 (Codex API 요구사항)
- role은 `"developer"` 사용 (system 아님)
- SSE 이벤트: `response.output_text.delta`, `response.completed`
- 401 시 1회 자동 재인증 후 재시도 (`_max_auth_retries = 1`)

### Gemini 3-Mode 지원

| 모드 | 엔드포인트 | 프로젝트 ID |
|------|----------|------------|
| Code Assist (기본) | `cloudcode-pa.googleapis.com/v1internal` | 자동 발견 |
| Vertex AI | `{location}-aiplatform.googleapis.com` | 필수 |
| Google AI | `generativelanguage.googleapis.com/v1beta` | 불필요 |

Gemini CLI 토큰 자동 재사용: `~/.gemini/oauth_creds.json`

### 점진적 로딩 (ChunkManager)

MD 파일에 HTML 주석 마커로 청크 구분:

| LoadLevel | 크기 | 내용 |
|-----------|------|------|
| METADATA (0) | ~100B | task_id, status, timestamp |
| SUMMARY (1) | ~300B | + summary, consensus % |
| CONCLUSION (2) | ~800B | + conclusions, agreed_items |
| FULL (3) | ~4000B | + 전체 분석 내용 |

### 컨텍스트 저장 구조

```
.claude/debates/{task_id}/
├── TASK.md                    # 초기 태스크
├── FINAL.md                   # 최종 결과
└── round_00/
    ├── claude.md / gpt.md / gemini.md   # 각 AI 분석
    ├── CONSENSUS.md                      # 합의 결과
    ├── reviews/                          # 상호 리뷰 (모델간)
    └── debates/                          # 토론 내용
```

## 인증 시스템

### 인증 정책 (CRITICAL)

**API 키 사용 절대 금지.** Browser OAuth만 허용 (구독 기반 무제한 사용).

```bash
# ✅ Browser OAuth 로그인
/ai-login openai    # ChatGPT Plus/Pro
/ai-login google    # Google OAuth
```

### 인증 아키텍처

| 컴포넌트 | 역할 |
|----------|------|
| `auth/providers/openai_provider.py` | OpenAI Device Code + PKCE 인증 |
| `auth/providers/google_provider.py` | Google OAuth (Gemini CLI 토큰 재사용) |
| `auth/storage/token_store.py` | keyring → 파일 fallback (OS별 경로) |
| `auth/flows/browser_oauth.py` | 브라우저 OAuth 플로우 (PKCE) |
| `auth/flows/device_code.py` | Device Code 플로우 (RFC 8628) |

### 토큰 저장 경로

| OS | Primary | Fallback |
|----|---------|----------|
| Windows | DPAPI (keyring) | `~/.config/claude-code/ai-auth/` |
| macOS | Keychain | `~/Library/Application Support/claude-code/ai-auth/` |
| Linux | libsecret | `~/.config/claude-code/ai-auth/` |

### 예외 계층

```
AuthenticationError
├── TokenExpiredError
├── TokenNotFoundError
├── RetryLimitExceededError (max_retries, attempts, provider)
└── OAuthError (error_code, provider)
```

## 테스트 구조

| 파일 | 범위 |
|------|------|
| `tests/test_engine.py` | 엔진 통합 (mock debate, claude self, consensus, 3AI) |
| `tests/test_auth/test_providers.py` | OpenAI/Google OAuth 플로우 |
| `tests/test_auth/test_token_store.py` | keyring + 파일 fallback |
| `tests/test_auth/test_browser_oauth.py` | PKCE + authorization code |
| `tests/test_auth/test_device_code.py` | RFC 8628 device code |
| `tests/test_auth/test_gemini_cli_token.py` | Gemini CLI 토큰 재사용 |
| `tests/test_auth/test_concurrent_auth.py` | 병렬 인증 처리 |
| `tests/test_auth/test_retry_*.py` | 재시도 로직 |

## 주요 패턴

- **Async First**: 모든 외부 호출은 async. 병렬 분석은 `asyncio.gather()` 사용
- **모델 버전 보존**: API 응답의 실제 모델 버전을 `model_version` 필드에 보존 (등록 키와 별도)
- **Auth Retry**: 401 시 1회 자동 재인증 후 재시도, 이후 `RetryLimitExceededError`
- **전략 패턴**: Normal만 구현 (pass-through). Mediated, ScopeReduced, PerspectiveShift는 stub
- **Python 3.12+**: `str | None` union 문법, modern async/await 사용
