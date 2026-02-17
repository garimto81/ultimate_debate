---
name: debug
description: 가설-검증 기반 디버깅
version: 2.0.0
triggers:
  keywords:
    - "debug"
    - "/debug"
    - "디버깅"
---

# /debug - 체계적 디버깅

## 실행 방법

```
TeamCreate(team_name="debug-session")
Task(subagent_type="architect", name="debugger",
     team_name="debug-session", model="opus",
     prompt="문제 원인 분석: [에러 내용]")
SendMessage(type="message", recipient="debugger", content="디버깅 시작.")
# 완료 대기 → shutdown_request → TeamDelete()
```

## 디버깅 Phase

1. D0: 문제 정의
2. D1: 가설 수립
3. D2: 검증
4. D3: 해결
5. D4: 회고
