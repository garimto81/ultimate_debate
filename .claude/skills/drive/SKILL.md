---
name: drive
description: >
  Google Drive 맥락 기반 정리 스킬. AI가 파일명, 내용, 폴더 구조를 분석하여
  의미적으로 분류하고 중복 제거, 버전 관리, 폴더 구조화를 수행합니다.
  단순 패턴 매칭이 아닌 문맥 이해 기반 정리.
version: 2.1.0

triggers:
  keywords:
    - "drive 정리"
    - "드라이브 정리"
    - "파일 정리"
    - "폴더 정리"
    - "중복 제거"
    - "버전 관리"
    - "drive cleanup"
    - "drive organize"
    - "구글 드라이브 정리"
    - "drive audit"
    - "드라이브 감사"
    - "폴더 점검"
    - "구조 확인"
    - "드라이브 점검"
    - "폴더 구조 유지"
  context:
    - "Drive 파일 분류"
    - "문서 정리"
    - "폴더 구조화"
    - "구조 감사"
    - "드리프트 감지"

capabilities:
  - semantic_analysis      # 파일명/내용 의미 분석
  - duplicate_detection    # 중복 파일 탐지
  - version_management     # 버전 아카이빙
  - folder_restructure     # 폴더 재구조화
  - project_classification # 프로젝트별 분류

model_preference: opus  # 의미 분석에 Opus 권장

auto_trigger: true
auto_execute: true  # /drive 호출 시 자동 실행
---

# Drive Organizer Skill

## ⚠️ 자동 실행 프로토콜 (CRITICAL)

**`/drive` 호출 시 아래 단계를 순서대로 자동 실행합니다.**

### Step 1: 현황 수집 (MANDATORY)

Drive API로 프로젝트별 파일 목록 수집 (파일명, 메타데이터, 문서 샘플링)

### Step 2: AI 분석 (Claude 직접 수행)

수집된 데이터를 분석하여:
- 프로젝트 분류 (파일명에서 WSOPTV, EBS 등 키워드 추출)
- 문서 유형 분류 (PRD, Executive Summary, Strategy 등)
- 버전/중복 감지 (v1/v2, 사본, 최종 등)
- 정리 계획 생성 (이동할 파일 목록, 생성할 폴더 구조)

### Step 3: 사용자 확인 (AskUserQuestion 사용)

분석 결과와 제안 작업을 요약하여 사용자에게 확인 요청:
- "전체 실행 (권장)" - 모든 작업 수행
- "중복 제거만" - 중복 파일만 정리
- "분석만" - 실행 없이 결과 확인
- "취소" - 작업 중단

### Step 4: 실행 (승인 시)

CLI 또는 Drive API로 정리 실행 (폴더 생성, 파일 이동, 버전 아카이브)

### Step 5: 결과 리포트

완료된 작업 요약, 최종 폴더 구조, Drive 링크 제공

---

## 옵션별 실행

| 명령 | 동작 |
|------|------|
| `/drive` | 전체 자동 실행 (분석 → 확인 → 실행) |
| `/drive --analyze` | 분석만 (실행 없음) |
| `/drive --project "WSOPTV"` | 특정 프로젝트만 정리 |
| `/drive --dedupe` | 중복 제거만 |
| `/drive --archive` | 구버전 아카이브만 |
| `/drive --audit` | 구조 감사 (거버넌스 점검) |
| `/drive --audit --fix` | 감사 + 교정 계획 생성 |
| `/drive --audit --fix --apply` | 감사 + 교정 실행 |

---

Google Drive를 **AI 맥락 분석** 기반으로 정리하는 스킬입니다.

---

## 🎯 핵심 차별점

| 기존 스크립트 방식 | 이 스킬 (AI 맥락 분석) |
|-------------------|----------------------|
| 파일명 패턴 매칭 (`PRD-*.md`) | **문서 제목/내용의 의미적 분석** |
| 하드코딩된 분류 규칙 | **맥락 기반 동적 분류** |
| 동일 파일명만 중복 감지 | **유사 제목/내용 기반 중복 감지** |
| 수동 폴더 구조 정의 | **프로젝트 분석 후 자동 제안** |

---

상세 워크플로우, 코드 예시, AI 분석 로직, 구조 감사: `REFERENCE.md`
