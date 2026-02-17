# /auto REFERENCE - Phase 전환 상세 워크플로우 (v21.0)

> **동기화 안내**: 핵심 코드 블록(Tool Call 패턴)은 `SKILL.md`에 인라인. 이 파일은 확장 패턴, 옵션 워크플로우, Gate 조건 상세를 담당합니다. SKILL.md의 인라인 코드 블록을 수정할 경우 이 파일의 해당 섹션도 함께 업데이트하세요.
> **v21.0**: 모든 Phase에서 Agent Teams 단일 패턴 사용. Skill() 호출 0개. State 파일 의존 0개.

---

## Agent Teams 운영 규칙 (v21.0)

**모든 에이전트 호출은 Agent Teams in-process 방식을 사용합니다. Skill() 호출 0개.**

### 팀 라이프사이클

1. **Phase 0**: `TeamCreate(team_name="pdca-{feature}")` — PDCA 시작 시 1회
2. **Phase 1-4**: `Task(name="역할", team_name="pdca-{feature}")` → `SendMessage` → 완료 대기 → `shutdown_request`
3. **Phase 5**: 보고서 생성 후 `TeamDelete()`

### Teammate 운영 규칙

1. **Spawn 시 role name 명시**: `name="doc-analyst"`, `name="verifier"` 등 역할 명확히
2. **Task 할당**: `TaskCreate` → `SendMessage`로 teammate에게 작업 전달
3. **완료 대기**: Mailbox 자동 수신 (Lead가 polling 불필요)
4. **순차 작업**: 이전 teammate `shutdown_request` 완료 후 다음 teammate spawn
5. **병렬 작업**: 독립 작업은 동시 spawn 가능 (Phase 1.0 분석 등)

### Context 분리 장점 (vs 기존 subagent)

| 기존 subagent | Agent Teams |
|--------------|-------------|
| 결과가 Lead context에 합류 → overflow | Mailbox로 전달 → Lead context 보호 |
| foreground 3개 상한 필요 | 제한 없음 (독립 context) |
| "5줄 요약" 강제 | 불필요 |
| compact 실패 위험 | compact 실패 없음 |

---

## Worktree 통합 (`--worktree` 옵션)

### Step 0.1: Worktree 설정 (Phase 0, TeamCreate 직후)

`--worktree` 옵션 지정 시 Phase 0에서 팀 생성 직후 실행:

```bash
# 1. worktree 생성
git worktree add "C:/claude/wt/{feature}" -b "feat/{feature}" main

# 2. .claude junction 생성
cmd /c "mklink /J \"C:\\claude\\wt\\{feature}\\.claude\" \"C:\\claude\\.claude\""

# 3. 검증
git worktree list
ls "C:/claude/wt/{feature}/.claude/commands"
```

성공 확인 후 이후 Phase의 모든 파일 경로에 worktree prefix 적용:
- `docs/01-plan/` → `C:\claude\wt\{feature}\docs\01-plan\`
- 구현 파일 → `C:\claude\wt\{feature}\` 하위

### Teammate Prompt 패턴 (`--worktree` 시)

모든 teammate prompt에 경로 prefix 주입:

```
# 기존
prompt="docs/01-plan/{feature}.plan.md를 참조하여 설계 문서를 작성하세요."

# --worktree 시
prompt="모든 파일은 C:\\claude\\wt\\{feature}\\ 하위에서 작업하세요.
       C:\\claude\\wt\\{feature}\\docs\\01-plan\\{feature}.plan.md를 참조하여 설계 문서를 작성하세요."
```

### Phase 5 Worktree Cleanup (TeamDelete 직전)

`--worktree` 옵션 시 Phase 5 보고서 생성 완료 후, TeamDelete 직전 실행:

```bash
# 1. junction 제거
cmd /c "rmdir \"C:\\claude\\wt\\{feature}\\.claude\""

# 2. worktree 제거
git worktree remove "C:/claude/wt/{feature}"

# 3. 정리
git worktree prune
```

### Agent Teams 병렬 격리 (HEAVY 모드)

HEAVY(4-5점) 시 teammate별 별도 worktree로 완전 격리:

```bash
# Phase 3 병렬 구현 시
git worktree add "C:/claude/wt/{feature}-impl" "feat/{feature}"
git worktree add "C:/claude/wt/{feature}-test" "feat/{feature}"
cmd /c "mklink /J \"C:\\claude\\wt\\{feature}-impl\\.claude\" \"C:\\claude\\.claude\""
cmd /c "mklink /J \"C:\\claude\\wt\\{feature}-test\\.claude\" \"C:\\claude\\.claude\""
```

```
Task(subagent_type="executor", name="impl", team_name="pdca-{feature}",
     model="sonnet", prompt="C:\\claude\\wt\\{feature}-impl\\ 경로에서 구현. 다른 경로 수정 금지.")
Task(subagent_type="executor", name="tester", team_name="pdca-{feature}",
     model="sonnet", prompt="C:\\claude\\wt\\{feature}-test\\ 경로에서 테스트 작성. 다른 경로 수정 금지.")
```

cleanup 시 모든 sub-worktree도 함께 제거.

---

## Phase 1→5 PDCA 전체 흐름

```
Phase 0: TeamCreate("pdca-{feature}")
    |
Phase 1 PLAN → Phase 2 DESIGN → Phase 3 DO → Phase 4 CHECK → Phase 5 ACT
     |              |              |              |              |
     v              v              v              v              v
  계획문서        설계문서       구현(impl-mgr)  QA+이중검증    개선/완료
  (teammates)   (teammate)     (teammates)    (Lead+mates)    |
                                                              v
                                                         TeamDelete()
```

---

## Phase 1: PLAN (사전 분석 → 복잡도 판단 → 계획 수립)

### Step 1.0: 사전 분석 (병렬 Teammates)

```
# 병렬 spawn (독립 작업)
Task(subagent_type="explore", name="doc-analyst", team_name="pdca-{feature}",
     model="haiku", prompt="docs/, .claude/ 내 관련 문서 탐색. 중복 범위 감지 필수. 결과를 5줄 이내로 요약.")

Task(subagent_type="explore", name="issue-analyst", team_name="pdca-{feature}",
     model="haiku", prompt="gh issue list 실행하여 유사 이슈 탐색. 연관 이슈 태깅 필요. 결과를 5줄 이내로 요약.")

# Mailbox로 결과 수신 후 두 teammate 모두 shutdown_request
SendMessage(type="shutdown_request", recipient="doc-analyst")
SendMessage(type="shutdown_request", recipient="issue-analyst")
```

**산출물**: 문서 중복 여부, 연관 이슈 번호 (Phase 1.3에 사용)

### Step 1.1: 복잡도 점수 판단 (MANDATORY - 5점 만점)

| # | 조건 | 1점 기준 | 0점 기준 |
|:-:|------|---------|---------|
| 1 | **파일 범위** | 3개 이상 파일 수정 예상 | 1-2개 파일 |
| 2 | **아키텍처** | 새 패턴/구조 도입 | 기존 패턴 내 수정 |
| 3 | **의존성** | 새 라이브러리/서비스 추가 | 기존 의존성만 사용 |
| 4 | **모듈 영향** | 2개 이상 모듈/패키지 영향 | 단일 모듈 내 변경 |
| 5 | **사용자 명시** | `ralplan` 키워드 포함 | 키워드 없음 |

**판단 로그 출력 (항상 필수):**
```
=== 복잡도 판단 ===
파일 범위: {0|1}점 ({근거})
아키텍처: {0|1}점 ({근거})
의존성:   {0|1}점 ({근거})
모듈 영향: {0|1}점 ({근거})
사용자 명시: {0|1}점
총점: {score}/5 -> {LIGHT|STANDARD|HEAVY}
===================
```

**복잡도 모드:**
- **0-1점**: LIGHT (간단, haiku)
- **2-3점**: STANDARD (보통, sonnet)
- **4-5점**: HEAVY (복잡, Planner-Critic Loop)

### Step 1.2: 계획 수립 (명시적 호출)

**LIGHT (0-1점): Planner haiku teammate**
```
Task(subagent_type="planner", name="planner", team_name="pdca-{feature}",
     model="haiku", prompt="... (복잡도: LIGHT {score}/5, 단일 파일 수정 예상). docs/01-plan/{feature}.plan.md 생성.")
SendMessage(type="message", recipient="planner", content="계획 수립 시작. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```

**STANDARD (2-3점): Planner sonnet teammate**
```
Task(subagent_type="planner", name="planner", team_name="pdca-{feature}",
     model="sonnet", prompt="... (복잡도: STANDARD {score}/5, 판단 근거 포함). docs/01-plan/{feature}.plan.md 생성.")
SendMessage(type="message", recipient="planner", content="계획 수립 시작. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```

**HEAVY (4-5점): Planner-Critic Loop (max 5 iterations)**

```
critic_feedback = ""      # Lead 메모리에서 관리
iteration_count = 0

Loop (max 5 iterations):
  iteration_count += 1

  # Step A: Planner Teammate
  Task(subagent_type="planner", name="planner-{iteration_count}",
       team_name="pdca-{feature}", model="sonnet",
       prompt="[Phase 1 HEAVY] 계획 수립 (Iteration {iteration_count}/5).
               작업: {user_request}
               이전 Critic 피드백: {critic_feedback}
               계획 문서 작성 후 사용자 확인 단계를 건너뛰세요.
               Critic teammate가 reviewer 역할을 대신합니다.
               계획 완료 시 바로 '계획 작성 완료' 메시지를 전송하세요.
               필수 포함: 배경, 구현 범위, 영향 파일, 위험 요소.
               출력: docs/01-plan/{feature}.plan.md")
  SendMessage(type="message", recipient="planner-{iteration_count}", content="계획 수립 시작.")
  # 결과 수신 대기 → shutdown_request

  # Step B: Architect Teammate
  Task(subagent_type="architect", name="arch-{iteration_count}",
       team_name="pdca-{feature}", model="sonnet",
       prompt="[Phase 1 HEAVY] 기술적 타당성 검증.
               Plan 파일: docs/01-plan/{feature}.plan.md
               검증 항목: 1. 파일 경로 존재 여부 2. 의존성 충돌 3. 아키텍처 일관성 4. 성능/보안 우려
               소견을 5줄 이내로 요약하세요.")
  SendMessage(type="message", recipient="arch-{iteration_count}", content="타당성 검증 시작.")
  # 결과 수신 대기 → shutdown_request

  # Step C: Critic Teammate
  Task(subagent_type="critic", name="critic-{iteration_count}",
       team_name="pdca-{feature}", model="sonnet",
       prompt="[Phase 1 HEAVY] 계획 완전성 검토 (Iteration {iteration_count}/5).
               Plan 파일: docs/01-plan/{feature}.plan.md
               Architect 소견: {architect_feedback}
               당신은 까다로운 코드 리뷰어입니다. 일반적으로 계획은 3회 이상 수정이 필요합니다.
               반드시 검증:
               - 모든 파일 참조가 실제 존재하는 경로인지
               - acceptance criteria가 구체적이고 측정 가능한지
               - 모호한 표현 ('적절히', '필요 시', '가능하면' 등) 여부
               - 누락된 edge case가 없는지
               반드시 첫 줄에 VERDICT: APPROVE 또는 VERDICT: REVISE를 출력하세요.
               APPROVE는 위 모든 조건 충족 시에만. REVISE 시 구체적 개선 피드백을 포함하세요.")
  SendMessage(type="message", recipient="critic-{iteration_count}", content="계획 검토 시작.")
  # 결과 수신 대기 → shutdown_request

  # Step D: Lead 판정
  critic_message = Mailbox에서 수신한 critic 메시지
  first_line = critic_message의 첫 줄

  if "VERDICT: APPROVE" in first_line:
      → Loop 종료, Phase 2 진입
  elif "VERDICT: REVISE" in first_line:
      → critic_feedback = critic_message에서 VERDICT: 줄 이후 전체
      → 누적 피드백이 1,500t 초과 시 최신 2회분만 유지
        (이전: "Iteration {N}: {핵심 요약 1줄}" 형태로 압축)
      → 다음 iteration
  else:
      → REVISE로 간주 (안전 기본값)

  if iteration_count >= 5 and not APPROVED:
      → Plan 파일에 "WARNING: Critic 5회 반복으로 강제 승인" 주석 추가
      → 강제 APPROVE → Phase 2 진입
```

**Critic 판정 파싱 규칙:**
- 판정 추출: Critic 메시지 첫 줄에서 `VERDICT: APPROVE` 또는 `VERDICT: REVISE` 키워드 확인
- 키워드 불일치: 첫 줄에 VERDICT 없으면 REVISE로 간주
- 피드백 범위: REVISE 시 `VERDICT:` 줄 이후 전체 내용을 critic_feedback에 저장
- 피드백 1,500t 이하: 전체 누적 유지 / 초과: 최신 2회분 전문 + 이전은 1줄 압축 / 5회 초과: 강제 APPROVE

**산출물**: `docs/01-plan/{feature}.plan.md`

### Step 1.3: 이슈 연동 (GitHub Issue)

**Step 1.0에서 연관 이슈 발견 시**: `gh issue comment <issue-number> "관련 Plan: docs/01-plan/{feature}.plan.md"`

**신규 이슈 생성 필요 시**: `gh issue create --title "{feature}" --body "Plan: docs/01-plan/{feature}.plan.md" --label "auto"`

---

## Phase 1→2 Gate: Plan 검증 (MANDATORY)

| # | 필수 섹션 | 확인 방법 |
|:-:|----------|----------|
| 1 | 배경/문제 정의 | `## 배경` 또는 `## 문제 정의` 헤딩 존재 |
| 2 | 구현 범위 | `## 구현 범위` 또는 `## 범위` 헤딩 존재 |
| 3 | 예상 영향 파일 | 파일 경로 목록 포함 |
| 4 | 위험 요소 | `## 위험` 또는 `위험 요소` 헤딩 존재 |

**누락 시**: Plan 문서를 먼저 보완한 후 Phase 2로 진행.

---

## 복잡도 분기 상세 (Phase 2-5 실행 차이)

### LIGHT 모드 (0-1점)

| Phase | 실행 |
|-------|------|
| Phase 1 | Explore teammates (haiku) x2 + Planner teammate (haiku) |
| Phase 2 | **스킵** (설계 문서 생성 없음) |
| Phase 3 | Executor teammate (sonnet) 단일 실행 |
| Phase 4 | Lead QA 1사이클 + Architect 검증 (gap-detector, E2E 스킵) |
| Phase 5 | haiku 보고서 (APPROVE 기반, gap-detector 없음) |

### STANDARD 모드 (2-3점)

| Phase | 실행 |
|-------|------|
| Phase 1 | Explore teammates (haiku) x2 + Planner teammate (sonnet) |
| Phase 2 | Executor teammate (sonnet) — 설계 문서 생성 |
| Phase 3 | impl-manager teammate (sonnet) — 5조건 자체 루프 |
| Phase 4 | Lead QA 3사이클 + E2E (있으면) + Architect + gap-detector + code-analyzer |
| Phase 5 | gap < 90% → pdca-iterator teammate (최대 5회) |

### HEAVY 모드 (4-5점)

| Phase | 실행 |
|-------|------|
| Phase 1 | Explore teammates (haiku) x2 + Planner-Critic Loop (max 5 iter) |
| Phase 2 | Executor-high teammate (opus) — 설계 문서 생성 |
| Phase 3 | impl-manager teammate (opus) — 5조건 자체 루프 + 병렬 가능 |
| Phase 4 | Lead QA 5사이클 + E2E (필수) + Architect + gap-detector + code-analyzer (opus) |
| Phase 5 | gap < 90% → pdca-iterator teammate (최대 5회) |

### 자동 승격 규칙 (Phase 중 복잡도 상향 조정)

| 승격 조건 | 결과 |
|----------|------|
| 빌드 실패 2회 이상 | LIGHT → STANDARD |
| QA 3사이클 초과 | STANDARD → HEAVY |
| 영향 파일 5개 이상 | LIGHT/STANDARD → HEAVY |
| Architect REJECT 2회 | 현재 모드 유지, pdca-iterator 최대 회수 +2 |

---

## Phase 2: DESIGN (설계 문서 생성)

> **CRITICAL**: `architect`는 READ-ONLY (Write/Edit 도구 없음). 설계 문서 **생성**에는 executor 계열 사용 필수.

**LIGHT 모드: 스킵** (설계 문서 생성 없음, Phase 3에서 직접 구현)

**STANDARD 모드: Executor sonnet teammate**
```
Task(subagent_type="executor", name="design-writer", team_name="pdca-{feature}",
     model="sonnet",
     prompt="docs/01-plan/{feature}.plan.md를 참조하여 설계 문서를 작성하세요.
     필수 포함: 구현 대상 파일 목록, 인터페이스 설계, 데이터 흐름, 테스트 전략.
     출력: docs/02-design/{feature}.design.md")
SendMessage(type="message", recipient="design-writer", content="설계 문서 생성 요청. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```

**HEAVY 모드: Executor-high opus teammate**
```
Task(subagent_type="executor-high", name="design-writer", team_name="pdca-{feature}",
     model="opus",
     prompt="docs/01-plan/{feature}.plan.md를 참조하여 설계 문서를 작성하세요.
     필수 포함: 구현 대상 파일 목록, 인터페이스 설계, 데이터 흐름, 테스트 전략, 예상 위험 요소.
     출력: docs/02-design/{feature}.design.md")
SendMessage(type="message", recipient="design-writer", content="설계 문서 생성 요청. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```

**산출물**: `docs/02-design/{feature}.design.md`

### Phase 2→3 Gate: Design 검증

| # | 필수 항목 | 확인 방법 |
|:-:|----------|----------|
| 1 | 구현 대상 파일 목록 | 구체적 파일 경로 나열 존재 |
| 2 | 인터페이스/API 설계 | 함수/클래스 시그니처 정의 |

---

## Phase 3: DO (옵션 처리 + 모드별 구현)

### Step 3.0: 옵션 처리 (있을 경우)

옵션이 있으면 구현 진입 전에 처리. 실패 시 에러 출력 후 중단 (조용한 스킵 금지).

### Step 3.1: 모드별 구현 (명시적 호출)

**LIGHT 모드: Executor teammate (sonnet) 단일 실행**
```
Task(subagent_type="executor", name="executor", team_name="pdca-{feature}",
     model="sonnet",
     prompt="docs/01-plan/{feature}.plan.md 기반 구현 (설계 문서 없음). TDD 필수.")
SendMessage(type="message", recipient="executor", content="구현 시작. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```
- 5조건 검증 없음 (단일 실행)
- 빌드 실패 시 즉시 STANDARD 모드로 승격

**STANDARD 모드: impl-manager teammate (sonnet) — 5조건 자체 루프**
```
Task(subagent_type="executor", name="impl-manager", team_name="pdca-{feature}",
     model="sonnet",
     prompt="{impl-manager prompt 전문 — 아래 'impl-manager Prompt 전문' 섹션 참조}")
SendMessage(type="message", recipient="impl-manager", content="5조건 구현 루프 시작.")
# Lead는 IMPLEMENTATION_COMPLETED 또는 IMPLEMENTATION_FAILED 메시지만 수신
```

**HEAVY 모드: impl-manager teammate (opus) — 5조건 자체 루프 + 병렬 가능**
```
Task(subagent_type="executor-high", name="impl-manager", team_name="pdca-{feature}",
     model="opus",
     prompt="{impl-manager prompt 전문 — 아래 'impl-manager Prompt 전문' 섹션 참조}")
SendMessage(type="message", recipient="impl-manager", content="5조건 구현 루프 시작.")
# Lead는 IMPLEMENTATION_COMPLETED 또는 IMPLEMENTATION_FAILED 메시지만 수신
```

**HEAVY 병렬 실행 (독립 작업 2개 이상 시):**
```
# Lead가 설계 문서 분석 → 독립 작업 분할
Task(subagent_type="executor-high", name="impl-api",
     team_name="pdca-{feature}", model="opus",
     prompt="[Phase 3 HEAVY 병렬] API 구현 담당. {impl-manager 전체 prompt}.
             담당 범위: src/api/ 하위 파일만. 다른 경로 수정 금지.")
Task(subagent_type="executor-high", name="impl-ui",
     team_name="pdca-{feature}", model="opus",
     prompt="[Phase 3 HEAVY 병렬] UI 구현 담당. {impl-manager 전체 prompt}.
             담당 범위: src/components/ 하위 파일만. 다른 경로 수정 금지.")

SendMessage(type="message", recipient="impl-api", content="API 구현 시작.")
SendMessage(type="message", recipient="impl-ui", content="UI 구현 시작.")
# 두 impl-manager 모두에서 IMPLEMENTATION_COMPLETED 수신 대기
# 하나라도 FAILED → Lead가 사용자에게 알림
```

**--worktree 병렬 격리** (Worktree 통합 섹션의 Agent Teams 병렬 격리 참조)

### Phase 3→4 Gate: impl-manager 완료 판정

- LIGHT: 스킵 (5조건 검증 없음, 빌드 통과만 확인)
- STANDARD/HEAVY: impl-manager가 `IMPLEMENTATION_COMPLETED` 메시지 전송 시 Phase 4 진입
- impl-manager가 `IMPLEMENTATION_FAILED` 메시지 전송 시 Lead가 사용자에게 알림 + 수동 개입 요청
- --interactive 모드: 사용자 확인 요청

---

## impl-manager Prompt 전문

Phase 3에서 impl-manager teammate에 전달하는 complete prompt:

```
[Phase 3 DO] Implementation Manager - 5조건 자체 루프

설계 문서: docs/02-design/{feature}.design.md
계획 문서: docs/01-plan/{feature}.plan.md

당신은 Implementation Manager입니다. 설계 문서를 기반으로 코드를 구현하고,
5가지 완료 조건을 모두 충족할 때까지 자동으로 수정/재검증을 반복합니다.

=== 5가지 완료 조건 (ALL 충족 필수) ===

1. TODO == 0: 설계 문서의 모든 구현 항목 완료. 부분 완료 금지.
2. 빌드 성공: 프로젝트 빌드 명령 실행 결과 에러 0개.
   - Python: ruff check src/ --fix (lint 통과)
   - Node.js: npm run build (빌드 통과)
   - 해당 빌드 명령이 없으면 이 조건은 자동 충족.
3. 테스트 통과: 모든 테스트 green.
   - Python: pytest tests/ -v (관련 테스트만 실행 가능)
   - Node.js: npm test 또는 jest
   - 테스트가 없으면 TDD 규칙에 따라 테스트 먼저 작성.
4. 에러 == 0: lint, type check 에러 0개.
   - Python: ruff check + mypy (설정 있을 때)
   - Node.js: tsc --noEmit (TypeScript일 때)
5. 자체 코드 리뷰: 작성한 코드의 아키텍처 일관성 확인.
   - 기존 코드 패턴과 일치하는가?
   - 불필요한 복잡도가 추가되지 않았는가?
   - 보안 취약점(OWASP Top 10)이 없는가?

=== 자체 Iteration 루프 ===

최대 10회까지 반복합니다:
  1. 5조건 검증 실행
  2. 미충족 조건 발견 시 → 해당 문제 수정
  3. 수정 후 → 1번으로 (재검증)
  4. ALL 충족 시 → IMPLEMENTATION_COMPLETED 메시지 전송
  5. 10회 도달 시 → IMPLEMENTATION_FAILED 메시지 전송

=== Iron Law Evidence Chain ===

IMPLEMENTATION_COMPLETED 전송 전 반드시 다음 5단계 증거를 확보하세요:
  1. 모든 테스트 통과 (pytest/jest 실행 결과 캡처)
  2. 빌드 성공 (build command 실행 결과 캡처)
  3. Lint/Type 에러 0개 (ruff/tsc 실행 결과 캡처)
  4. 자체 코드 리뷰 완료 (아키텍처 일관성 확인 내용)
  5. 위 4개 결과를 IMPLEMENTATION_COMPLETED 메시지에 포함

증거 없는 완료 주장은 절대 금지합니다.

=== Zero Tolerance 규칙 ===

다음 행위는 절대 금지합니다:
  - 범위 축소: 설계 문서의 구현 항목을 임의로 제외
  - 부분 완료: "나머지는 나중에" 식의 미완성 제출
  - 테스트 삭제: 실패하는 테스트를 삭제하여 green 만들기
  - 조기 중단: 5조건 미충족 상태에서 COMPLETED 전송
  - 불확실 언어: "should work", "probably fine", "seems to pass" 등 사용 시
    → 해당 항목에 대해 구체적 검증을 추가로 실행

=== Red Flags 자체 감지 ===

다음 패턴을 자체 감지하고 경고하세요:
  - "should", "probably", "seems to" 등 불확실 언어 사용
  - TODO/FIXME/HACK 주석 추가
  - 테스트 커버리지 80% 미만
  - 하드코딩된 값 (매직 넘버, 매직 스트링)
  - 에러 핸들링 누락 (bare except, empty catch)

감지 시 처리: Red Flag 발견 → 해당 항목을 즉시 수정 후 다음 iteration으로 진행.
수정 불가 시 IMPLEMENTATION_FAILED 메시지에 Red Flag 목록을 포함하여 Lead에게 보고.

=== 메시지 형식 ===

[성공 시]
IMPLEMENTATION_COMPLETED: {
  "iterations": {실행 횟수},
  "files_changed": [{변경 파일 목록}],
  "test_results": "{pytest/jest 결과 요약}",
  "build_results": "{빌드 결과 요약}",
  "lint_results": "{lint 결과 요약}",
  "self_review": "{자체 리뷰 요약}"
}

[실패 시]
IMPLEMENTATION_FAILED: {
  "iterations": 10,
  "remaining_issues": [{미해결 문제 목록}],
  "last_attempt": "{마지막 시도 요약}",
  "recommendation": "{권장 조치}"
}

=== Background Operations ===

install, build, test 등 장시간 명령은 background로 실행하세요:
  - npm install → background
  - pip install → background
  - 전체 테스트 suite → foreground (결과 확인 필요)

=== Delegation ===

직접 코드를 작성하세요. 추가 subagent를 spawn하지 마세요.
이 teammate 내부에서의 에이전트 호출은 금지됩니다.
```

### 자동 재시도/승격/실패 로직

| 조건 | 처리 |
|------|------|
| impl-manager 5조건 루프 내 빌드 실패 | impl-manager 자체 재시도 (10회 한도 내) |
| impl-manager 10회 초과 (FAILED 반환) | Lead가 사용자에게 알림 + 수동 개입 요청 |
| LIGHT에서 빌드 실패 2회 | STANDARD 자동 승격 (impl-manager 재spawn) |
| QA 3사이클 초과 | STANDARD → HEAVY 자동 승격 |
| 영향 파일 5개 이상 감지 | LIGHT/STANDARD → HEAVY 자동 승격 |
| 진행 상태 추적 | `pdca-status.json`의 `implManagerIteration` 필드 |
| 세션 중단 후 resume | `pdca-status.json` 기반 Phase/iteration 복원 |

---

## Phase 4: CHECK (QA 사이클 + E2E + 이중 검증)

### Step 4.1: QA 사이클 — Lead 직접 실행 + Executor 수정 위임

```
failure_history = []  # 실패 기록 배열 (Lead 메모리에서 관리)
max_cycles = LIGHT:1 / STANDARD:3 / HEAVY:5
cycle = 0

while cycle < max_cycles:
  cycle += 1

  # Step A: Lead 직접 QA 실행
  # Python 프로젝트
  Bash("ruff check src/ --fix")        → lint_result
  Bash("pytest tests/ -v")             → test_result
  # Node.js 프로젝트 (해당 시)
  Bash("npm run build")                → build_result
  Bash("npm test")                     → test_result
  # TypeScript (해당 시)
  Bash("npx tsc --noEmit")             → type_result

  모든 검사 통과 → Step 4.2 (이중 검증) 진입

  실패 발견 →
    # Step B: 실패 기록 + Same Failure 3x 검사
    failure_entry = {
      "cycle": cycle,
      "type": "lint|test|build|type",
      "detail": "{실패 상세}",
      "signature": "{실패 식별 시그니처}"
    }
    failure_history.append(failure_entry)

    # Same Failure 3x 감지
    same_failures = [f for f in failure_history if f.signature == failure_entry.signature]
    if len(same_failures) >= 3:
      → QA 사이클 조기 종료
      → "[Phase 4] 동일 실패 3회 감지: {signature}. Root cause: {analysis}. 수동 개입 필요." 출력
      → 사용자에게 수동 개입 요청
      → Phase 4 종료 (Phase 5로 미진입)

    # Step C: Executor Teammate 수정 위임
    Task(subagent_type="executor", name="fixer-{cycle}",
         team_name="pdca-{feature}", model="sonnet",
         prompt="QA 실패 수정.
                 실패 유형: {failure_type}
                 실패 상세: {failure_detail}
                 이전 실패 이력: {failure_history 요약}
                 수정 후 해당 검사를 재실행하여 통과를 확인하세요.")
    SendMessage(type="message", recipient="fixer-{cycle}", content="QA 실패 수정 시작.")
    # 완료 대기 → shutdown_request

    → 다음 cycle로 (Step A 재실행)
```

### Same Failure 3x 조기 종료

| 항목 | 설명 |
|------|------|
| 실패 시그니처 | `{failure_type}:{핵심 에러 메시지}` (예: `test:test_coordinator::test_heavy_mode FAILED`) |
| 동일 판정 | 시그니처가 정확히 일치하는 실패가 3회 누적 |
| 조기 종료 출력 | `"[Phase 4] 동일 실패 3회 감지: {signature}. Root cause: {analysis}. 수동 개입 필요."` |
| 후속 처리 | Phase 5로 진입하지 않음. 사용자에게 실패 보고서 제공 |

### Step 4.2: 이중 검증 (순차 teammate - context 분리)

**LIGHT 모드: Architect teammate만 (gap-detector 스킵)**
```
Task(subagent_type="architect", name="verifier", team_name="pdca-{feature}",
     model="sonnet",
     prompt="구현된 기능이 docs/01-plan/{feature}.plan.md 요구사항과 일치하는지 검증.")
SendMessage(type="message", recipient="verifier", content="검증 시작. APPROVE/REJECT 판정 후 TaskUpdate 처리.")
# verifier 완료 대기 → shutdown_request
```

**STANDARD/HEAVY 모드: Architect → gap-detector → code-analyzer (순차 teammate)**
```
# 1. Architect teammate 먼저 실행
Task(subagent_type="architect", name="verifier", team_name="pdca-{feature}",
     model="sonnet",
     prompt="구현된 기능이 docs/02-design/{feature}.design.md와 일치하는지 검증.")
SendMessage(type="message", recipient="verifier", content="검증 시작. APPROVE/REJECT 판정 후 TaskUpdate 처리.")
# verifier 완료 대기 → shutdown_request

# 2. gap-detector teammate (verifier 완료 후 spawn)
Task(subagent_type="bkit:gap-detector", name="gap-checker", team_name="pdca-{feature}",
     model="sonnet",
     prompt="docs/02-design/{feature}.design.md와 실제 구현 코드 간 일치도 분석. 90% 기준.")
SendMessage(type="message", recipient="gap-checker", content="갭 분석 시작. 완료 후 TaskUpdate 처리.")
# gap-checker 완료 대기 → shutdown_request

# 3. code-analyzer teammate (gap-checker 완료 후 spawn)
# Lead가 직접 프로젝트 유형 감지 후 Vercel BP 규칙 동적 주입
#
# === Vercel BP 동적 주입 메커니즘 (Lead 직접 실행) ===
# has_nextjs = len(Glob("next.config.*")) > 0
# has_react = "react" in Read("package.json")  # dependency 존재 여부
# if has_nextjs or has_react:
#     vercel_bp_rules = "(아래 'Vercel BP 검증 규칙' 섹션 전문)"
#     analyzer_prompt = f"구현 코드의 품질, 보안, 성능 이슈 분석.\n\n추가 검증 — Vercel BP 규칙:\n{vercel_bp_rules}"
# else:
#     analyzer_prompt = "구현 코드의 품질, 보안, 성능 이슈 분석."
#
Task(subagent_type="bkit:code-analyzer", name="quality-checker", team_name="pdca-{feature}",
     model="sonnet",
     prompt=analyzer_prompt)  # ← React/Next.js 프로젝트일 때만 Vercel BP 규칙 포함
SendMessage(type="message", recipient="quality-checker", content="코드 품질 분석 시작. 완료 후 TaskUpdate 처리.")
# quality-checker 완료 대기 → shutdown_request
```

**HEAVY 모드: 동일 (순차 teammate, opus)**

- Architect: 기능 완성도 검증 (APPROVE/REJECT)
- gap-detector: 설계-구현 일치도 검증 (0-100%)
- code-analyzer: 코드 품질, 보안, 성능 분석 + Vercel BP (해당 시)

### Step 4.3: E2E 검증 (Playwright 있을 때만)

**실행 조건:** `playwright.config.ts` 또는 `playwright.config.js` 존재

```bash
npx playwright test --reporter=list
```

**실패 시:**
1. `--strict` 옵션으로 상세 로그 수집
2. `/debug` 스킬 호출 (D0-D4 Phase 디버깅)
3. 실패 원인 수정 후 재실행

**스킵 조건:**
- LIGHT 모드
- Playwright 설정 파일 없음
- `--skip-e2e` 옵션 명시

### Step 4.4: TDD 커버리지 보고 (있을 때만)

**Python 프로젝트:**
```bash
pytest --cov --cov-report=term-missing
```

**JavaScript/TypeScript 프로젝트:**
```bash
jest --coverage
```

**출력:** 커버리지 퍼센트, 미커버 라인 번호 (80% 미만 시 경고)

---

## Vercel BP 검증 규칙

Phase 4 Step 4.2에서 code-analyzer teammate prompt에 동적 주입하는 규칙:

```
=== Vercel Best Practices 검증 규칙 ===

[React 성능]
- useMemo/useCallback: 실제 re-render 비용이 높은 경우에만 사용. 과도한 메모이제이션 지양.
- key prop: 배열 렌더링 시 안정적 key 사용 (index 금지).
- lazy loading: 큰 컴포넌트는 React.lazy + Suspense.
- state 최소화: 파생 가능한 값은 state 대신 계산.

[Next.js 패턴]
- App Router 우선: pages/ 대신 app/ 디렉토리 사용.
- Server Component 기본: 'use client' 최소화. 인터랙티브 부분만 Client.
- Metadata API: generateMetadata 사용, <Head> 지양.
- Image 최적화: next/image 필수, width/height 명시.
- Font 최적화: next/font 사용, FOUT/FOIT 방지.

[접근성]
- 모든 인터랙티브 요소에 aria-label 또는 accessible name.
- Semantic HTML: div 남용 대신 nav, main, section, article, aside.
- 키보드 네비게이션: 모든 기능이 Tab/Enter로 접근 가능.
- 색상 대비: WCAG 2.1 AA 기준 (4.5:1 이상).

[보안]
- dangerouslySetInnerHTML 사용 시 sanitize 필수.
- 환경 변수: NEXT_PUBLIC_ prefix 없이 서버 전용 비밀 유지.
- CSP 헤더: next.config.js에 Content-Security-Policy 설정.

[성능]
- Bundle size: dynamic import로 코드 분할.
- API Route: Edge Runtime 우선 (해당 시).
- Caching: ISR/SSG 우선, SSR은 필요한 경우만.
```

**동적 주입 조건:**
- `Glob("next.config.*")` 결과 존재 또는 `package.json` 내 `"react"` dependency 존재 시 주입
- 웹 프로젝트가 아닌 경우 생략

---

## Phase 5: ACT (결과 기반 자동 실행 - "Recommended" 출력 금지)

| Check 결과 | 자동 실행 | 다음 |
|-----------|----------|------|
| gap < 90% | pdca-iterator teammate (최대 5회 반복) | Phase 4 재실행 |
| gap >= 90% + Architect APPROVE | report-generator teammate | TeamDelete → 완료 |
| Architect REJECT | executor teammate (수정) | Phase 4 재실행 |

**Case 1: gap < 90%**
```
Task(subagent_type="bkit:pdca-iterator", name="iterator", team_name="pdca-{feature}",
     model="sonnet",
     prompt="설계-구현 갭을 90% 이상으로 개선하세요. 최대 5회 반복.")
SendMessage(type="message", recipient="iterator", content="갭 자동 개선 시작.")
# 완료 대기 → shutdown_request → Phase 4 재실행
```

**Case 2: gap >= 90% + APPROVE**
```
Task(subagent_type="bkit:report-generator", name="reporter", team_name="pdca-{feature}",
     model="haiku",
     prompt="PDCA 사이클 완료 보고서를 생성하세요.
     포함: Plan 요약, Design 요약, 구현 결과, Check 결과, 교훈
     출력: docs/04-report/{feature}.report.md")
SendMessage(type="message", recipient="reporter", content="보고서 생성 요청.")
# 완료 대기 → shutdown_request → TeamDelete()
```

**Case 3: Architect REJECT**
```
Task(subagent_type="executor", name="fixer", team_name="pdca-{feature}",
     model="sonnet",
     prompt="Architect 거부 사유를 해결하세요: {rejection_reason}")
SendMessage(type="message", recipient="fixer", content="피드백 반영 시작.")
# 완료 대기 → shutdown_request → Phase 4 재실행
```

---

## `--slack` 옵션 워크플로우

Slack 채널의 모든 메시지를 분석하여 프로젝트 컨텍스트로 활용합니다.

**Step 1: 인증 확인**
```bash
cd C:\claude && python -m lib.slack status --json
```
- `"authenticated": false` -> 에러 출력 후 중단

**Step 2: 채널 히스토리 수집**
```bash
python -m lib.slack history "<채널ID>" --limit 100 --json
```

**Step 3: 메시지 분석 (Analyst Teammate)**
```
Task(subagent_type="analyst", name="slack-analyst", team_name="pdca-{feature}",
     model="opus",
     prompt="SLACK CHANNEL ANALYSIS
     채널: <채널ID>
     분석 항목: 주요 토픽, 핵심 결정사항, 공유 문서 링크, 참여자 역할, 미해결 이슈, 기술 스택
     출력: 구조화된 컨텍스트 문서")
SendMessage(type="message", recipient="slack-analyst", content="Slack 채널 분석 요청.")
# 완료 대기 → shutdown_request
```

**Step 4: 컨텍스트 파일 생성**
`.omc/slack-context/<채널ID>.md` 생성 (프로젝트 개요, 핵심 결정사항, 관련 문서, 기술 스택, 미해결 이슈, 원본 메시지)

**Step 5: 메인 워크플로우 실행**
- 생성된 컨텍스트 파일을 Read하여 Phase 1 (PLAN)에 전달

---

## `--gmail` 옵션 워크플로우

Gmail 메일을 분석하여 프로젝트 컨텍스트로 활용합니다.

**사용 형식:**
```bash
/auto --gmail                           # 안 읽은 메일 분석
/auto --gmail "검색어"                   # Gmail 검색 쿼리로 필터링
/auto --gmail "작업 설명"                # 메일 기반 작업 실행
/auto --gmail "from:client" "응답 초안"  # 검색 + 작업 조합
```

**Step 1: 인증 확인 (MANDATORY)**
```bash
cd C:\claude && python -m lib.gmail status --json
```

**Step 2: 메일 수집**

| 입력 패턴 | 실행 명령 |
|----------|----------|
| `--gmail` (검색어 없음) | `python -m lib.gmail unread --limit 20 --json` |
| `--gmail "from:..."` | `python -m lib.gmail search "from:..." --limit 20 --json` |
| `--gmail "subject:..."` | `python -m lib.gmail search "subject:..." --limit 20 --json` |
| `--gmail "newer_than:7d"` | `python -m lib.gmail search "newer_than:7d" --limit 20 --json` |

**Step 3: 메일 분석 (Analyst Teammate)**
```
Task(subagent_type="analyst", name="gmail-analyst", team_name="pdca-{feature}",
     model="opus",
     prompt="GMAIL ANALYSIS
     분석 항목: 요청사항/할일 추출, 발신자 우선순위, 회신 필요 메일, 첨부파일, 키워드 연관성, 리스크
     출력: 구조화된 이메일 분석 문서 (마크다운)")
SendMessage(type="message", recipient="gmail-analyst", content="Gmail 분석 요청.")
# 완료 대기 → shutdown_request
```

**Step 4: 컨텍스트 파일 생성**
`.omc/gmail-context/<timestamp>.md` 생성

**Step 5: 후속 작업 분기**

| 사용자 요청 | 실행 |
|------------|------|
| 검색만 | 분석 결과 출력 후 종료 |
| "응답 초안" | 각 메일에 대한 회신 초안 생성 |
| "할일 생성" | TaskCreate로 TODO 항목 생성 |
| 구체적 작업 | 메인 워크플로우 실행 (메일 컨텍스트 포함) |

---

## `--interactive` 옵션 워크플로우

각 PDCA Phase 전환 시 사용자에게 확인을 요청합니다.

| Phase 전환 | 선택지 | 기본값 |
|-----------|--------|:------:|
| Phase 1 PLAN 완료 → Phase 2 DESIGN | 진행 / 수정 / 건너뛰기 | 진행 |
| Phase 2 DESIGN 완료 → Phase 3 DO | 진행 / 수정 / 건너뛰기 | 진행 |
| Phase 3 DO 완료 → Phase 4 CHECK | 진행 / 수정 | 진행 |
| Phase 4 CHECK 결과 → Phase 5 ACT | 자동 개선 / 수동 수정 / 완료 | 자동 개선 |

**Phase 전환 시 출력 형식:**
```
===================================================
 Phase {N} {이름} 완료 -> Phase {N+1} {이름} 진입 대기
===================================================
 산출물: {파일 경로}
 소요 teammates: {agent (model)}
 핵심 결정: [1줄 요약]
===================================================
```

**--interactive 미사용 시** (기본 동작): 모든 Phase를 자동으로 진행합니다.

---

## /work 통합 안내 (완료)

`/work`는 `/auto`로 통합되었습니다 (v19.0).

| 기존 | 신규 | 상태 |
|------|------|------|
| `/work --loop` | `/auto` | 리다이렉트 완료 (v17.0) |
| `/work "작업"` | `/auto "작업"` | 리다이렉트 완료 (v19.0) |

**변경 없는 기능:**
- 5-Phase PDCA 워크플로우 동일
- 브랜치 자동 생성, 이슈 연동
- TDD 강제 규칙

**v20.1 변경:**
- 모든 subagent 호출을 Agent Teams in-process 방식으로 전환
- Context 분리로 compact 실패 문제 근본 해결
- TeamCreate/TeamDelete 라이프사이클 추가
- Phase 2 DESIGN: architect(READ-ONLY) → executor/executor-high(Write 가능)로 교체
- LIGHT Phase 4: Architect 검증 추가 (gap-detector는 스킵)
- 토큰 사용량 약 1.5-2배 증가 (독립 context 비용)

**v21.0 변경:**
- `/auto` 내부 Skill() 호출 완전 제거 (ralplan, ralph, ultraqa → Agent Teams 단일 패턴)
- Phase 1 HEAVY: Skill(ralplan) → Planner-Critic Loop (max 5 iter)
- Phase 3 STD/HEAVY: Skill(ralph) → impl-manager 5조건 자체 루프 (max 10 iter)
- Phase 4 Step 4.1: Skill(ultraqa) → Lead 직접 QA + Executor 수정 위임
- Phase 4 Step 4.2: code-analyzer에 Vercel BP 규칙 동적 주입
- State 파일 의존 0개 (Agent Teams lifecycle으로 대체)
- Stop Hook 충돌 자연 해소 (state 파일 미생성)
- `pdca-status.json`: `ralphIteration` → `implManagerIteration` 필드 변경

---

## Resume (`/auto resume`) — Context Recovery

`/clear` 또는 새 세션 시작 후:
1. `docs/.pdca-status.json` 읽기 → `primaryFeature`와 `phaseNumber` 확인
2. 산출물 존재 검증: Plan 파일, Design 파일 유무로 실제 진행 Phase 교차 확인
3. Git 상태 확인: `git branch --show-current`, `git status --short`
4. Phase 3 중단 시: `implManagerIteration` 필드로 impl-manager 반복 위치 확인
5. `TeamCreate(team_name="pdca-{feature}")` 새로 생성 (이전 팀은 복원 불가)
6. 해당 Phase부터 재개 (완료된 Phase 재실행 금지)

### Resume 시 impl-manager 재개

`pdca-status.json`에 추가되는 필드:
```json
{
  "implManagerIteration": 5,
  "implManagerStatus": "in_progress",
  "implManagerRemainingIssues": ["test failure in X", "lint error in Y"]
}
```

Resume 시:
- iteration 5회 미만 → 해당 지점부터 재개
- iteration 5회 이상 소진 → 처음부터 재시작
- impl-manager teammate를 새로 spawn하면서 prompt에 포함:
  ```
  "이전 시도에서 {N}회까지 진행됨. 남은 이슈: {remaining_issues}.
   이전 시도의 변경 사항은 이미 파일에 반영되어 있음. 이어서 진행."
  ```

### Agent Teams Context 장점

| 기존 (subagent) | 신규 (Agent Teams) |
|-----------------|-------------------|
| 결과가 Lead context에 합류 → overflow | 결과가 Mailbox로 전달 → Lead context 보호 |
| foreground 3개 상한 필요 | 제한 없음 (독립 context) |
| "5줄 요약" 강제 필요 | 불필요 (context 분리) |
| compact 실패 위험 | compact 실패 없음 |

Context limit 발생 시: `claude --continue` 또는 `/clear` 후 `/auto resume`

---

## 자율 발견 모드 상세

| Tier | 이름 | 발견 대상 | 실행 |
|:----:|------|----------|------|
| 0 | CONTEXT | context limit 접근 | `/clear` + `/auto resume` 안내 |
| 1 | EXPLICIT | 사용자 지시 | 해당 작업 실행 |
| 2 | URGENT | 빌드/테스트 실패 | `/debug` 실행 |
| 3 | WORK | pending TODO, 이슈 | 작업 처리 |
| 4 | SUPPORT | staged 파일, 린트 에러 | `/commit`, `/check` |
| 5 | AUTONOMOUS | 코드 품질 개선 | 리팩토링 제안 |
