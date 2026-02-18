---
name: auto
description: PDCA Orchestrator - 통합 자율 워크플로우 (Agent Teams 단일 패턴)
version: 23.0.0
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
model_preference: sonnet
auto_trigger: true
agents:
  - executor
  - executor-high
  - architect
  - planner
  - critic
  - qa-tester
  - build-fixer
  - security-reviewer
  - designer
  - code-reviewer
  - writer
---

# /auto - PDCA Orchestrator (v23.0)

> **핵심**: `/auto "작업"` = Phase 0-5 PDCA 자동 진행. `/auto` 단독 = 자율 발견 모드. `/work`는 `/auto`로 통합됨.
> **Agent Teams**: 모든 Phase에서 Agent Teams 단일 패턴 사용. Skill() 호출 0개. State 파일 의존 0개 (pdca-status.json은 진행 추적용, stop hook 비연동). 상세: `REFERENCE.md`
> **v23.0 Sonnet 4.6**: 모든 복잡도 모드에서 기본 model="sonnet" (Sonnet 4.6 = Opus-level @ 1/5 cost). `--opus` 시에만 HEAVY 핵심 에이전트 opus 에스컬레이션. Context: 1M tokens (Sonnet 4.6 beta).

---

## 필수 실행 규칙 (CRITICAL)

**이 스킬이 활성화되면 반드시 Phase 0→5 순서로 실행하세요!**

### Phase 0: 옵션 파싱 + 모드 결정 + 팀 생성

| 옵션 | 효과 |
|------|------|
| `--skip-analysis` | Step 1.0 사전 분석 스킵 |
| `--no-issue` | Step 1.3 이슈 연동 스킵 |
| `--strict` | E2E 테스트 1회 실패 즉시 중단 (QA cycle과 무관) |
| `--dry-run` | 판단만 출력, 실행 안함 |
| `--eco` | LIGHT 모드 강제 |
| `--worktree` | feature 전용 worktree 생성 후 해당 경로에서 작업, 완료 시 자동 정리 |
| `--opus` | HEAVY 모드에서 핵심 에이전트를 Opus 4.6으로 에스컬레이션 (기본: Sonnet 4.6) |

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

> **모델 오버라이드**: Sonnet 4.6이 Opus-level 성능을 제공하므로, 모든 복잡도 모드에서 기본 `model="sonnet"`. `--opus` 플래그 시에만 HEAVY의 핵심 에이전트가 opus로 에스컬레이션.

**Step 1.2**: 계획 수립 → `docs/01-plan/{feature}.plan.md` 생성 (Graduated Plan Review)

**LIGHT (0-1점): Planner + Lead Quality Gate**
```
Task(subagent_type="planner", name="planner", team_name="pdca-{feature}",
     model="haiku", prompt="(복잡도: LIGHT {score}/5). docs/01-plan/{feature}.plan.md 생성.
     사용자 확인/인터뷰 단계 건너뛰고 바로 계획 문서를 작성하세요.")
SendMessage(type="message", recipient="planner", content="계획 수립 시작.")
# 완료 대기 → shutdown_request
# Lead Quality Gate: (1) plan 파일 존재+내용 있음, (2) 파일 경로 1개+ 언급
# 미충족 시 Planner 1회 재요청
```

**STANDARD (2-3점): Planner + Critic-Lite 단일 검토**
```
Task(subagent_type="planner", name="planner", team_name="pdca-{feature}",
     model="sonnet", prompt="(복잡도: STANDARD {score}/5). docs/01-plan/{feature}.plan.md 생성.
     사용자 확인/인터뷰 단계 건너뛰세요. Critic-Lite가 검토합니다.")
SendMessage(type="message", recipient="planner", content="계획 수립 시작.")
# 완료 대기 → shutdown_request
# Critic-Lite: Quality Gates 4 검증 (QG1-QG4) — 상세 prompt: REFERENCE.md
Task(subagent_type="critic", name="critic-lite", team_name="pdca-{feature}",
     model="sonnet", prompt="[Critic-Lite] QG1-QG4 검증. VERDICT: APPROVE/REVISE.")
SendMessage(type="message", recipient="critic-lite", content="Plan 검토 시작.")
# REVISE → Planner 1회 수정 → 수정본 수용 (추가 Critic 없음)
```

**HEAVY (4-5점): Planner-Critic Loop (max 5 iterations)** — 상세 prompt: `REFERENCE.md`
```
critic_feedback = ""
Loop (i=1..5):
  1. Planner teammate (sonnet) → 계획 수립 (critic_feedback 반영)
  2. Architect teammate (sonnet) → 기술적 타당성 검증
  3. Critic teammate (sonnet) → Quality Gates 4 (QG1-QG4) + VERDICT: APPROVE/REVISE
  APPROVE → Loop 종료 / REVISE → critic_feedback 업데이트 → 다음 iteration
  5회 초과 → 경고 포함 강제 승인
```

**Step 1.3**: 이슈 연동 (없으면 생성, 있으면 코멘트). `--no-issue`로 스킵 가능.

### Phase 2: DESIGN (설계 문서 생성)

**Plan→Design Gate (STANDARD/HEAVY만)**: 4개 필수 섹션 확인 (배경, 구현 범위, 영향 파일, 위험 요소)

| 모드 | 실행 | 에이전트 |
|------|------|---------|
| LIGHT | **스킵** (Phase 3 직행) | — |
| STANDARD | design-writer teammate | `executor` (sonnet) |
| HEAVY | design-writer teammate | `executor-high` (sonnet, `--opus` 시 opus) |

> **주의**: `architect`는 READ-ONLY (Write 도구 없음). 설계 **문서 생성**에는 executor 계열 사용 필수.

```
# STANDARD 예시 (HEAVY: executor-high + sonnet, --opus 시 opus)
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
| HEAVY | impl-manager teammate (sonnet, `--opus` 시 opus) — 5조건 자체 루프 + 병렬 가능 |

```
# LIGHT: executor teammate 단일 실행
Task(subagent_type="executor", name="executor", team_name="pdca-{feature}",
     model="sonnet", prompt="docs/01-plan/{feature}.plan.md 기반 구현. TDD 필수.")
SendMessage(type="message", recipient="executor", content="구현 시작.")

# STANDARD/HEAVY: impl-manager teammate (5조건 자체 루프) — 상세 prompt: REFERENCE.md
# HEAVY: executor-high subagent_type 사용 (--opus 시 model="opus", 기본 model="sonnet")
Task(subagent_type="executor[-high]", name="impl-manager",
     team_name="pdca-{feature}", model="sonnet",
     prompt="설계 문서 기반 구현. 5조건 자체 루프 (max 10회). 상세 prompt: REFERENCE.md")
SendMessage(type="message", recipient="impl-manager", content="5조건 구현 루프 시작.")
# Lead는 IMPLEMENTATION_COMPLETED 또는 IMPLEMENTATION_FAILED 메시지만 수신
```

impl-manager 5조건: TODO==0, 빌드 성공, 테스트 통과, 에러==0, 자체 코드 리뷰. 상세: `REFERENCE.md`
**Step 3.2**: Architect Verification Gate (STANDARD/HEAVY 필수, LIGHT 스킵)

```
# impl-manager IMPLEMENTATION_COMPLETED 수신 후 (STANDARD/HEAVY만)
Task(subagent_type="architect", name="impl-verifier", team_name="pdca-{feature}",
     model="sonnet", prompt="[Phase 3 Architect Gate] 구현 외부 검증. 상세: REFERENCE.md")
SendMessage(type="message", recipient="impl-verifier", content="구현 검증 시작.")
# VERDICT: APPROVE → Phase 4 진입
# VERDICT: REJECT + DOMAIN → Step 3.3 Domain-Smart Fix
# 2회 REJECT → 사용자 알림 후 Phase 4 진입 허용
```

**Step 3.3**: Domain-Smart Fix Routing (Architect REJECT 시)

| Architect DOMAIN | 에이전트 | 용도 |
|------------------|---------|------|
| UI, component, style | designer | 프론트엔드 수정 |
| build, compile, type | build-fixer | 빌드/타입 에러 |
| test, coverage | executor | 테스트 수정 |
| security | security-reviewer | 보안 이슈 |
| 기타 | executor | 일반 수정 |

```
# Domain-Smart Fix → Architect 재검증 (max 2회)
Task(subagent_type="{domain-agent}", name="domain-fixer", team_name="pdca-{feature}",
     model="sonnet", prompt="Architect 거부 사유: {rejection}. DOMAIN: {domain}. 수정 실행.")
# 수정 완료 → Step 3.2 Architect 재검증
```

### Phase 4: CHECK (QA Runner + Architect 진단 + 검증 + E2E + TDD)

**Step 4.1**: QA 사이클 — QA Runner + Architect 진단 + Domain-Smart Fix

```
# LIGHT: QA 1회 실행. 실패 시 보고만 (STANDARD 자동 승격 검토). 진단/수정 없음.
Task(subagent_type="qa-tester", name="qa-runner", team_name="pdca-{feature}",
     model="sonnet", prompt="6종 QA 실행. 상세: REFERENCE.md")
# QA_PASSED → Step 4.2 / QA_FAILED → 실패 보고 + STANDARD 승격 조건 확인

# STANDARD/HEAVY: QA 사이클 (max STANDARD:3 / HEAVY:5)
failure_history = []
Loop (max_cycles):
  # A. QA Runner teammate
  Task(subagent_type="qa-tester", name="qa-runner-{i}", team_name="pdca-{feature}",
       model="sonnet", prompt="6종 QA 실행. 상세: REFERENCE.md")
  # QA_PASSED → Step 4.2 / QA_FAILED → B
  # B. Architect Root Cause 진단 (MANDATORY)
  Task(subagent_type="architect", name="diagnostician-{i}", team_name="pdca-{feature}",
       model="sonnet", prompt="QA 실패 root cause 진단. 출력: DIAGNOSIS + FIX_GUIDE + DOMAIN.")
  # C. Domain-Smart Fix
  Task(subagent_type="{domain-agent}", name="fixer-{i}", team_name="pdca-{feature}",
       model="sonnet", prompt="진단 기반 수정: {DIAGNOSIS}. 지침: {FIX_GUIDE}.")
```

**4종 Exit Conditions:**

| 우선순위 | 조건 | 처리 |
|:--------:|------|------|
| 1 | Environment Error | 즉시 중단 + 환경 문제 보고 |
| 2 | Same Failure 3x | 조기 종료 + root cause 보고 |
| 3 | Max Cycles 도달 | 미해결 이슈 보고 |
| 4 | Goal Met | Step 4.2 이중 검증 진입 |

QA Runner 6종 goal, Architect 진단 prompt, Domain routing 상세: `REFERENCE.md`

**Step 4.2**: 검증 (순차 teammate — context spike 방지)

| 모드 | 실행 |
|------|------|
| LIGHT | architect teammate (sonnet) — APPROVE/REJECT만 |
| STANDARD | architect → code-reviewer (sonnet) 순차 |
| HEAVY | architect → code-reviewer (sonnet, `--opus` 시 opus) 순차 |

```
# LIGHT: architect만 / STANDARD/HEAVY: architect → gap-detector → code-analyzer 순차
Task(subagent_type="architect", name="verifier", team_name="pdca-{feature}",
     model="sonnet", prompt="구현이 Plan/Design 요구사항과 일치하는지 검증. APPROVE/REJECT 판정.")
SendMessage(type="message", recipient="verifier", content="검증 시작.")
# 완료 대기 → shutdown_request → (STANDARD/HEAVY: code-reviewer 순차 spawn)
# code-reviewer prompt에 Vercel BP 규칙 동적 주입 (React/Next.js 프로젝트 시) — 상세: REFERENCE.md
```

> architect는 READ-ONLY이므로 **검증/판정에 적합**. 파일 생성에는 사용 금지.

**Step 4.3**: E2E — Playwright 존재 시만. 실패 시 `/debug`. `--strict` → 1회 실패 중단.
**Step 4.4**: TDD 커버리지 — 신규 80% 이상, 전체 감소 불가.

### Phase 5: ACT (결과 기반 자동 실행 + 팀 정리)

| Check 결과 | 자동 실행 |
|-----------|----------|
| gap < 90% | executor teammate로 갭 개선 (최대 5회) → Phase 4 재실행 |
| gap >= 90% + APPROVE | writer teammate → `docs/04-report/` |
| Architect REJECT | executor teammate (수정) → Phase 4 재실행 |

> **Phase 4↔5 루프 가드**: Phase 5→Phase 4 재진입 누적 최대 3회. 초과 시 미해결 이슈 보고 후 종료.

```
# gap >= 90% + APPROVE → 보고서 생성 후 팀 정리
Task(subagent_type="writer", name="reporter", team_name="pdca-{feature}",
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
| **Phase 1** | haiku 계획 + Lead QG | sonnet 계획 + Critic-Lite | Planner-Critic Loop (sonnet) |
| **Phase 2** | 스킵 | executor (sonnet) 설계 | executor-high (sonnet) 설계 |
| **Phase 3.1** | executor (sonnet) | impl-manager (sonnet) | impl-manager (sonnet) + 병렬 |
| **Phase 3.2** | — | Architect Gate | Architect Gate |
| **Phase 4.1** | QA 1회 (보고만) | QA 3회 + 진단 | QA 5회 + 진단 |
| **Phase 4.2** | Architect (sonnet) | Architect + code-reviewer (sonnet) | Architect + code-reviewer (sonnet) |
| **Phase 5** | writer (haiku) + TeamDelete | writer (haiku) + TeamDelete | writer (haiku) + TeamDelete |

> **Sonnet 4.6 통합 (v23.0)**: Sonnet 4.6이 Opus-level 성능을 1/5 가격에 제공하므로, 모든 모드에서 기본 model="sonnet" 사용. `--opus` 플래그 시에만 HEAVY의 핵심 에이전트(design-writer, impl-manager, architect, code-reviewer)가 opus로 에스컬레이션.

**자동 승격**: LIGHT→STANDARD: 빌드 실패 2회 또는 영향 파일 5개+. STANDARD→HEAVY: QA 3사이클 초과 또는 영향 파일 5개+.

## 자율 발견 모드 (`/auto` 단독 실행 — 작업 인수 없음)

Tier 0 CONTEXT → 1 EXPLICIT → 2 URGENT → 3 WORK → 4 SUPPORT → 5 AUTONOMOUS 순서로 발견. 상세: `REFERENCE.md`

## 세션 관리

`/auto status` (상태 확인) / `/auto stop` (중지+TeamDelete) / `/auto resume` (재개+TeamCreate). 상세: `REFERENCE.md`

## 금지 사항

옵션 실패 시 조용히 스킵 / Architect 검증 없이 완료 선언 / 증거 없이 "완료됨" 주장 / 테스트 삭제로 문제 해결 / **TeamDelete 없이 세션 종료** / **architect 에이전트로 파일 생성 시도** / **Skill() 호출 금지 (Agent Teams 단일 패턴)** / **`--opus` 없이 model="opus" 사용 금지** / **코드 블록 상세, 옵션 워크플로우, impl-manager prompt, Vercel BP**: `REFERENCE.md`
