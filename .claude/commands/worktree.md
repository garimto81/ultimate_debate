---
name: worktree
description: Git worktree 관리 (생성/목록/제거/정리)
---

# /worktree - Git Worktree 관리

Feature 브랜치별 독립 워크트리를 생성하여 병렬 작업 시 파일 충돌을 방지합니다.

## 서브커맨드

### create - 워크트리 생성

```
/worktree create <branch> [base]
```

**실행 흐름** (Bash 3단계, 세션 내 직접 실행):

```bash
# 1. worktree 생성 (base 미지정 시 main)
git worktree add "C:/claude/wt/{branch}" -b "{branch}" {base:main}

# 2. .claude junction 생성 (UAC 불필요)
cmd /c "mklink /J \"C:\\claude\\wt\\{branch}\\.claude\" \"C:\\claude\\.claude\""

# 3. 검증
git worktree list
ls "C:/claude/wt/{branch}/.claude/commands"
```

**결과**: `C:\claude\wt\{branch}\` 디렉토리에 독립 워크트리 생성. CLAUDE.md 상향 탐색 자동 작동.

### list - 워크트리 목록

```
/worktree list
```

**실행**: `git worktree list`

### remove - 워크트리 제거

```
/worktree remove <branch>
```

**실행 흐름**:

```bash
# 1. junction 먼저 제거 (rmdir는 junction만 삭제, 원본 안 건드림)
cmd /c "rmdir \"C:\\claude\\wt\\{branch}\\.claude\""

# 2. worktree 제거
git worktree remove "C:/claude/wt/{branch}"

# 3. 검증
git worktree list
```

### cleanup - 병합 완료된 워크트리 일괄 정리

```
/worktree cleanup
```

**실행 흐름**:

```bash
# 1. merged 브랜치 감지
git branch --merged main

# 2. wt/ 하위 디렉토리 중 merged 브랜치와 일치하는 것 제거
# 각 worktree에 대해:
cmd /c "rmdir \"C:\\claude\\wt\\{branch}\\.claude\""
git worktree remove "C:/claude/wt/{branch}"

# 3. 정리
git worktree prune
git worktree list
```

## 경로 규칙

| 항목 | 경로 |
|------|------|
| Worktree 루트 | `C:\claude\wt\{branch}\` |
| .claude junction | `C:\claude\wt\{branch}\.claude` → `C:\claude\.claude` |
| CLAUDE.md 상속 | `C:\claude\wt\{branch}\` → `C:\claude\CLAUDE.md` 자동 탐색 |

## Agent Teammate 활용

Worktree 내 파일은 절대 경로로 Read/Write/Edit 가능:

```
TeamCreate(team_name="wt-{branch}")
Task(subagent_type="executor", name="impl", team_name="wt-{branch}",
     model="sonnet", prompt="모든 파일은 C:\\claude\\wt\\{branch}\\ 하위에서 작업하세요.")
SendMessage(type="message", recipient="impl", content="구현 시작.")
# 완료 대기 → shutdown_request → TeamDelete()
```

## .gitignore

`C:\claude\.gitignore`의 화이트리스트 방식(`/*`)에 의해 `/wt/`는 자동 무시됨.

## 주의사항

- junction 제거 시 반드시 `rmdir`로 junction만 삭제 (`rm -rf` 사용 금지 → 원본 `.claude/` 삭제됨)
- worktree 제거 전 junction을 먼저 제거할 것
- 사용자에게 외부 터미널 실행 요청 금지 (모든 조작은 세션 내 직접 실행)
