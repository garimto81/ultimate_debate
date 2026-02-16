---
name: auto
description: PDCA Orchestrator - 통합 자율 워크플로우 (Agent Teams + PDCA)
version: 20.1.0
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
omc_agents:
  - executor
  - executor-high
  - oh-my-claudecode:architect
  - planner
  - critic
bkit_agents:
  - gap-detector
  - pdca-iterator
  - code-analyzer
  - report-generator
---

# /auto - PDCA Orchestrator (v20.1)

> **핵심**: `/auto "작업"` = Phase 0-5 PDCA 자동 진행. `/auto` 단독 = 자율 발견 모드. `/work`는 `/auto`로 통합됨.
> **Agent Teams**: 모든 에이전트는 `TeamCreate → Task(name, team_name) → SendMessage → shutdown_request → TeamDelete` 패턴 사용. 상세: `REFERENCE.md`

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

**팀 생성 (MANDATORY):** `TeamCreate(team_name="pdca-{feature}")`

### Phase 1: PLAN (사전 분석 → 복잡도 판단 → 계획 수립 → 이슈 연동)

**Step 1.0**: 병렬 explore(haiku) x2 — 문서 탐색 + 이슈 탐색. `--skip-analysis`로 스킵 가능.

**Step 1.1: 복잡도 판단 (5점 만점)** — 상세 기준: `REFERENCE.md`

| 점수 | 모드 | 라우팅 |
|:----:|:----:|--------|
| 0-1 | LIGHT | planner teammate (haiku) |
| 2-3 | STANDARD | planner teammate (sonnet) |
| 4-5 | HEAVY | `Skill(ralplan)` |

**Step 1.2**: 계획 수립 → `docs/01-plan/{feature}.plan.md` 생성
**Step 1.3**: 이슈 연동 (없으면 생성, 있으면 코멘트). `--no-issue`로 스킵 가능.

### Phase 2: DESIGN (설계 문서 생성)

**Plan→Design Gate**: 4개 필수 섹션 확인 (배경, 구현 범위, 영향 파일, 위험 요소)

| 모드 | 실행 | 에이전트 |
|------|------|---------|
| LIGHT | **스킵** (Phase 3 직행) | — |
| STANDARD | design-writer teammate | `oh-my-claudecode:executor` (sonnet) |
| HEAVY | design-writer teammate | `oh-my-claudecode:executor-high` (opus) |

> **주의**: `oh-my-claudecode:architect`는 READ-ONLY (Write 도구 없음). 설계 **문서 생성**에는 executor 계열 사용 필수.

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
| LIGHT | executor teammate (sonnet) — 단일 실행 (Ralph 없음) |
| STANDARD/HEAVY | `Skill(ralph)` — Ralph 루프 (Ultrawork 내장) |

Ralph 5조건: TODO==0, 기능동작, 테스트통과, 에러==0, Architect승인. 상세: `REFERENCE.md`

### Phase 4: CHECK (UltraQA + 검증 + E2E + TDD)

**Step 4.1**: `Skill(oh-my-claudecode:ultraqa)` — Build→Lint→Test→Fix, 커버리지 80% 필수

**Step 4.2**: 검증 (순차 teammate — context spike 방지)

| 모드 | 실행 |
|------|------|
| LIGHT | architect teammate (sonnet) — APPROVE/REJECT만 |
| STANDARD | architect → gap-detector → code-analyzer (sonnet) 순차 |
| HEAVY | architect → gap-detector → code-analyzer (opus) 순차 |

> architect는 READ-ONLY이므로 **검증/판정에 적합**. 파일 생성에는 사용 금지.

**Step 4.3**: E2E — Playwright 존재 시만. 실패 시 `Skill(debug)`. `--strict` → 1회 실패 중단.
**Step 4.4**: TDD 커버리지 — 신규 80% 이상, 전체 감소 불가.

### Phase 5: ACT (결과 기반 자동 실행 + 팀 정리)

| Check 결과 | 자동 실행 |
|-----------|----------|
| gap < 90% | pdca-iterator teammate (sonnet, 최대 5회) → Phase 4 재실행 |
| gap >= 90% + APPROVE | report-generator teammate (haiku) → `docs/04-report/` |
| Architect REJECT | executor teammate (sonnet) → Phase 4 재실행 |

**팀 정리 (MANDATORY):** `TeamDelete()`

---

## 복잡도 기반 모드 분기

| | LIGHT (0-1) | STANDARD (2-3) | HEAVY (4-5) |
|------|:-----------:|:--------------:|:-----------:|
| **Phase 0** | TeamCreate | TeamCreate | TeamCreate |
| **Phase 1** | haiku 분석 + haiku 계획 | haiku 분석 + sonnet 계획 | haiku 분석 + Ralplan |
| **Phase 2** | 스킵 | executor (sonnet) 설계 | executor-high (opus) 설계 |
| **Phase 3** | executor (sonnet) | Ralph (sonnet) | Ralph (opus 검증) |
| **Phase 4** | UltraQA + Architect검증 | UltraQA + 이중검증 | UltraQA + 이중검증 + E2E |
| **Phase 5** | haiku 보고서 + TeamDelete | sonnet 보고서 + TeamDelete | 완전 보고서 + TeamDelete |

**자동 승격**: LIGHT에서 빌드 실패 2회 / UltraQA 3사이클 / 영향 파일 5개+ 시 STANDARD 승격

---

## 자율 발견 모드 (`/auto` 단독 실행 — 작업 인수 없음)

| Tier | 이름 | 발견 대상 | 실행 |
|:----:|------|----------|------|
| 0 | CONTEXT | context limit 접근 | `/clear` + `/auto resume` 안내 |
| 1 | EXPLICIT | 사용자 지시 | 해당 작업 실행 |
| 2 | URGENT | 빌드/테스트 실패 | `/debug` 실행 |
| 3 | WORK | pending TODO, 이슈 | 작업 처리 |
| 4 | SUPPORT | staged 파일, 린트 에러 | `/commit`, `/check` |
| 5 | AUTONOMOUS | 코드 품질 개선 | 리팩토링 제안 |

## 세션 관리

```bash
/auto status    # 현재 상태 확인
/auto stop      # 중지 (pdca-status.json에 상태 저장, TeamDelete 실행)
/auto resume    # 재개 (pdca-status.json + 산출물 기반 Phase 복원, TeamCreate 재생성)
```

Resume, Context Recovery 상세: `REFERENCE.md`

## 금지 사항

옵션 실패 시 조용히 스킵 / Architect 검증 없이 완료 선언 / 증거 없이 "완료됨" 주장 / 테스트 삭제로 문제 해결 / **TeamDelete 없이 세션 종료** / **architect 에이전트로 파일 생성 시도**

**코드 블록 상세, 옵션 워크플로우**: `REFERENCE.md`
