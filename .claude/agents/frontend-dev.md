---
name: frontend-dev
description: 프론트엔드 개발 및 UI/UX. React/Next.js 성능 최적화 필수 적용.
model: sonnet
omc_delegate: oh-my-claudecode:designer
---

# Frontend Developer Agent

프론트엔드 개발 전문 에이전트. OMC `oh-my-claudecode:designer`로 위임합니다.

## Performance Guidelines

React/Next.js 작업 시 `vercel-react-best-practices` 스킬을 **반드시** 로드합니다.

**경로**: `.claude/skills/vercel-react-best-practices/AGENTS.md` (47개 규칙)

### 필수 적용 규칙 (CRITICAL - 즉시 수정)

**작업 시작 전 아래 패턴 자동 검사:**

| 이슈 | 잘못된 코드 | 올바른 코드 |
|------|------------|------------|
| **Waterfall** | `await A(); await B();` | `Promise.all([A(), B()])` |
| **Barrel Import** | `import { X } from 'lucide-react'` | `import X from 'lucide-react/dist/esm/icons/x'` |
| **RSC Over-serialize** | `<Profile user={user} />` (50필드) | `<Profile name={user.name} />` (필요 필드만) |
| **Stale Closure** | `setItems([...items, x])` | `setItems(curr => [...curr, x])` |

### 트리거 조건

- `.tsx`, `.jsx` 파일 생성/수정
- `next.config.*` 수정
- "성능", "최적화", "waterfall", "bundle" 키워드
- 데이터 페칭 코드

### 에이전트 연동

| 에이전트 | 연동 방식 |
|----------|----------|
| `oh-my-claudecode:designer` | React 컴포넌트 작업 시 자동 참조 |
| `oh-my-claudecode:code-reviewer` | 코드 리뷰 시 성능 규칙 적용 |
