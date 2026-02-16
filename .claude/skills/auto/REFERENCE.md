# /auto REFERENCE - Phase 전환 상세 워크플로우 (v20.1)

이 파일은 SKILL.md에서 분리된 상세 워크플로우입니다.

---

## Agent Teams 운영 규칙 (v20.0)

**모든 에이전트 호출은 Agent Teams in-process 방식을 사용합니다.**

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

## Phase 1→5 PDCA 전체 흐름

```
Phase 0: TeamCreate("pdca-{feature}")
    |
Phase 1 PLAN → Phase 2 DESIGN → Phase 3 DO → Phase 4 CHECK → Phase 5 ACT
     |              |              |              |              |
     v              v              v              v              v
  계획문서        설계문서        구현(Ralph)    QA+이중검증    개선/완료
  (teammates)   (teammate)     (teammates)    (teammates)     |
                                                              v
                                                         TeamDelete()
```

---

## Phase 1: PLAN (사전 분석 → 복잡도 판단 → 계획 수립)

### Step 1.0: 사전 분석 (병렬 Teammates)

```
# 병렬 spawn (독립 작업)
Task(subagent_type="oh-my-claudecode:explore", name="doc-analyst", team_name="pdca-{feature}",
     model="haiku", prompt="docs/, .claude/ 내 관련 문서 탐색. 중복 범위 감지 필수. 결과를 5줄 이내로 요약.")

Task(subagent_type="oh-my-claudecode:explore", name="issue-analyst", team_name="pdca-{feature}",
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
- **4-5점**: HEAVY (복잡, ralplan)

### Step 1.2: 계획 수립 (명시적 호출)

**LIGHT (0-1점): Planner haiku teammate**
```
Task(subagent_type="oh-my-claudecode:planner", name="planner", team_name="pdca-{feature}",
     model="haiku", prompt="... (복잡도: LIGHT {score}/5, 단일 파일 수정 예상). docs/01-plan/{feature}.plan.md 생성.")
SendMessage(type="message", recipient="planner", content="계획 수립 시작. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```

**STANDARD (2-3점): Planner sonnet teammate**
```
Task(subagent_type="oh-my-claudecode:planner", name="planner", team_name="pdca-{feature}",
     model="sonnet", prompt="... (복잡도: STANDARD {score}/5, 판단 근거 포함). docs/01-plan/{feature}.plan.md 생성.")
SendMessage(type="message", recipient="planner", content="계획 수립 시작. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```

**HEAVY (4-5점): Ralplan 실행**
```
Skill(skill="oh-my-claudecode:ralplan",
      args="작업 설명. Critic 추가 검증: docs/01-plan/ 내 기존 Plan과 범위 겹침 여부 확인 필수")
```

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
| Phase 3 | Executor teammate (sonnet) 단일 실행 (Ralph 없음) |
| Phase 4 | UltraQA 1사이클 + Architect 검증 (gap-detector, E2E 스킵) |
| Phase 5 | haiku 보고서 (APPROVE 기반, gap-detector 없음) |

### STANDARD 모드 (2-3점)

| Phase | 실행 |
|-------|------|
| Phase 1 | Explore teammates (haiku) x2 + Planner teammate (sonnet) |
| Phase 2 | Executor teammate (sonnet) — 설계 문서 생성 |
| Phase 3 | Ralph 루프 (5조건 검증) |
| Phase 4 | UltraQA 3사이클 + E2E (있으면) + Architect + gap-detector + code-analyzer |
| Phase 5 | gap < 90% → pdca-iterator teammate (최대 5회) |

### HEAVY 모드 (4-5점)

| Phase | 실행 |
|-------|------|
| Phase 1 | Explore teammates (haiku) x2 + Ralplan (Planner+Critic) |
| Phase 2 | Executor-high teammate (opus) — 설계 문서 생성 |
| Phase 3 | Ralph 루프 + Ultrawork (병렬 teammates) |
| Phase 4 | UltraQA 5사이클 + E2E (필수) + Architect + gap-detector + code-analyzer (opus) |
| Phase 5 | gap < 90% → pdca-iterator teammate (최대 5회) |

### 자동 승격 규칙 (Phase 중 복잡도 상향 조정)

| 승격 조건 | 결과 |
|----------|------|
| 빌드 실패 2회 이상 | LIGHT → STANDARD |
| UltraQA 3사이클 초과 | STANDARD → HEAVY |
| 영향 파일 5개 이상 | LIGHT/STANDARD → HEAVY |
| Architect REJECT 2회 | 현재 모드 유지, pdca-iterator 최대 회수 +2 |

---

## Phase 2: DESIGN (설계 문서 생성)

> **CRITICAL**: `oh-my-claudecode:architect`는 READ-ONLY (Write/Edit 도구 없음). 설계 문서 **생성**에는 executor 계열 사용 필수.

**LIGHT 모드: 스킵** (설계 문서 생성 없음, Phase 3에서 직접 구현)

**STANDARD 모드: Executor sonnet teammate**
```
Task(subagent_type="oh-my-claudecode:executor", name="design-writer", team_name="pdca-{feature}",
     model="sonnet",
     prompt="docs/01-plan/{feature}.plan.md를 참조하여 설계 문서를 작성하세요.
     필수 포함: 구현 대상 파일 목록, 인터페이스 설계, 데이터 흐름, 테스트 전략.
     출력: docs/02-design/{feature}.design.md")
SendMessage(type="message", recipient="design-writer", content="설계 문서 생성 요청. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```

**HEAVY 모드: Executor-high opus teammate**
```
Task(subagent_type="oh-my-claudecode:executor-high", name="design-writer", team_name="pdca-{feature}",
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
Task(subagent_type="oh-my-claudecode:executor", name="executor", team_name="pdca-{feature}",
     model="sonnet",
     prompt="docs/01-plan/{feature}.plan.md 기반 구현 (설계 문서 없음). TDD 필수.")
SendMessage(type="message", recipient="executor", content="구현 시작. 완료 후 TaskUpdate로 completed 처리.")
# 완료 대기 → shutdown_request
```
- Ralph 루프 없음 (5조건 검증 스킵)
- 빌드 실패 시 즉시 STANDARD 모드로 승격

**STANDARD/HEAVY 모드: Ralph 루프**
```
Skill(skill="oh-my-claudecode:ralph",
      args="docs/02-design/{feature}.design.md 기반 구현")
```

**Ralph 루프 내부 동작:**
```
1. Ultrawork 활성화 (병렬 teammate 실행)
   - 독립 작업: 동시 spawn
   - 의존 작업: 순차 실행
2. Architect 검증 (각 작업 완료 후)
3. 5개 완료 조건 확인:
   ☐ TODO == 0 (모든 할일 완료)
   ☐ 기능 동작 (정상 실행 확인)
   ☐ 테스트 통과 (빌드/테스트 green)
   ☐ 에러 == 0 (미해결 에러 없음)
   ☐ Architect 승인 (품질 검증 통과)
4. ANY 실패 → 해당 조건 수정 후 재검증 (자동 재시도)
5. ALL 충족 → Phase 4 자동 진입
```

### Phase 3→4 Gate: Ralph 5조건

- LIGHT: 스킵 (5조건 검증 없음, 빌드 통과만 확인)
- STANDARD/HEAVY: Ralph 5개 조건 **모두** 충족 시 Phase 4 자동 진입
- --interactive 모드: 사용자 확인 요청

---

## Phase 4: CHECK (UltraQA + E2E + 이중 검증)

### Step 4.1: UltraQA 사이클 (명시적 호출)

```
Skill(skill="oh-my-claudecode:ultraqa")
```

Build → Lint → Test → Fix 사이클, 모드별 최대 반복:
- LIGHT: 1회
- STANDARD: 3회
- HEAVY: 5회

모두 통과 시 Step 4.2 진입.

### Step 4.2: 이중 검증 (순차 teammate - context 분리)

**LIGHT 모드: Architect teammate만 (gap-detector 스킵)**
```
Task(subagent_type="oh-my-claudecode:architect", name="verifier", team_name="pdca-{feature}",
     model="sonnet",
     prompt="구현된 기능이 docs/01-plan/{feature}.plan.md 요구사항과 일치하는지 검증.")
SendMessage(type="message", recipient="verifier", content="검증 시작. APPROVE/REJECT 판정 후 TaskUpdate 처리.")
# verifier 완료 대기 → shutdown_request
```

**STANDARD 모드: Architect → gap-detector → code-analyzer (순차 teammate)**
```
# 1. Architect teammate 먼저 실행
Task(subagent_type="oh-my-claudecode:architect", name="verifier", team_name="pdca-{feature}",
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
Task(subagent_type="bkit:code-analyzer", name="quality-checker", team_name="pdca-{feature}",
     model="sonnet",
     prompt="구현 코드의 품질, 보안, 성능 이슈 분석.")
SendMessage(type="message", recipient="quality-checker", content="코드 품질 분석 시작. 완료 후 TaskUpdate 처리.")
# quality-checker 완료 대기 → shutdown_request
```

**HEAVY 모드: 동일 (순차 teammate, opus)**
```
# 1. Architect (opus) → 2. gap-detector (opus) → 3. code-analyzer (opus) 순차
```

- Architect: 기능 완성도 검증 (APPROVE/REJECT)
- gap-detector: 설계-구현 일치도 검증 (0-100%)
- code-analyzer: 코드 품질, 보안, 성능 분석

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
Task(subagent_type="oh-my-claudecode:executor", name="fixer", team_name="pdca-{feature}",
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
Task(subagent_type="oh-my-claudecode:analyst", name="slack-analyst", team_name="pdca-{feature}",
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
Task(subagent_type="oh-my-claudecode:analyst", name="gmail-analyst", team_name="pdca-{feature}",
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

---

## Resume (`/auto resume`) — Context Recovery

`/clear` 또는 새 세션 시작 후:
1. `docs/.pdca-status.json` 읽기 → `primaryFeature`와 `phaseNumber` 확인
2. 산출물 존재 검증: Plan 파일, Design 파일 유무로 실제 진행 Phase 교차 확인
3. Git 상태 확인: `git branch --show-current`, `git status --short`
4. Phase 3 중단 시: `ralphIteration` 필드로 Ralph 반복 위치 확인
5. `TeamCreate(team_name="pdca-{feature}")` 새로 생성 (이전 팀은 복원 불가)
6. 해당 Phase부터 재개 (완료된 Phase 재실행 금지)

### Agent Teams Context 장점

| 기존 (subagent) | 신규 (Agent Teams) |
|-----------------|-------------------|
| 결과가 Lead context에 합류 → overflow | 결과가 Mailbox로 전달 → Lead context 보호 |
| foreground 3개 상한 필요 | 제한 없음 (독립 context) |
| "5줄 요약" 강제 필요 | 불필요 (context 분리) |
| compact 실패 위험 | compact 실패 없음 |

Context limit 발생 시: `claude --continue` 또는 `/clear` 후 `/auto resume`
