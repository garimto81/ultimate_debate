---
name: daily
description: >
  Daily Dashboard v3.0 - 3소스 통합 학습+액션 추천 엔진.
  Gmail/Slack/GitHub 증분 수집, AI 크로스소스 분석, 액션 초안 생성.
  프로젝트 전문가 모드 + Config Auto-Bootstrap.
version: 3.1.0

triggers:
  keywords:
    - "daily"
    - "오늘 현황"
    - "일일 대시보드"
    - "프로젝트 진행률"
    - "전체 현황"
    - "데일리 브리핑"
    - "morning briefing"
    - "아침 브리핑"
    - "daily"
    - "일일 동기화"
    - "업체 현황"
    - "vendor status"
  file_patterns:
    - "**/daily/**"
    - "**/checklists/**"
    - "**/daily-briefings/**"
  context:
    - "업무 현황"
    - "프로젝트 관리"

capabilities:
  - daily_dashboard
  - incremental_collection
  - cross_source_analysis
  - action_recommendation
  - attachment_analysis
  - expert_context_loading
  - config_auto_bootstrap
  - gmail_housekeeping
  - slack_lists_update

model_preference: sonnet
auto_trigger: true
---

# Daily Skill v3.0 - 9-Phase Pipeline

3소스(Gmail/Slack/GitHub) 증분 수집 + AI 크로스소스 분석 + 액션 추천 엔진.

**패러다임**: "수집+표시" -> "학습+액션 추천"

**Design Reference**: `C:\claude\docs\02-design\daily-redesign.design.md`

## 실행 규칙 (CRITICAL)

**이 스킬이 활성화되면 반드시 아래 9-Phase Pipeline을 순차 실행하세요!**

```
Phase 0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8
Config   Expert  Collect  Attach  AI     Action  Project  Gmail    State
Bootstrap Context  (incr)  Analyze Analyze Recom   Ops    Housekp  Update
```

## 9-Phase Pipeline 요약

| Phase | 이름 | 핵심 동작 | 에러 처리 |
|:-----:|------|----------|----------|
| 0 | Config Bootstrap | `.project-sync.yaml` 탐색/자동 생성 | CLAUDE.md 없으면 디렉토리명 기반 최소 설정 |
| 1 | Expert Context | 3-Tier 컨텍스트 구성 (Identity 500t / Operational 2000t / Deep 3000t) | Tier 2 없으면 생략 (초회) |
| 2 | Incremental Collection | Gmail History API + Slack last_ts + GitHub since 증분 수집 | 인증 실패 소스 skip, 활성 0개면 중단 |
| 3 | Attachment Analysis | PDF/Excel/이미지 AI 분석, SHA256 캐시 | 다운로드 실패/암호화 -> skip |
| 4 | AI Cross-Source Analysis | 소스별 독립 분석 + 크로스소스 연결 (동일 주제, 상태 불일치) | 단일 소스 -> 독립 분석만 |
| 5 | Action Recommendation | 미응답 48h+, PR 리뷰 대기 3일+ 등 액션 초안 생성 (최대 10건) | 분석 결과 없으면 "액션 불필요" |
| 6 | Project-Specific Ops | vendor: Slack Lists 갱신 / dev: CI/CD+브랜치 상태 | config 없으면 skip |
| 7 | Gmail Housekeeping | 라벨 자동 적용 + INBOX 정리 (auto/confirm/skip) | API 실패 -> skip |
| 8 | State Update | 8A: 커서 갱신 / 8B: Knowledge 갱신 / 8C: Snapshot+Eviction | 쓰기 실패 -> 다음 실행에서 재수집 |

## Phase 0: Config Bootstrap

`.project-sync.yaml` 탐색. 없으면 자동 생성:
1. CLAUDE.md/README.md/디렉토리명으로 프로젝트 식별
2. Gmail/Slack/GitHub 인증 상태 확인
3. 프로젝트 타입 자동 분류 (vendor_management / development / infrastructure / research / content)

Write `.project-sync.yaml` v2.0:
```yaml
version: "2.0"
project_name: "{auto-detected}"
meta:
  auto_generated: true
  confidence: 0.0-1.0
daily:
  sources:
    gmail: { enabled: true/false }
    slack: { enabled: true/false, channel_id: "{fuzzy-matched}" }
    github: { enabled: true/false, repo: "{from git remote}" }
  project_type: "{auto-classified}"
```

## Phase 1: Expert Context Loading

```
Tier 1 Identity (500t): CLAUDE.md + .project-sync.yaml -> 프로젝트명, 목표, 기술 스택
Tier 2 Operational (2000t): .omc/daily-state/<project>/knowledge/snapshots/latest.json
Tier 3 Deep (3000t): docs/ 핵심 문서 (README, PRD, 아키텍처)
```

## Phase 2: Incremental Data Collection

**인증 확인** -> 실패 소스 skip, 활성 0개면 중단

| 소스 | 초회 | 증분 |
|------|------|------|
| Gmail | 7일 lookback + historyId 시딩 | History API (404 -> list fallback) |
| Slack | 7일 lookback | last_ts 이후 |
| GitHub | `gh issue/pr list` | `--since "{last_check}"` |

## Phase 3: Attachment Analysis

대상: PDF, Excel, 이미지. SHA256 캐시로 재분석 방지.

| 타입 | 방법 |
|------|------|
| PDF 20p 이하 | Claude Read tool 직접 분석 |
| PDF 20p 초과 | `lib/pdf_utils` 청크 분할 |
| Excel/CSV | 구조 요약 (행/열, 헤더, 샘플 5행) |
| 이미지 | Claude Vision 분석 |

분석 관점: vendor -> 견적서/금액/조건, dev -> API 스펙/변경점

## Phase 4: AI Cross-Source Analysis

1. 소스별 독립 분석 (Gmail 긴급도, Slack 의사결정, GitHub PR/이슈)
2. 크로스소스 연결 (동일 주제, 액션 연결, 상태 불일치, 타임라인)
3. 이전 이벤트 컨텍스트 주입 (snapshots/latest.json)

## Phase 5: Action Recommendation

| 액션 유형 | 생성 조건 |
|----------|----------|
| 이메일 회신 초안 | 미응답 48h+, 견적 수신 |
| Slack 메시지 초안 | 미응답 질문, follow-up |
| GitHub 액션 | PR 리뷰 대기 3일+, 이슈 미응답 |

톤 캘리브레이션: `communication_style` 참조. 최대 10건, URGENT->HIGH->MEDIUM 정렬.

## Phase 6: Project-Specific Operations

**vendor_management**: Slack Lists 갱신, 업체 상태 전이, 견적 비교표
**development**: CI/CD 상태, 브랜치 상태, 마일스톤 진행률

## Phase 7: Gmail Housekeeping

라벨 자동 적용 (`gmail_label_auto: true`) + INBOX 정리 (`auto`/`confirm`/`skip`)

## Phase 8: State Update & Knowledge Layer

**8A**: 커서 갱신 (Gmail historyId, Slack last_ts, GitHub last_check)
**8B**: Knowledge 갱신 (Entity/Relationship/Pattern/Event)
**8C**: Snapshot (latest.json ~1300t) + 일별 Snapshot (7일 보존) + Eviction (6개월 초과)

상세: `docs/01-plan/knowledge-layer.plan.md`

## 출력 형식

```
================================================================================
                   Daily Dashboard v3.0 (YYYY-MM-DD Day)
                   프로젝트: {project_identity}
================================================================================

[소스 현황] Gmail: {N}건 / Slack: {N}건 / GitHub: 이슈 {N}, PR {N}
[크로스 소스 인사이트] {topic}: {insight} (소스: Gmail+Slack)
[액션 아이템] URGENT ({N}건) / HIGH ({N}건) - 각 초안+소요시간
[소스별 상세] Gmail / Slack / GitHub 각 상세
[첨부파일 분석] {filename}: {summary}

총 액션: {total}건 | 예상 소요: 약 {total_time}분
================================================================================
```

## 서브커맨드

| 커맨드 | 설명 |
|--------|------|
| `/daily` | 전체 대시보드 (9-Phase 전체) |
| `/daily ebs` | EBS 브리핑: `cd C:\claude\ebs\tools\morning-automation && python main.py --post` |
