# LLM Workflow Integration Plan

> GPT/Gemini를 /auto PDCA 워크플로우(Phase 0-5)에 통합하는 계획

**Version**: 1.0.0
**Status**: PLAN_READY
**Date**: 2026-02-17
**Complexity**: HEAVY (5/5)

---

## 1. 설계 원칙

### 1.1 Claude 오케스트레이터 역할 유지 (불변)

Claude Code는 파일 I/O, Git, Bash, Agent Teams, Phase 전환 등 대체 불가 역할을 수행한다.
GPT/Gemini는 **읽기 전용 자문역** 또는 **초안 생성기**로만 투입하며, 최종 판단과 실행은 항상 Claude가 수행한다.

### 1.2 기존 Ultimate Debate 엔진 재사용

`engine.py`의 `UltimateDebate` 클래스와 `BaseAIClient` 인터페이스(analyze/review/debate)를 그대로 활용한다.
신규 클래스 생성 대신 기존 `OpenAIClient`, `GeminiClient`를 Phase별 어댑터로 래핑한다.

### 1.3 점진적 도입 (Tier 1 먼저)

Tier 1(높은 ROI, 읽기 전용)을 먼저 구현하고, 안정화 후 Tier 2로 확장한다.

---

## 2. Phase별 GPT/Gemini 삽입 설계

### Phase 1: PLAN

| Step | 현재 | 통합 후 | 투입 LLM | 역할 |
|------|------|---------|----------|------|
| 1.0 문서 탐색 | explore(haiku) x2 | explore(haiku) x2 + **Gemini 대규모 분석** | **Gemini** | 1M 컨텍스트로 전체 코드베이스/문서 한번에 분석. explore가 놓치는 cross-file 관계 보완 |
| 1.2 계획 수립 | planner(sonnet) 또는 ralplan | planner + **GPT 구조적 계획 리뷰** | **GPT** | planner 산출물을 GPT가 리뷰하여 누락된 단계/위험 요소 보완 |

**호출 패턴 (Phase 1.0)**:
```python
# 기존 explore 병렬 실행 (변경 없음)
Task(subagent_type="oh-my-claudecode:explore", name="doc-analyst", ...)
Task(subagent_type="oh-my-claudecode:explore", name="issue-analyst", ...)

# 추가: Gemini 대규모 문서 분석 (병렬)
gemini = GeminiClient("gemini-2.5-flash")
await gemini.ensure_authenticated()
gemini_analysis = await gemini.analyze(
    task=f"프로젝트 전체 구조 분석: {task_description}",
    context={"scope": "full_codebase", "files": file_list}
)
# 결과를 plan context에 병합
```

**호출 패턴 (Phase 1.2)**:
```python
# 기존 planner 실행 (변경 없음)
Task(subagent_type="oh-my-claudecode:planner", name="planner", ...)
# planner 완료 대기

# 추가: GPT가 계획 리뷰
gpt = OpenAIClient("gpt-5.2-codex")
await gpt.ensure_authenticated()
gpt_review = await gpt.review(
    task=task_description,
    peer_analysis={"analysis": plan_content, "conclusion": plan_summary},
    own_analysis={}  # GPT 자체 분석 없이 리뷰만
)
# disagreement_points가 있으면 planner에 피드백 → 계획 보강
```

### Phase 2: DESIGN (Tier 2)

| Step | 현재 | 통합 후 | 투입 LLM | 역할 |
|------|------|---------|----------|------|
| 설계 문서 | executor(sonnet) | executor + **GPT+Gemini 설계 리뷰** | **GPT+Gemini** | API/인터페이스 설계를 다관점 리뷰 |

**호출 패턴**:
```python
# 기존 executor 설계 완료 후
# Ultimate Debate 엔진으로 설계 리뷰 토론
debate = UltimateDebate(
    task=f"설계 리뷰: {design_content[:2000]}",
    include_claude_self=True,
    max_rounds=2,
    consensus_threshold=0.7
)
debate.register_ai_client("gpt", gpt_client)
debate.register_ai_client("gemini", gemini_client)
debate.set_claude_analysis({
    "analysis": "Claude의 설계 검증 결과",
    "conclusion": "...",
    "confidence": 0.85
})
review_result = await debate.run()
# disputed_items가 있으면 설계 수정
```

### Phase 3: DO (Tier 2)

| Step | 현재 | 통합 후 | 투입 LLM | 역할 |
|------|------|---------|----------|------|
| 구현 | executor/Ralph | executor/Ralph + **GPT 코드 초안** | **GPT** | 반복적 코드 생성 가속 (Claude가 최종 적용) |

**호출 패턴**:
```python
# GPT에 코드 초안 요청 (복잡한 함수 단위)
gpt_draft = await gpt_client.analyze(
    task=f"다음 함수를 Python으로 구현하세요: {function_spec}",
    context={"design": design_doc, "existing_code": related_code}
)
# Claude(executor)가 GPT 초안을 검토 → 수정 → 적용
# GPT 초안은 참고용, 최종 Write는 반드시 Claude executor가 수행
```

**주의**: GPT는 파일 I/O 권한이 없다. 생성된 코드는 Claude executor가 검증 후 Write 도구로 적용한다.

### Phase 4: CHECK (Tier 1 - 최우선)

| Step | 현재 | 통합 후 | 투입 LLM | 역할 |
|------|------|---------|----------|------|
| 4.2 검증 | architect(sonnet) 순차 | architect + **GPT+Gemini 다관점 검증** | **GPT+Gemini** | 읽기 전용 코드 리뷰, 버그/보안 취약점 탐지 |

**이것이 최고 ROI 투입 지점이다.** 이유:
1. 읽기 전용 (파일 수정 없음) → 위험도 최소
2. 3가지 관점(Claude/GPT/Gemini)으로 검증 품질 대폭 향상
3. 기존 Ultimate Debate 엔진을 그대로 재사용 가능

**호출 패턴**:
```python
# Step 4.1: UltraQA (기존 유지)
Skill(skill="oh-my-claudecode:ultraqa")

# Step 4.2: 3AI 다관점 검증 (Ultimate Debate 엔진 활용)
debate = UltimateDebate(
    task=f"코드 검증: {implementation_summary}",
    include_claude_self=True,
    max_rounds=3,
    consensus_threshold=0.8
)
debate.register_ai_client("gpt", gpt_client)
debate.register_ai_client("gemini", gemini_client)

# Claude(architect)의 검증 결과를 자체 분석으로 설정
debate.set_claude_analysis({
    "analysis": architect_verification_result,
    "conclusion": "APPROVE" or "REJECT",
    "confidence": 0.9,
    "key_points": ["검증 포인트 1", "검증 포인트 2"]
})

consensus = await debate.run()

# 합의 결과에 따라 판정
if consensus["consensus_percentage"] >= 0.8:
    # 3AI 모두 승인 → APPROVE
    verification_result = "APPROVE"
elif consensus["disputed_items"]:
    # 불일치 항목 → Claude가 최종 판단
    verification_result = claude_final_judgment(consensus["disputed_items"])
```

### Phase 5: ACT (Tier 2)

| Step | 현재 | 통합 후 | 투입 LLM | 역할 |
|------|------|---------|----------|------|
| 보고서 | report-generator(haiku) | report-generator + **Gemini 요약** | **Gemini** | 대규모 토론 결과/코드 변경사항 요약 |

**호출 패턴**:
```python
# 기존 report-generator 병렬로 Gemini 요약 요청
gemini_summary = await gemini_client.analyze(
    task="다음 PDCA 사이클 결과를 요약하세요",
    context={"phases": all_phase_results, "changes": file_changes}
)
# report-generator 산출물에 Gemini 요약 섹션 추가
```

---

## 3. 구현 우선순위

### Tier 1 (즉시 구현 - 1~2주)

| 순번 | 대상 | 예상 효과 | 구현 난이도 |
|:----:|------|----------|:----------:|
| 1 | **Phase 4.2 다관점 검증** | 검증 품질 3배 향상, 버그 탈루 감소 | 낮음 (엔진 재사용) |
| 2 | **Phase 1.0 Gemini 대규모 분석** | cross-file 관계 발견율 향상 | 낮음 (analyze 호출) |
| 3 | **Phase 1.2 GPT 계획 리뷰** | 계획 완성도 향상 | 낮음 (review 호출) |

### Tier 2 (안정화 후 - 3~4주)

| 순번 | 대상 | 예상 효과 | 구현 난이도 |
|:----:|------|----------|:----------:|
| 4 | **Phase 2 설계 토론** | 설계 품질 향상 | 중간 (debate.run) |
| 5 | **Phase 3 GPT 코드 초안** | 코딩 속도 향상 | 중간 (초안 검증 필요) |
| 6 | **Phase 5 Gemini 요약** | 보고서 품질 향상 | 낮음 (analyze 호출) |

---

## 4. 구체적 코드 변경 파일 목록

### 신규 생성 파일

| 파일 | 역할 |
|------|------|
| `src/ultimate_debate/workflow/__init__.py` | 워크플로우 통합 모듈 패키지 |
| `src/ultimate_debate/workflow/phase_advisor.py` | Phase별 GPT/Gemini 자문 어댑터. `advise_plan()`, `advise_design()`, `verify_code()`, `summarize_result()` |
| `src/ultimate_debate/workflow/client_pool.py` | GPT/Gemini 클라이언트 풀 관리. 인증 상태 캐싱, 장애 시 graceful degradation |
| `tests/test_workflow/test_phase_advisor.py` | phase_advisor 단위 테스트 |
| `tests/test_workflow/test_client_pool.py` | client_pool 단위 테스트 |

### 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `.claude/skills/auto/SKILL.md` | Phase 1.0, 1.2, 4.2에 GPT/Gemini 투입 지시 추가 |
| `.claude/skills/auto/REFERENCE.md` | 3AI 검증 워크플로우 상세 기술 |
| `src/ultimate_debate/engine.py` | `run_verification()` 메서드 추가 (Phase 4.2 전용 축약 워크플로우) |
| `pyproject.toml` | workflow extras 추가 (선택적 의존성) |

### 변경 없음 (재사용만)

| 파일 | 이유 |
|------|------|
| `src/ultimate_debate/clients/base.py` | BaseAIClient 인터페이스 그대로 사용 |
| `src/ultimate_debate/clients/openai_client.py` | 기존 analyze/review/debate 그대로 호출 |
| `src/ultimate_debate/clients/gemini_client.py` | 기존 analyze/review/debate 그대로 호출 |
| `src/ultimate_debate/consensus/protocol.py` | SHA-256 합의 체커 그대로 사용 |

---

## 5. 핵심 신규 모듈 설계

### 5.1 PhaseAdvisor (workflow/phase_advisor.py)

```python
class PhaseAdvisor:
    """Phase별 GPT/Gemini 자문 어댑터.

    각 PDCA Phase에서 외부 LLM을 자문역으로 투입.
    실패 시 graceful degradation (자문 없이 진행).
    """

    def __init__(self, client_pool: ClientPool):
        self.pool = client_pool

    async def analyze_codebase(self, task: str, file_list: list[str]) -> dict:
        """Phase 1.0: Gemini 대규모 코드베이스 분석"""
        gemini = await self.pool.get_client("gemini")
        if not gemini:
            return {"skipped": True, "reason": "Gemini unavailable"}
        return await gemini.analyze(task, context={"files": file_list})

    async def review_plan(self, task: str, plan_content: str) -> dict:
        """Phase 1.2: GPT 계획 리뷰"""
        gpt = await self.pool.get_client("gpt")
        if not gpt:
            return {"skipped": True, "reason": "GPT unavailable"}
        return await gpt.review(task, {"analysis": plan_content}, {})

    async def verify_implementation(
        self, task: str, code_summary: str, claude_verdict: dict
    ) -> dict:
        """Phase 4.2: 3AI 다관점 검증 (Ultimate Debate 엔진)"""
        debate = UltimateDebate(
            task=f"코드 검증: {task}",
            include_claude_self=True,
            max_rounds=2,
            consensus_threshold=0.8
        )

        gpt = await self.pool.get_client("gpt")
        gemini = await self.pool.get_client("gemini")

        if gpt:
            debate.register_ai_client("gpt", gpt)
        if gemini:
            debate.register_ai_client("gemini", gemini)

        debate.set_claude_analysis(claude_verdict)
        return await debate.run()

    async def summarize_results(self, task: str, results: dict) -> dict:
        """Phase 5: Gemini 결과 요약"""
        gemini = await self.pool.get_client("gemini")
        if not gemini:
            return {"skipped": True, "reason": "Gemini unavailable"}
        return await gemini.analyze(
            f"PDCA 결과 요약: {task}", context=results
        )
```

### 5.2 ClientPool (workflow/client_pool.py)

```python
class ClientPool:
    """GPT/Gemini 클라이언트 풀.

    인증 상태 캐싱, 장애 시 graceful degradation.
    인증 실패한 클라이언트는 None 반환 (자문 스킵).
    """

    def __init__(self):
        self._clients: dict[str, BaseAIClient] = {}
        self._auth_status: dict[str, bool] = {}

    async def initialize(self, models: list[str] | None = None):
        """클라이언트 초기화 및 인증.

        인증 실패 시 해당 LLM은 비활성화 (워크플로우 중단 없음).
        """
        models = models or ["gpt", "gemini"]
        for model in models:
            try:
                if model == "gpt":
                    client = OpenAIClient("gpt-5.2-codex")
                elif model == "gemini":
                    client = GeminiClient("gemini-2.5-flash")
                else:
                    continue
                await client.ensure_authenticated()
                self._clients[model] = client
                self._auth_status[model] = True
            except Exception as e:
                logger.warning(f"{model} authentication failed: {e}")
                self._auth_status[model] = False

    async def get_client(self, model: str) -> BaseAIClient | None:
        """클라이언트 반환. 인증 실패 시 None."""
        if not self._auth_status.get(model):
            return None
        return self._clients.get(model)

    @property
    def available_models(self) -> list[str]:
        return [m for m, ok in self._auth_status.items() if ok]
```

### 5.3 engine.py 추가 메서드

```python
# UltimateDebate 클래스에 추가
async def run_verification(self) -> dict[str, Any]:
    """Phase 4.2 전용 축약 워크플로우.

    전체 5-phase 대신 analyze → consensus check만 수행.
    검증 목적이므로 debate round 없이 1회 분석 후 합의 판정.
    """
    analyses = await self.run_parallel_analysis()
    self.consensus_result = self.consensus_checker.check_consensus(
        list(analyses.values())
    )
    return {
        "status": self.consensus_result.status,
        "consensus_percentage": self.consensus_result.consensus_percentage,
        "agreed_items": self.consensus_result.agreed_items,
        "disputed_items": self.consensus_result.disputed_items,
        "analyses": {k: v.get("conclusion", "") for k, v in analyses.items()},
    }
```

---

## 6. 비용/속도 트레이드오프

### Tier 1 투입 지점

| 투입 지점 | 추가 API 호출 | 추가 지연 (예상) | ROI |
|-----------|:------------:|:--------------:|:---:|
| Phase 4.2 검증 | GPT 1회 + Gemini 1회 | +15~30초 | **최고** - 버그 조기 발견으로 후속 수정 비용 절감 |
| Phase 1.0 분석 | Gemini 1회 | +10~20초 | 높음 - 전체 구조 파악으로 계획 품질 향상 |
| Phase 1.2 리뷰 | GPT 1회 | +10~15초 | 높음 - 계획 누락 방지 |

### Tier 2 투입 지점

| 투입 지점 | 추가 API 호출 | 추가 지연 (예상) | ROI |
|-----------|:------------:|:--------------:|:---:|
| Phase 2 설계 | GPT 1~3회 + Gemini 1~3회 | +30~90초 | 중간 - 설계 품질 향상, debate round 비용 |
| Phase 3 초안 | GPT 1~5회 | +30~60초 | 중간 - 코딩 가속, 검증 비용 추가 |
| Phase 5 요약 | Gemini 1회 | +10~20초 | 낮음 - 보고서 품질만 향상 |

### 비용 모드 라우팅

| PDCA 모드 | 외부 LLM 투입 |
|-----------|--------------|
| LIGHT (0-1) | **없음** (Claude만, 기존과 동일) |
| STANDARD (2-3) | Phase 4.2만 (Tier 1 #1) |
| HEAVY (4-5) | Tier 1 전체 + Tier 2 선택적 |

`--eco` 옵션 시 외부 LLM 투입 전면 스킵.

---

## 7. 위험 요소 및 대응

### 7.1 할루시네이션

| LLM | 할루시네이션 위험 | 대응 |
|-----|:----------------:|------|
| GPT | 중간 (64K+ 토큰 시 정확도 저하) | 입력 컨텍스트 32K 이하로 제한, 결론만 추출 |
| Gemini | 높음 (Flash 91%) | Pro 모델 사용, 코드 검증은 반드시 Claude가 최종 판단 |
| Claude | 낮음 (SWE-bench 최고) | 오케스트레이터이자 최종 판정자 역할 유지 |

**핵심 원칙**: GPT/Gemini 결과는 항상 **참고용**. 최종 APPROVE/REJECT는 Claude architect가 판정.

### 7.2 인증 만료

| 시나리오 | 대응 |
|---------|------|
| GPT 토큰 만료 (401) | `_max_auth_retries=1` 자동 재인증 → 실패 시 자문 스킵 |
| Gemini 토큰 만료 (401) | 동일 로직 → 실패 시 자문 스킵 |
| 양쪽 모두 실패 | Claude 단독 진행 (기존 워크플로우와 동일) |

**ClientPool의 graceful degradation**: 인증 실패한 LLM은 `get_client()`가 `None` 반환.
`PhaseAdvisor`는 `None`이면 자문을 스킵하고 `{"skipped": True}` 반환.
워크플로우는 절대 중단되지 않는다.

### 7.3 API 장애/타임아웃

| 시나리오 | 대응 |
|---------|------|
| API 응답 지연 (>30초) | httpx timeout 120초 (기존) → 타임아웃 시 자문 스킵 |
| API 500/503 | 1회 재시도 → 실패 시 자문 스킵 |
| JSON 파싱 실패 | 기존 fallback 로직 (raw content 반환) 유지 |

### 7.4 컨텍스트 크기 초과

| LLM | 컨텍스트 한도 | 대응 |
|-----|:-----------:|------|
| GPT | ~128K (64K 이상 정확도 저하) | 입력을 32K 이하로 청킹, 핵심 부분만 전달 |
| Gemini | ~1M | 대규모 분석에 활용, 청킹 불필요 |
| Claude | Agent Teams 기반 | 기존 context spike 방지 패턴 유지 |

---

## 8. SKILL.md 수정 설계 (Phase 4.2 예시)

```markdown
### Phase 4: CHECK (UltraQA + 3AI 검증)

**Step 4.2**: 검증 (순차 teammate + 3AI 다관점 검증)

| 모드 | 실행 |
|------|------|
| LIGHT | architect teammate (sonnet) — APPROVE/REJECT만 |
| STANDARD | architect + **GPT/Gemini 다관점 검증** (sonnet) 순차 |
| HEAVY | architect + **3AI Ultimate Debate** + gap-detector + code-analyzer (opus) 순차 |

```python
# STANDARD/HEAVY: 3AI 다관점 검증
from ultimate_debate.workflow.phase_advisor import PhaseAdvisor
from ultimate_debate.workflow.client_pool import ClientPool

pool = ClientPool()
await pool.initialize()  # GPT/Gemini 인증 (실패 시 스킵)
advisor = PhaseAdvisor(pool)

# architect 검증 완료 후, 3AI 추가 검증
verification = await advisor.verify_implementation(
    task=task_description,
    code_summary=implementation_summary,
    claude_verdict=architect_result
)

# 합의율 80% 이상이면 APPROVE
if verification["consensus_percentage"] >= 0.8:
    final_verdict = "APPROVE"
else:
    # 불일치 항목은 Claude가 최종 판단
    final_verdict = resolve_disputes(verification["disputed_items"])
```
```

---

## 9. 테스트 전략

### TDD 순서 (Red-Green-Refactor)

| 순번 | 테스트 파일 | 테스트 내용 |
|:----:|-----------|-----------|
| 1 | `tests/test_workflow/test_client_pool.py` | ClientPool 초기화, 인증 실패 graceful degradation, get_client None 반환 |
| 2 | `tests/test_workflow/test_phase_advisor.py` | PhaseAdvisor 각 메서드, LLM 미가용 시 스킵, verify_implementation debate 통합 |
| 3 | `tests/test_engine.py` (추가) | `run_verification()` 축약 워크플로우 |

### Mock 전략

모든 테스트는 실제 API 호출 없이 mock으로 수행:
- `OpenAIClient._call_api` → mock JSON 응답
- `GeminiClient._call_api` → mock JSON 응답
- `ensure_authenticated` → mock True 반환

---

## 10. 구현 로드맵

### Week 1: 기반 구축

1. `workflow/client_pool.py` TDD 구현
2. `workflow/phase_advisor.py` TDD 구현 (verify_implementation만)
3. `engine.py`에 `run_verification()` 추가
4. Phase 4.2 통합 테스트

### Week 2: Tier 1 완성

5. PhaseAdvisor.analyze_codebase() 구현 (Phase 1.0)
6. PhaseAdvisor.review_plan() 구현 (Phase 1.2)
7. SKILL.md, REFERENCE.md 업데이트
8. 통합 테스트 + 실제 인증 E2E

### Week 3-4: Tier 2 (선택적)

9. Phase 2 설계 토론
10. Phase 3 GPT 코드 초안
11. Phase 5 Gemini 요약
12. 전체 PDCA 사이클 E2E 테스트

---

## 부록: 의사결정 흐름도

```
/auto "작업" 시작
    │
    ├─ Phase 0: 팀 생성 + 복잡도 판단
    │
    ├─ Phase 1: PLAN
    │   ├─ [기존] explore x2 병렬
    │   ├─ [신규] Gemini 대규모 분석 (HEAVY만, 병렬)
    │   ├─ [기존] planner/ralplan
    │   └─ [신규] GPT 계획 리뷰 (HEAVY만, 순차)
    │
    ├─ Phase 2: DESIGN
    │   ├─ [기존] executor 설계
    │   └─ [신규] 3AI 설계 토론 (HEAVY + Tier 2)
    │
    ├─ Phase 3: DO
    │   ├─ [기존] executor/Ralph
    │   └─ [신규] GPT 코드 초안 (HEAVY + Tier 2)
    │
    ├─ Phase 4: CHECK
    │   ├─ [기존] UltraQA
    │   ├─ [기존] architect 검증
    │   ├─ [신규] 3AI 다관점 검증 (STANDARD/HEAVY)  ← 최우선 구현
    │   │   ├─ GPT 코드 리뷰
    │   │   ├─ Gemini 전체 구조 검증
    │   │   ├─ Claude architect 최종 판정
    │   │   └─ consensus >= 80% → APPROVE
    │   └─ [기존] gap-detector, code-analyzer (STANDARD/HEAVY)
    │
    └─ Phase 5: ACT
        ├─ [기존] report-generator
        └─ [신규] Gemini 결과 요약 (HEAVY + Tier 2)
```
