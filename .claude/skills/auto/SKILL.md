---
name: auto
description: PDCA Orchestrator - 통합 자율 워크플로우 (Agent Teams 단일 패턴)
version: 21.0.0
triggers:
  keywords:
    - "/auto"
    - "auto"
    - "autopilot"
    - "ulw"
    - "ultrawork"
    - "ralph"
    - "/work"
    - "work"
model_preference: opus
auto_trigger: true
agents:
  - executor
  - executor-high
  - architect
  - planner
  - critic
  - gap-detector
  - pdca-iterator
  - code-analyzer
  - report-generator
---

# /auto - PDCA Orchestrator (v21.0)

> **핵심**: `/auto "작업"` = Phase 0-5 PDCA 자동 진행. `/auto` 단독 = 자율 발견 모드. `/work`는 `/auto`로 통합됨.
> **Agent Teams**: 모든 Phase에서 Agent Teams 단일 패턴 사용. Skill() 호출 0개. State 파일 의존 0개. 상세: `REFERENCE.md`

---

## 필수 실행 규칙 (CRITICAL)

**이 스킬이 활성화되면 반드시 Phase 0→5 순서로 실행하세요!**

### Phase 0: 옵션 파싱 + 모드 결정 + 팀 생성

| 옵션 | 효과 |
|------|------|
| `--skip-analysis` | Step 1.0 사전 분석 스킵 |
| `--no-issue` | Step 1.3 이슈 연동 스킵 |
| `--strict` | E2E 1회 실패 시 중단 |
| `--dry-run` | 판단만 출력, 실행 안함 |
| `--eco` | LIGHT 모드 강제 |
| `--worktree` | feature 전용 worktree 생성 후 해당 경로에서 작업, 완료 시 자동 정리 |

**팀 생성 (MANDATORY):** `TeamCreate(team_name="pdca-{feature}")`

### Phase 1: PLAN (사전 분석 → 복잡도 판단 → 계획 수립 → 이슈 연동)

**Step 1.0**: 병렬 explore(haiku) x2 — 문서 탐색 + 이슈 탐색. `--skip-analysis`로 스킵 가능.

```
Task(subagent_type="explore", name="doc-analyst", team_name="pdca-{feature}",
     model="haiku", prompt="docs/, .claude/ 내 관련 문서 탐색. 결과 5줄 이내 요약.")
Task(subagent_type="explore", name="issue-analyst", team_name="pdca-{feature}",
     model="haiku", prompt="gh issue list로 유사 이슈 탐색. 결과 5줄 이내 요약.")
# 완료 대기 → 각각 SendMessage(type="shutdown_request", recipient="...")
```

**Step 1.1: 복잡도 판단 (5점 만점)** — 상세 기준: `REFERENCE.md`

| 점수 | 모드 | 라우팅 |
|:----:|:----:|--------|
| 0-1 | LIGHT | planner teammate (haiku) |
| 2-3 | STANDARD | planner teammate (sonnet) |
| 4-5 | HEAVY | Planner-Critic Loop (max 5 iter) |

**Step 1.2**: 계획 수립 → `docs/01-plan/{feature}.plan.md` 생성

```
# LIGHT: model="haiku" / STANDARD: model="sonnet"
Task(subagent_type="planner", name="planner", team_name="pdca-{feature}",
     model="sonnet", prompt="(복잡도: STANDARD {score}/5). docs/01-plan/{feature}.plan.md 생성.")
SendMessage(type="message", recipient="planner", content="계획 수립 시작.")
```

**HEAVY (4-5점): Planner-Critic Loop (max 5 iterations)** — 상세 prompt: `REFERENCE.md`

```
critic_feedback = ""
Loop (i=1..5):
  1. Planner teammate (sonnet) → 계획 수립 (critic_feedback 반영)
  2. Architect teammate (sonnet) → 기술적 타당성 검증
  3. Critic teammate (sonnet) → VERDICT: APPROVE / VERDICT: REVISE
  APPROVE → Loop 종료 / REVISE → critic_feedback 업데이트 → 다음 iteration
  5회 초과 → 경고 포함 강제 승인
```

**Step 1.3**: 이슈 연동 (없으면 생성, 있으면 코멘트). `--no-issue`로 스킵 가능.

### Phase 2: DESIGN (설계 문서 생성)

**Plan→Design Gate**: 4개 필수 섹션 확인 (배경, 구현 범위, 영향 파일, 위험 요소)

| 모드 | 실행 | 에이전트 |
|------|------|---------|
| LIGHT | **스킵** (Phase 3 직행) | — |
| STANDARD | design-writer teammate | `executor` (sonnet) |
| HEAVY | design-writer teammate | `executor-high` (opus) |

> **주의**: `architect`는 READ-ONLY (Write 도구 없음). 설계 **문서 생성**에는 executor 계열 사용 필수.

```
# STANDARD 예시 (HEAVY: executor-high + opus)
Task(subagent_type="executor", name="design-writer", team_name="pdca-{feature}",
     model="sonnet", prompt="docs/01-plan/{feature}.plan.md 참조. 설계 문서 작성. 출력: docs/02-design/{feature}.design.md")
SendMessage(type="message", recipient="design-writer", content="설계 문서 생성 요청.")
```

**산출물**: `docs/02-design/{feature}.design.md` (STANDARD/HEAVY만)

### Phase 3: DO (옵션 라우팅 + 구현)

**Step 3.0**: 옵션 처리 (구현 진입 전 실행)

| 옵션 | 스킬 | 옵션 | 스킬 |
|------|------|------|------|
| `--gdocs` | `prd-sync` | `--slack <채널>` | Slack 분석 |
| `--mockup [파일]` | `mockup-hybrid` | `--gmail` | Gmail 분석 |
| `--debate` | `ultimate-debate` | `--daily` | `daily` |
| `--research` | `research` | `--interactive` | Phase별 승인 |

**옵션 실패 시**: 에러 출력, **절대 조용히 스킵 금지**. 상세: `REFERENCE.md`

**Step 3.1**: 구현 실행

| 모드 | 실행 |
|------|------|
| LIGHT | executor teammate (sonnet) — 단일 실행 |
| STANDARD | impl-manager teammate (sonnet) — 5조건 자체 루프 |
| HEAVY | impl-manager teammate (opus) — 5조건 자체 루프 + 병렬 가능 |

```
# LIGHT: executor teammate 단일 실행
Task(subagent_type="executor", name="executor", team_name="pdca-{feature}",
     model="sonnet", prompt="docs/01-plan/{feature}.plan.md 기반 구현. TDD 필수.")
SendMessage(type="message", recipient="executor", content="구현 시작.")

# STANDARD/HEAVY: impl-manager teammate (5조건 자체 루프) — 상세 prompt: REFERENCE.md
Task(subagent_type="executor[-high]", name="impl-manager",
     team_name="pdca-{feature}", model="sonnet|opus",
     prompt="설계 문서 기반 구현. 5조건 자체 루프 (max 10회). 상세 prompt: REFERENCE.md")
SendMessage(type="message", recipient="impl-manager", content="5조건 구현 루프 시작.")
# Lead는 IMPLEMENTATION_COMPLETED 또는 IMPLEMENTATION_FAILED 메시지만 수신

# HEAVY 병렬 실행: Lead가 독립 작업 2개+ 판단 시 병렬 impl-manager spawn
```

impl-manager 5조건: TODO==0, 빌드 성공, 테스트 통과, 에러==0, 자체 코드 리뷰. 상세: `REFERENCE.md`

### Phase 4: CHECK (QA 사이클 + 검증 + E2E + TDD)

**Step 4.1**: QA 사이클 — Lead 직접 실행 + Executor 수정 위임

```
failure_history = []
Loop (max LIGHT:1 / STANDARD:3 / HEAVY:5):
  Lead 직접 실행: ruff check src/ --fix && pytest tests/ -v && npm run build (해당 시)
  실패 시:
    failure_history에 실패 내용 추가
    동일 실패 3회 연속 → QA 조기 종료 + 사용자 알림
    Task(subagent_type="executor", name="fixer-{i}",
         team_name="pdca-{feature}", model="sonnet",
         prompt="QA 실패 수정: {failure_details}")
    SendMessage → 완료 대기 → shutdown_request
  모든 검사 통과 → Step 4.2
```

Same Failure 3x 조기 종료, failure_history 관리 상세: `REFERENCE.md`

**Step 4.2**: 검증 (순차 teammate — context spike 방지)

| 모드 | 실행 |
|------|------|
| LIGHT | architect teammate (sonnet) — APPROVE/REJECT만 |
| STANDARD | architect → gap-detector → code-analyzer (sonnet) 순차 |
| HEAVY | architect → gap-detector → code-analyzer (opus) 순차 |

```
# LIGHT: architect만 / STANDARD/HEAVY: architect → gap-detector → code-analyzer 순차
Task(subagent_type="architect", name="verifier", team_name="pdca-{feature}",
     model="sonnet", prompt="구현이 Plan/Design 요구사항과 일치하는지 검증. APPROVE/REJECT 판정.")
SendMessage(type="message", recipient="verifier", content="검증 시작.")
# 완료 대기 → shutdown_request → (STANDARD/HEAVY: gap-detector, code-analyzer 순차 spawn)
# code-analyzer prompt에 Vercel BP 규칙 동적 주입 (React/Next.js 프로젝트 시) — 상세: REFERENCE.md
```

> architect는 READ-ONLY이므로 **검증/판정에 적합**. 파일 생성에는 사용 금지.

**Step 4.3**: E2E — Playwright 존재 시만. 실패 시 `/debug`. `--strict` → 1회 실패 중단.
**Step 4.4**: TDD 커버리지 — 신규 80% 이상, 전체 감소 불가.

### Phase 5: ACT (결과 기반 자동 실행 + 팀 정리)

| Check 결과 | 자동 실행 |
|-----------|----------|
| gap < 90% | pdca-iterator teammate (sonnet, 최대 5회) → Phase 4 재실행 |
| gap >= 90% + APPROVE | report-generator teammate (haiku) → `docs/04-report/` |
| Architect REJECT | executor teammate (sonnet) → Phase 4 재실행 |

```
# gap >= 90% + APPROVE → 보고서 생성 후 팀 정리
Task(subagent_type="bkit:report-generator", name="reporter", team_name="pdca-{feature}",
     model="haiku", prompt="PDCA 완료 보고서 생성. 출력: docs/04-report/{feature}.report.md")
SendMessage(type="message", recipient="reporter", content="보고서 생성 요청.")
# 완료 대기 → shutdown_request → TeamDelete()
```

**팀 정리 (MANDATORY):** `TeamDelete()`

---

## 복잡도 기반 모드 분기

| | LIGHT (0-1) | STANDARD (2-3) | HEAVY (4-5) |
|------|:-----------:|:--------------:|:-----------:|
| **Phase 0** | TeamCreate | TeamCreate | TeamCreate |
| **Phase 1** | haiku 분석 + haiku 계획 | haiku 분석 + sonnet 계획 | haiku 분석 + Planner-Critic Loop |
| **Phase 2** | 스킵 | executor (sonnet) 설계 | executor-high (opus) 설계 |
| **Phase 3** | executor (sonnet) | impl-manager (sonnet) | impl-manager (opus) + 병렬 |
| **Phase 4** | Lead QA + Architect검증 | Lead QA + 이중검증 | Lead QA + 이중검증 + E2E |
| **Phase 5** | haiku 보고서 + TeamDelete | sonnet 보고서 + TeamDelete | 완전 보고서 + TeamDelete |

**자동 승격**: LIGHT에서 빌드 실패 2회 / QA 3사이클 초과 / 영향 파일 5개+ 시 STANDARD 승격

---

## 자율 발견 모드 (`/auto` 단독 실행 — 작업 인수 없음)

Tier 0 CONTEXT → 1 EXPLICIT → 2 URGENT → 3 WORK → 4 SUPPORT → 5 AUTONOMOUS 순서로 발견. 상세: `REFERENCE.md`

## 세션 관리

`/auto status` (상태 확인) / `/auto stop` (중지+TeamDelete) / `/auto resume` (재개+TeamCreate). 상세: `REFERENCE.md`

## 금지 사항

옵션 실패 시 조용히 스킵 / Architect 검증 없이 완료 선언 / 증거 없이 "완료됨" 주장 / 테스트 삭제로 문제 해결 / **TeamDelete 없이 세션 종료** / **architect 에이전트로 파일 생성 시도** / **Skill() 호출 금지 (Agent Teams 단일 패턴)**

**코드 블록 상세, 옵션 워크플로우, impl-manager prompt 전문, Vercel BP 규칙**: `REFERENCE.md`
