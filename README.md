# Ultimate Debate

Multi-AI Consensus Debate Engine (독립 패키지)

## 개요

Ultimate Debate는 여러 AI 모델 간의 합의 도출을 위한 토론 엔진입니다.

## 핵심 기능

- **다층 비교 시스템**: TF-IDF, 구조 정렬, SHA-256 해시
- **4단계 합의 프로토콜**: 80%+ → FULL / 50~80% → CROSS_REVIEW / <50% → DEBATE
- **청킹 시스템**: LoadLevel에 따른 점진적 로딩
- **전략 패턴**: Normal, Mediated, Scope Reduced, Perspective Shift

## 설치

```bash
cd packages/ultimate-debate
uv pip install -e .
```

## 사용법

```python
from ultimate_debate.engine import UltimateDebate

debate = UltimateDebate(
    task="분석할 주제",
    max_rounds=5,
    consensus_threshold=0.8
)

# AI 클라이언트 등록
debate.register_ai_client("claude", claude_client)
debate.register_ai_client("gpt", gpt_client)

# 토론 실행
result = await debate.run()
```

## 구조

```
src/ultimate_debate/
├── engine.py              # 메인 엔진
├── comparison/            # 비교 시스템
│   ├── semantic.py        # TF-IDF
│   ├── structural.py      # 구조 정렬
│   └── hash.py            # SHA-256
├── consensus/             # 합의 프로토콜
│   ├── protocol.py        # 4 트리거
│   └── tracker.py         # 수렴 추적
├── strategies/            # 토론 전략
│   └── *.py              # Normal, Mediated, etc.
├── clients/               # AI 클라이언트 인터페이스
│   └── base.py           # BaseAIClient
└── storage/               # 저장소
    ├── context_manager.py # Context 관리
    └── chunker.py        # 청킹 시스템
```
