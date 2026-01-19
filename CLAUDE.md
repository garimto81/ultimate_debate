# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 개요

Ultimate Debate는 여러 AI 모델(Claude, GPT, Gemini) 간의 토론을 통해 합의를 도출하는 Multi-AI Consensus Engine입니다.

## 빌드 및 테스트

```powershell
# 설치
uv pip install -e .
uv pip install -e ".[dev]"      # 개발 의존성 포함
uv pip install -e ".[secure]"   # keyring 포함 (토큰 저장)

# 린트
ruff check src/ --fix

# 테스트 (개별 파일 권장)
pytest tests/test_engine.py -v
pytest tests/test_auth/test_token_store.py -v

# 전체 테스트 (시간 소요)
pytest tests/ -v
```

## 아키텍처

### 5-Phase 토론 워크플로우

```
Phase 1: Parallel Analysis    → 모든 AI가 독립적으로 분석
Phase 2: Consensus Check      → 해시 비교로 합의 확인
Phase 3: Cross Review         → 50~80% 합의 시 상호 리뷰
Phase 4: Debate Round         → <50% 합의 시 토론 진행
Phase 5: Final Strategy       → 최종 결과 생성 (FINAL.md)
```

### 합의 프로토콜 (consensus/protocol.py)

| 합의율 | 상태 | 다음 액션 |
|--------|------|----------|
| ≥80% | FULL_CONSENSUS | 종료 |
| 50~80% | PARTIAL_CONSENSUS | CROSS_REVIEW |
| <50% | NO_CONSENSUS | DEBATE |

### 핵심 모듈

| 모듈 | 역할 |
|------|------|
| `engine.py` | 메인 오케스트레이터, 5-Phase 실행 |
| `clients/base.py` | AI 클라이언트 인터페이스 (analyze/review/debate) |
| `consensus/protocol.py` | 해시 기반 합의 체커 |
| `comparison/semantic.py` | TF-IDF 유사도 비교 |
| `storage/context_manager.py` | MD 파일 기반 컨텍스트 저장 |
| `strategies/base.py` | 토론 전략 패턴 (Normal/Mediated/Scope Reduced/Perspective Shift) |

### AI 클라이언트 구현

`BaseAIClient`를 상속하여 구현:
- `analyze(task, context)` → 분석 결과 (analysis, conclusion, confidence)
- `review(task, peer_analysis, own_analysis)` → 리뷰 (feedback, agreement_points, disagreement_points)
- `debate(task, own_position, opposing_views)` → 토론 (updated_position, rebuttals, concessions)

### 컨텍스트 저장 구조

토론 결과는 `.claude/debates/{task_id}/`에 MD 파일로 저장:

```
.claude/debates/{task_id}/
├── TASK.md                    # 초기 태스크
├── FINAL.md                   # 최종 결과
└── round_00/
    ├── claude.md              # Claude 분석
    ├── gpt.md                 # GPT 분석
    ├── gemini.md              # Gemini 분석
    ├── CONSENSUS.md           # 합의 결과
    ├── reviews/               # 상호 리뷰
    └── debates/               # 토론 내용
```

## 사용 예시

```python
from ultimate_debate.engine import UltimateDebate
from ultimate_debate.clients.openai_client import OpenAIClient

debate = UltimateDebate(
    task="캐싱 전략 분석",
    max_rounds=5,
    consensus_threshold=0.8
)

# AI 클라이언트 등록
debate.register_ai_client("gpt", OpenAIClient("gpt-4o"))

# 토론 실행
result = await debate.run()
```

## 인증 시스템 (auth/)

Browser OAuth 기반 인증:
- `providers/`: OpenAI, Google 인증 제공자
- `storage/token_store.py`: 토큰 저장소 (keyring 연동)
- `flows/browser_oauth.py`: 브라우저 OAuth 플로우

## 인증 정책 (CRITICAL)

| 규칙 | 설명 |
|------|------|
| **API 키 사용 절대 금지** | OPENAI_API_KEY, GOOGLE_API_KEY 등 API 키 방식 사용 금지 |
| **Browser OAuth만 허용** | Claude Code `/login`과 동일한 브라우저 기반 인증만 사용 |
| **구독 기반 인증** | ChatGPT Plus/Pro, Google 계정 OAuth 사용 |

### 금지 사항

```powershell
# ❌ 절대 금지 - API 키 환경변수 설정
[System.Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-...", "User")
[System.Environment]::SetEnvironmentVariable("GOOGLE_API_KEY", "...", "User")

# ❌ 절대 금지 - API 키 직접 사용
openai.api_key = "sk-..."
```

### 허용 방식

```powershell
# ✅ Browser OAuth 로그인
/ai-login openai    # ChatGPT Plus/Pro 구독 계정
/ai-login google    # Google 계정 OAuth
```

> **이유**: API 키는 사용량 기반 과금. Browser OAuth는 구독료로 무제한 사용.
