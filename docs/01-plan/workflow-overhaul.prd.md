# PRD: Ultimate Debate 워크플로우 전면 수정

**Version**: 1.0.0
**Status**: DRAFT
**Date**: 2026-02-18
**Author**: Claude Code (PDCA Lead)

---

## 1. 배경 및 현재 상태

### 1.1 프로젝트 개요

Ultimate Debate는 3개 AI(Claude, GPT, Gemini)가 병렬 분석 → 교차 검토 → 합의 판정 → 재토론을 반복하여 최종 합의안을 도출하는 Multi-AI Consensus Engine이다.

### 1.2 현재 진행 중인 변경 (34 파일, +2324/-569줄)

현재 워크플로우가 전면 수정되고 있으며, 변경은 크게 **4개 영역**으로 분류된다:

| 영역 | 핵심 변경 | 영향 파일 수 | 상태 |
|------|----------|:-----------:|:----:|
| A. 합의 알고리즘 | SHA-256 해시 → Semantic Similarity (TF-IDF) | 2 | 완료 |
| B. 모델 자동 발견 | 로그인 시 최고 성능 모델 자동 선택 | 4 | 완료 |
| C. 워크플로우 통합 | ClientPool + PhaseAdvisor + PDCA 삽입 | 6 | 부분 완료 |
| D. 엔진 안정성 | 실패 추적, 플레이스홀더 필터링, dict 버그 수정 | 3 | 완료 |

### 1.3 변경 상세 분석

#### A. 합의 알고리즘 전환 (consensus/protocol.py)

**Before**: SHA-256 해시 비교 — 결론 문자열이 1글자라도 다르면 불일치 판정
**After**: TF-IDF cosine similarity 클러스터링 — 의미적으로 유사하면 합의 인정

```
기존: "Use Redis for caching" vs "Redis caching recommended" → 불일치 (해시 다름)
변경: 동일 → 합의 인정 (cosine similarity > 0.3)
```

- `SemanticComparator` (이미 `comparison/semantic.py`에 구현) 통합
- `similarity_threshold` 파라미터 추가 (기본값 0.3)
- 클러스터 기반 agreed/disputed 분류

**위험**: threshold 0.3이 너무 관대할 수 있음 → 실 데이터 기반 튜닝 필요

#### B. 모델 자동 발견 (openai_client.py, gemini_client.py)

**OpenAI**:
- `MODEL_CAPABILITY_RANKINGS`: gpt-5.3-codex(100) > gpt-5.2-codex(90) > gpt-5.1-codex(80)
- `ensure_authenticated()` 시 Codex API 프로빙으로 최고 모델 자동 선택
- 기본 모델: gpt-5.2-codex → gpt-5.3-codex 변경

**Gemini**:
- `MODEL_CAPABILITY_RANKINGS`: gemini-2.5-pro(100) > gemini-2.5-flash(80) > gemini-2.0-pro(70)
- Google AI API 모델 리스트 조회 + `generateContent` 지원 모델만 필터
- 기본 모델: gemini-2.5-flash → gemini-2.5-pro 변경
- Session ID 추가 (`uuid.uuid4()`)

**위험**: 모델 발견 실패 시 기존 model_name 유지 (graceful) — 위험 낮음

#### C. 워크플로우 통합 모듈 (신규: `workflow/`)

| 모듈 | 역할 | 상태 |
|------|------|:----:|
| `client_pool.py` | GPT/Gemini 클라이언트 풀 관리, 인증 상태 추적 | 완료 |
| `phase_advisor.py` | Phase별 GPT/Gemini 자문 (1.0, 1.2, 4.2, 5) | 완료 |
| `__init__.py` | 패키지 공개 API | 완료 |

**PhaseAdvisor 매핑**:

| Phase | 메서드 | 투입 LLM | 용도 |
|-------|--------|----------|------|
| 1.0 문서 탐색 | `analyze_codebase()` | Gemini | 1M 컨텍스트 전체 분석 |
| 1.2 계획 수립 | `review_plan()` | GPT | 계획 리뷰, 누락 보완 |
| 4.2 검증 | `verify_implementation()` | GPT+Gemini+Claude | 3AI 다관점 검증 |
| 5 보고서 | `summarize_results()` | Gemini | 결과 요약 |

**미완료 항목**:
- `auto/SKILL.md`에 PhaseAdvisor 호출 지시가 아직 통합되지 않음
- `REFERENCE.md` 업데이트 부분적

#### D. 엔진 안정성 개선 (engine.py)

| 수정 | 변경 내용 |
|------|----------|
| `failed_clients` 추적 | `asyncio.gather(return_exceptions=True)` + 실패 기록 |
| 플레이스홀더 필터링 | `requires_input=True` 리뷰를 합의 체크에서 제외 |
| dict 버그 수정 | `updated_position`이 dict일 때 `["conclusion"]` 추출 |
| 분석 실패 스킵 | 리뷰/토론에서 분석 실패 클라이언트 자동 제외 |

---

## 2. 문제 정의

### 2.1 미해결 구조적 문제

| 문제 | 심각도 | 근본 원인 |
|------|:------:|----------|
| **Mock fallback 여전히 존재** | 높음 | `engine.py:274` — 클라이언트 없으면 `_mock_parallel_analysis()` 자동 호출 |
| **Preflight 검증 없음** | 높음 | `run()` 진입 시 클라이언트 상태 확인 로직 없음 |
| **결과 무결성 검증 없음** | 중간 | 실제 API 응답인지 mock인지 구분 불가 |
| **auto/SKILL.md 미동기화** | 중간 | PhaseAdvisor 코드는 완성됐으나 스킬 지시에 미반영 |
| **ClientPool 재인증 없음** | 중간 | `initialize()` 1회 호출 후 토큰 만료 감지 불가 |
| **테스트 파편화** | 낮음 | test_engine.py, test_workflow/, test_model_discovery.py 분산 |

### 2.2 이전 세션에서 확인된 문제

1. **시뮬레이션 오용**: OMC DELEGATION-FIRST 규칙이 architect 에이전트를 실제 API 대신 호출하게 유도
2. **실제 API 검증 성공**: GPT(gpt-5.3-codex) + Gemini(gemini-2.5-pro) 모두 실제 호출 확인
3. **Gemini 3.0 미지원**: gemini-3.0-* 모델 전부 404 NOT_FOUND

---

## 3. 목표

### 3.1 핵심 목표

1. **실제 API 호출 보장** — Mock fallback 완전 제거, strict mode 도입
2. **Preflight Health Check** — `run()` 진입 전 클라이언트 건강 확인
3. **auto/SKILL.md 동기화** — PhaseAdvisor를 PDCA Phase에 공식 통합
4. **결과 무결성 검증** — API 응답 품질 자동 체크

### 3.2 비목표 (이 PRD 범위 밖)

- Gemini 3.0 지원 (아직 출시 전)
- Tier 2 기능 구현 (Phase 2 설계 토론, Phase 3 코드 초안)
- 새로운 AI 추가 (Llama, Mistral 등)
- OMC 워크플로우 자체 수정

---

## 4. 구현 전략

### 4.1 Phase A: Mock Fallback 제거 + Strict Mode (우선순위 1)

**영향 파일**: `src/ultimate_debate/engine.py`

**변경 1**: `_mock_*` 메서드를 `run()` 에서 제거

```python
# 현재 (engine.py:273-275)
if not analyses:
    return self._mock_parallel_analysis()  # 위험: 무조건 mock 성공

# 변경 후
if not analyses:
    raise NoAvailableClientsError(
        "분석 가능한 AI 클라이언트가 없습니다. "
        "register_ai_client()로 외부 AI를 등록하거나 "
        "include_claude_self=True를 설정하세요."
    )
```

**변경 2**: `strict` 파라미터 추가

```python
class UltimateDebate:
    def __init__(self, ..., strict: bool = False):
        self.strict = strict

    async def run(self):
        if self.strict and not self.ai_clients:
            raise StrictModeError("strict 모드: 외부 AI 필수")
```

**변경 3**: Mock 메서드를 테스트 전용으로 격리

```python
# 기존 _mock_* 메서드는 유지하되 run()에서 호출하지 않음
# tests/conftest.py에서만 사용
```

**테스트**: `test_engine.py`에 NoAvailableClientsError 및 strict mode 테스트 추가

### 4.2 Phase B: Preflight Health Check (우선순위 2)

**영향 파일**: `src/ultimate_debate/workflow/client_pool.py`, `engine.py`

**변경 1**: ClientPool에 `health_check()` 추가

```python
@dataclass
class HealthStatus:
    available: bool
    latency_ms: float = 0.0
    model_version: str = ""
    error: str = ""

class ClientPool:
    async def health_check(self) -> dict[str, HealthStatus]:
        """각 클라이언트의 readiness + liveliness 확인."""
        results = {}
        for model, client in self._clients.items():
            try:
                start = time.monotonic()
                # lightweight ping: 짧은 analyze 호출
                await asyncio.wait_for(
                    client.analyze("health check ping", context={}),
                    timeout=30.0
                )
                latency = (time.monotonic() - start) * 1000
                results[model] = HealthStatus(
                    available=True,
                    latency_ms=latency,
                    model_version=getattr(client, 'discovered_model', client.model_name)
                )
            except Exception as e:
                results[model] = HealthStatus(available=False, error=str(e))
        return results
```

**변경 2**: `run()` 진입 시 preflight 호출

```python
async def run(self):
    # Preflight: 등록된 클라이언트 상태 확인
    for name, client in list(self.ai_clients.items()):
        try:
            await asyncio.wait_for(
                client.ensure_authenticated(),
                timeout=30.0
            )
        except Exception as e:
            logger.warning(f"{name} preflight failed: {e}")
            if self.strict:
                raise
            self.failed_clients[name] = str(e)
            del self.ai_clients[name]
    ...
```

**테스트**: health_check 및 preflight 실패 시나리오

### 4.3 Phase C: 결과 무결성 검증 (우선순위 3)

**영향 파일**: `src/ultimate_debate/engine.py`

```python
def _validate_analysis(self, model: str, result: dict) -> bool:
    """분석 결과가 유효한 API 응답인지 검증."""
    required_fields = ["analysis", "conclusion", "confidence"]
    if not all(k in result for k in required_fields):
        logger.warning(f"{model}: 필수 필드 누락")
        return False

    # 최소 분석 길이 (실제 분석은 최소 50자 이상)
    analysis = result.get("analysis", "")
    if len(analysis) < 50:
        logger.warning(f"{model}: 분석이 너무 짧음 ({len(analysis)}자)")
        return False

    # confidence 범위 검증
    conf = result.get("confidence", 0)
    if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
        logger.warning(f"{model}: confidence 범위 초과 ({conf})")
        return False

    return True
```

**적용 지점**: `run_parallel_analysis()`에서 결과 수신 후 검증

### 4.4 Phase D: auto/SKILL.md 동기화 (우선순위 4)

**영향 파일**: `.claude/skills/auto/SKILL.md`, `.claude/skills/auto/REFERENCE.md`

SKILL.md Phase 4.2에 PhaseAdvisor 호출 지시 추가:

```markdown
**Step 4.2**: 검증 (STANDARD/HEAVY 시 3AI 다관점 검증 추가)

| 모드 | 기존 | 추가 |
|------|------|------|
| LIGHT | architect (sonnet) | 변경 없음 |
| STANDARD | architect → gap-detector | + PhaseAdvisor.verify_implementation() |
| HEAVY | architect → gap-detector → code-analyzer | + PhaseAdvisor.verify_implementation() |

3AI 검증 코드:
\```python
from ultimate_debate.workflow import ClientPool, PhaseAdvisor

pool = ClientPool()
await pool.initialize()
advisor = PhaseAdvisor(pool)

verification = await advisor.verify_implementation(
    task=task_description,
    code_summary=implementation_summary,
    claude_verdict=architect_result
)
await pool.close()
\```
```

---

## 5. 기존 계획과의 관계

### 5.1 기존 계획 문서

| 문서 | 상태 | 이 PRD와의 관계 |
|------|:----:|---------------|
| `llm-workflow-integration.plan.md` | 대부분 구현 | Phase C/D의 기반. Tier 1은 코드 완성, Tier 2는 미착수 |
| `debate-quality-fix.plan.md` | 완료 | 영역 A, D에 해당. 모두 반영됨 |

### 5.2 이 PRD가 추가하는 것

기존 계획에 **없었던** 항목:

1. Mock fallback 제거 + strict mode (이전 세션에서 발견된 시뮬레이션 문제 대응)
2. Preflight health check (liteLLM 패턴 참고)
3. 결과 무결성 검증 (Consilium 패턴 참고)
4. auto/SKILL.md 동기화 (코드와 지시 문서 간 갭)

---

## 6. 구현 우선순위 및 로드맵

| Phase | 항목 | 난이도 | 영향도 | 예상 시간 |
|:-----:|------|:------:|:------:|:---------:|
| A | Mock fallback 제거 + strict mode | 낮음 | 높음 | 30분 |
| B | Preflight health check | 중간 | 높음 | 1시간 |
| C | 결과 무결성 검증 | 낮음 | 중간 | 30분 |
| D | auto/SKILL.md 동기화 | 낮음 | 중간 | 30분 |

**총 예상**: 2.5시간 (TDD 포함)

**구현 순서**: A → B → C → D (의존성 없음, 병렬 가능하나 순차 권장)

---

## 7. 테스트 전략

### 7.1 TDD 순서

| 순번 | 테스트 | 대상 |
|:----:|--------|------|
| 1 | `test_run_raises_without_clients` | Phase A: NoAvailableClientsError |
| 2 | `test_strict_mode_requires_external_ai` | Phase A: strict=True |
| 3 | `test_mock_methods_not_called_in_run` | Phase A: mock 격리 확인 |
| 4 | `test_health_check_all_healthy` | Phase B: 전부 정상 |
| 5 | `test_health_check_partial_failure` | Phase B: 일부 실패 |
| 6 | `test_preflight_removes_dead_clients` | Phase B: 실패 클라이언트 자동 제거 |
| 7 | `test_validate_analysis_rejects_short` | Phase C: 짧은 분석 거부 |
| 8 | `test_validate_analysis_rejects_missing_fields` | Phase C: 필드 누락 거부 |

### 7.2 E2E 검증

`tests/test_workflow/test_e2e_real_api.py`에 추가:
- Test 8: Preflight health check (실제 API)
- Test 9: Strict mode + 실제 API 호출

---

## 8. 위험 요소

| 위험 | 확률 | 영향 | 대응 |
|------|:----:|:----:|------|
| Mock 제거 시 기존 테스트 실패 | 높음 | 중간 | conftest.py에 mock fixture 분리 |
| Preflight 호출이 API 비용 추가 | 낮음 | 낮음 | 구독 기반이므로 무제한 |
| similarity_threshold 0.3이 부적절 | 중간 | 중간 | 실제 토론 데이터로 A/B 테스트 후 조정 |
| auto/SKILL.md 수정 시 다른 워크플로우 영향 | 낮음 | 높음 | Phase별 테스트로 검증 |

---

## 9. 성공 기준

| 기준 | 측정 방법 |
|------|----------|
| Mock fallback이 `run()`에서 절대 호출되지 않음 | 테스트 코드로 검증 |
| 실제 API 미등록 시 명확한 에러 발생 | `NoAvailableClientsError` raise |
| Preflight에서 실패한 클라이언트가 자동 제거됨 | E2E 테스트 |
| 분석 결과가 50자 미만이면 거부됨 | 단위 테스트 |
| auto/SKILL.md가 실제 코드와 100% 동기화 | 수동 검증 |

---

## 10. 부록: 전체 변경 파일 현황

### 완료된 변경 (커밋 대기)

| 파일 | 변경량 | 내용 |
|------|:------:|------|
| `engine.py` | +61 | failed_clients, run_verification, 버그 수정 |
| `consensus/protocol.py` | +75 | SHA-256 → Semantic Similarity |
| `clients/base.py` | +3 | Docstring 수정 |
| `clients/openai_client.py` | +221 | 모델 자동 발견, 랭킹, 기본값 변경 |
| `clients/gemini_client.py` | +370 | 모델 자동 발견, 랭킹, 기본값 변경 |
| `workflow/__init__.py` | 신규 | 패키지 init |
| `workflow/client_pool.py` | 신규 | 클라이언트 풀 관리 |
| `workflow/phase_advisor.py` | 신규 | Phase별 자문 어댑터 |
| `tests/test_engine.py` | +262 | run_verification, 3AI, semantic 테스트 |
| `tests/test_workflow/` | 신규 | ClientPool, PhaseAdvisor, E2E 테스트 |
| `tests/test_model_discovery.py` | 신규 | 모델 자동 발견 테스트 |

### 이 PRD에서 추가할 변경

| 파일 | 변경 | 내용 |
|------|:----:|------|
| `engine.py` | 수정 | Mock fallback 제거, strict mode, preflight, 결과 검증 |
| `workflow/client_pool.py` | 수정 | health_check() 추가 |
| `auto/SKILL.md` | 수정 | PhaseAdvisor 통합 지시 추가 |
| `auto/REFERENCE.md` | 수정 | 3AI 검증 상세 코드 블록 |
| `tests/test_engine.py` | 수정 | strict mode, preflight, 검증 테스트 |
| `tests/test_workflow/test_client_pool.py` | 수정 | health_check 테스트 |
| `tests/test_workflow/test_e2e_real_api.py` | 수정 | preflight, strict E2E |
