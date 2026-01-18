# PRD-0035: Multi-AI 끝장토론 Verifier

**Version**: 4.0.0 | **Date**: 2026-01-18 | **Status**: Draft
**Priority**: P1 | **Type**: Enhancement

---

## 1. Executive Summary

### 핵심 컨셉: "끝장 토론" (Ultimate Debate)

**3개 AI가 100% 합의에 도달할 때까지 무제한으로 토론을 계속**합니다.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      🔥 끝장 토론 (Ultimate Debate)                  │
│                                                                      │
│   "모든 AI가 동의할 때까지 끝나지 않는다"                             │
│   "라운드 제한 없음 - 100% 합의가 유일한 종료 조건"                    │
│                                                                      │
│   ┌─────────┐    ┌─────────┐    ┌─────────┐                         │
│   │ Claude  │◄──►│ Gemini  │◄──►│  GPT    │                         │
│   │ Opus4.5 │    │ 3 Pro   │    │  5.2    │                         │
│   └────┬────┘    └────┬────┘    └────┬────┘                         │
│        │              │              │                               │
│        └──────────────┴──────────────┘                               │
│                       │                                              │
│                       ▼                                              │
│              ┌────────────────┐                                      │
│              │ 100% 합의?     │                                      │
│              └────────┬───────┘                                      │
│                       │                                              │
│            ┌──────────┴──────────┐                                   │
│            │                     │                                   │
│         [NO]                  [YES]                                  │
│            │                     │                                   │
│            ▼                     ▼                                   │
│   ┌────────────────┐    ┌────────────────┐                          │
│   │ 무제한 재토론  │    │ 🎯 끝장토론    │                          │
│   │ (합의까지)     │    │    종료!       │                          │
│   └────────────────┘    └────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
```

### v4.0 핵심 변경사항

| 항목 | v3.0 | v4.0 |
|------|------|------|
| 라운드 제한 | 최대 5라운드 | **무제한** |
| 비교검토 | 해시 비교만 | **3-Layer 비교 시스템** |
| 합의 호출 | 라운드마다 체크 | **Consensus Protocol** |
| 종료 조건 | 5라운드 OR 합의 | **100% 합의만** |
| 무한루프 방지 | 라운드 제한 | **Convergence 감지** |

---

## 2. 비교검토 방식 (3-Layer Comparison System)

### 2.1 3계층 비교 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│                    3-Layer Comparison System                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Layer 1: Semantic Comparison (의미적 비교)                          │
│  ─────────────────────────────────────────────────────────────────  │
│  각 AI의 "결론 핵심 문장"을 추출하여 의미적으로 비교                   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Claude: "인증 미들웨어를 auth_middleware.py로 통합해야 함"    │    │
│  │ Gemini: "인증 로직을 하나의 미들웨어로 중앙화 권장"           │    │
│  │ GPT:    "auth_middleware.py 생성하여 인증 처리 일원화"        │    │
│  │                                                               │    │
│  │ → Semantic Similarity: 95% (동일 의도)                        │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Layer 2: Structural Comparison (구조적 비교)                        │
│  ─────────────────────────────────────────────────────────────────  │
│  제안된 "구현 단계"와 "파일 변경 목록"을 구조적으로 비교               │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Claude: [1] 미들웨어 생성 → [2] 데코레이터 적용 → [3] 테스트   │    │
│  │ Gemini: [1] 미들웨어 생성 → [2] 라우터 수정 → [3] 테스트       │    │
│  │ GPT:    [1] 미들웨어 생성 → [2] 데코레이터 적용 → [3] 테스트   │    │
│  │                                                               │    │
│  │ → Step Alignment: 2/3 동일 (Step 2 불일치)                    │    │
│  │ → Disputed: "데코레이터 vs 라우터 수정"                        │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Layer 3: Hash Comparison (해시 비교) - 최종 검증                    │
│  ─────────────────────────────────────────────────────────────────  │
│  정규화된 결론을 SHA-256으로 비교 (완전 일치 확인)                    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Claude: sha256("middleware통합+decorator+test") = abc123...   │    │
│  │ Gemini: sha256("middleware통합+router+test") = def456...      │    │
│  │ GPT:    sha256("middleware통합+decorator+test") = abc123...   │    │
│  │                                                               │    │
│  │ → Hash Match: 2/3 (Claude == GPT)                             │    │
│  │ → 완전 합의 아님: Gemini 설득 필요                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 비교 알고리즘

```python
@dataclass
class ComparisonResult:
    """3-Layer 비교 결과"""

    # Layer 1: 의미적 비교
    semantic_similarity: float  # 0.0 ~ 1.0
    semantic_aligned: bool      # >= 0.9 면 True

    # Layer 2: 구조적 비교
    step_alignment: float       # 동일 단계 비율
    aligned_steps: list[str]    # 합의된 단계들
    disputed_steps: list[str]   # 불일치 단계들

    # Layer 3: 해시 비교
    hash_match_ratio: float     # 동일 해시 비율
    dominant_hash: str          # 가장 많은 AI가 선택한 해시
    minority_models: list[str]  # 소수 의견 모델들

    # 최종 판정
    is_full_consensus: bool
    disputed_items: list[dict]


class ThreeLayerComparator:
    """3계층 비교 시스템"""

    async def compare(self, analyses: list[AnalysisResult]) -> ComparisonResult:
        """
        3계층 비교 수행

        Args:
            analyses: 각 AI의 분석 결과 리스트

        Returns:
            ComparisonResult: 비교 결과
        """
        # Layer 1: 의미적 비교
        semantic = await self._semantic_comparison(analyses)

        # Layer 2: 구조적 비교
        structural = self._structural_comparison(analyses)

        # Layer 3: 해시 비교
        hash_result = self._hash_comparison(analyses)

        # 최종 판정: 모든 Layer에서 합의해야 100% 합의
        is_full_consensus = (
            semantic.aligned and
            len(structural.disputed_steps) == 0 and
            hash_result.match_ratio == 1.0
        )

        return ComparisonResult(
            semantic_similarity=semantic.similarity,
            semantic_aligned=semantic.aligned,
            step_alignment=structural.alignment,
            aligned_steps=structural.aligned,
            disputed_steps=structural.disputed,
            hash_match_ratio=hash_result.match_ratio,
            dominant_hash=hash_result.dominant,
            minority_models=hash_result.minorities,
            is_full_consensus=is_full_consensus,
            disputed_items=self._extract_disputed_items(semantic, structural, hash_result)
        )

    async def _semantic_comparison(self, analyses: list) -> SemanticResult:
        """
        의미적 비교: 각 AI의 핵심 결론을 의미적으로 비교

        방법:
        1. 각 분석에서 "conclusion" 필드 추출
        2. 텍스트 정규화 (소문자, 불용어 제거)
        3. 코사인 유사도 계산 (TF-IDF 기반)
        4. 모든 쌍의 평균 유사도 계산
        """
        conclusions = [a.conclusion for a in analyses]
        normalized = [self._normalize_text(c) for c in conclusions]

        # 모든 쌍의 유사도 계산
        similarities = []
        for i in range(len(normalized)):
            for j in range(i + 1, len(normalized)):
                sim = self._calculate_similarity(normalized[i], normalized[j])
                similarities.append(sim)

        avg_similarity = sum(similarities) / len(similarities)

        return SemanticResult(
            similarity=avg_similarity,
            aligned=avg_similarity >= 0.9
        )

    def _structural_comparison(self, analyses: list) -> StructuralResult:
        """
        구조적 비교: 구현 단계와 파일 목록 비교

        방법:
        1. 각 분석에서 "steps" 리스트 추출
        2. 단계별로 정규화된 키 생성
        3. 모든 AI에서 동일한 단계 찾기
        4. 불일치 단계 식별
        """
        all_steps = [set(a.steps) for a in analyses]

        # 모든 AI에서 공통된 단계
        common_steps = all_steps[0].intersection(*all_steps[1:])

        # 일부 AI에서만 있는 단계
        all_unique = set.union(*all_steps)
        disputed_steps = all_unique - common_steps

        alignment = len(common_steps) / len(all_unique) if all_unique else 1.0

        return StructuralResult(
            alignment=alignment,
            aligned=list(common_steps),
            disputed=list(disputed_steps)
        )

    def _hash_comparison(self, analyses: list) -> HashResult:
        """
        해시 비교: 정규화된 결론의 해시 비교

        방법:
        1. 결론 정규화 (공백, 대소문자, 순서 통일)
        2. SHA-256 해시 계산
        3. 동일 해시 그룹화
        4. 다수 해시 결정
        """
        hashes = {}
        for a in analyses:
            normalized = self._normalize_for_hash(a.conclusion)
            h = hashlib.sha256(normalized.encode()).hexdigest()
            if h not in hashes:
                hashes[h] = []
            hashes[h].append(a.model)

        # 가장 많은 모델이 선택한 해시
        dominant = max(hashes.items(), key=lambda x: len(x[1]))

        # 소수 의견 모델
        minorities = []
        for h, models in hashes.items():
            if h != dominant[0]:
                minorities.extend(models)

        match_ratio = len(dominant[1]) / len(analyses)

        return HashResult(
            match_ratio=match_ratio,
            dominant=dominant[0],
            minorities=minorities
        )
```

### 2.3 비교검토 출력 형식

```markdown
## 🔍 비교검토 결과 (Round 3)

### Layer 1: 의미적 비교
| 쌍 | 유사도 | 판정 |
|------|--------|------|
| Claude ↔ Gemini | 92% | ✅ 동일 의도 |
| Claude ↔ GPT | 98% | ✅ 동일 의도 |
| Gemini ↔ GPT | 90% | ✅ 동일 의도 |
| **평균** | **93.3%** | **✅ ALIGNED** |

### Layer 2: 구조적 비교
| 단계 | Claude | Gemini | GPT | 상태 |
|------|--------|--------|-----|------|
| 미들웨어 생성 | ✅ | ✅ | ✅ | ✅ 합의 |
| 데코레이터 적용 | ✅ | ❌ | ✅ | ⚠️ 불일치 |
| 라우터 수정 | ❌ | ✅ | ❌ | ⚠️ 불일치 |
| 테스트 추가 | ✅ | ✅ | ✅ | ✅ 합의 |

**구조 정렬률**: 50% (2/4 합의)

### Layer 3: 해시 비교
| 모델 | 해시 | 그룹 |
|------|------|------|
| Claude | `abc123...` | A |
| Gemini | `def456...` | B |
| GPT | `abc123...` | A |

**해시 일치율**: 66.7% (2/3)

### 최종 판정
❌ **부분 합의** - Layer 2, Layer 3 불일치

### 불일치 항목 (재토론 필요)
1. **Step 2 방식**: 데코레이터 vs 라우터 수정
   - Claude/GPT: 데코레이터 패턴 선호
   - Gemini: 라우터 직접 수정 선호

→ **다음 라운드에서 Step 2에 대해 집중 토론**
```

---

## 3. 합의 호출방식 (Consensus Protocol)

### 3.1 합의 판정 트리거

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Consensus Protocol                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                     Trigger Points                           │    │
│  │                                                               │    │
│  │  T1: 매 라운드 분석 완료 후                                   │    │
│  │      → 자동으로 3-Layer Comparison 실행                      │    │
│  │                                                               │    │
│  │  T2: 교차 검토 완료 후                                        │    │
│  │      → 반박 항목 0개면 합의 체크                              │    │
│  │                                                               │    │
│  │  T3: 재토론 후 입장 변경 시                                   │    │
│  │      → 즉시 합의 체크 (조기 종료 가능)                        │    │
│  │                                                               │    │
│  │  T4: Convergence 감지 시                                      │    │
│  │      → 의견 수렴 중이면 합의 임박 알림                        │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Consensus Levels                          │    │
│  │                                                               │    │
│  │  Level 3: FULL_CONSENSUS (100% 합의)                         │    │
│  │  ─────────────────────────────────────                       │    │
│  │  조건: Layer 1, 2, 3 모두 합의                                │    │
│  │  결과: 토론 종료, 전략 자동 실행                              │    │
│  │                                                               │    │
│  │  Level 2: NEAR_CONSENSUS (90%+ 합의)                         │    │
│  │  ─────────────────────────────────────                       │    │
│  │  조건: Layer 1 합의, Layer 2/3 일부 불일치                    │    │
│  │  결과: 마이크로 재토론 (불일치 항목만)                        │    │
│  │                                                               │    │
│  │  Level 1: PARTIAL_CONSENSUS (50-90% 합의)                    │    │
│  │  ─────────────────────────────────────                       │    │
│  │  조건: Layer 1 합의, Layer 2/3 다수 불일치                    │    │
│  │  결과: 풀 재토론                                              │    │
│  │                                                               │    │
│  │  Level 0: NO_CONSENSUS (<50% 합의)                           │    │
│  │  ─────────────────────────────────────                       │    │
│  │  조건: Layer 1도 불일치                                       │    │
│  │  결과: 근본적 재분석                                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 합의 체크 알고리즘

```python
class ConsensusProtocol:
    """합의 프로토콜"""

    def __init__(self):
        self.comparator = ThreeLayerComparator()
        self.history: list[ComparisonResult] = []

    async def check_consensus(
        self,
        analyses: list[AnalysisResult],
        trigger: str = "ROUND_COMPLETE"
    ) -> ConsensusDecision:
        """
        합의 체크 실행

        Args:
            analyses: 각 AI의 분석 결과
            trigger: 트리거 포인트 (T1/T2/T3/T4)

        Returns:
            ConsensusDecision: 합의 결정
        """
        # 3-Layer 비교 수행
        comparison = await self.comparator.compare(analyses)
        self.history.append(comparison)

        # 합의 레벨 판정
        level = self._determine_level(comparison)

        # 다음 액션 결정
        next_action = self._decide_next_action(level, comparison)

        return ConsensusDecision(
            level=level,
            comparison=comparison,
            next_action=next_action,
            trigger=trigger,
            round=len(self.history)
        )

    def _determine_level(self, comparison: ComparisonResult) -> int:
        """합의 레벨 판정"""

        # Level 3: 완전 합의
        if comparison.is_full_consensus:
            return 3

        # Level 2: 거의 합의 (90%+)
        if (comparison.semantic_aligned and
            comparison.step_alignment >= 0.9 and
            comparison.hash_match_ratio >= 0.9):
            return 2

        # Level 1: 부분 합의 (50-90%)
        if (comparison.semantic_aligned and
            comparison.step_alignment >= 0.5):
            return 1

        # Level 0: 합의 없음
        return 0

    def _decide_next_action(
        self,
        level: int,
        comparison: ComparisonResult
    ) -> NextAction:
        """다음 액션 결정"""

        if level == 3:
            return NextAction(
                type="TERMINATE",
                reason="100% 합의 도달",
                disputed_items=[]
            )

        if level == 2:
            return NextAction(
                type="MICRO_DEBATE",
                reason="90%+ 합의 - 미세 조정만 필요",
                disputed_items=comparison.disputed_items,
                focus_on=comparison.disputed_steps
            )

        if level == 1:
            return NextAction(
                type="FULL_DEBATE",
                reason="부분 합의 - 재토론 필요",
                disputed_items=comparison.disputed_items,
                minority_to_persuade=comparison.minority_models
            )

        # Level 0
        return NextAction(
            type="FUNDAMENTAL_REANALYSIS",
            reason="근본적 불일치 - 재분석 필요",
            disputed_items=comparison.disputed_items,
            require_new_approach=True
        )


class ConsensusCallManager:
    """합의 호출 관리자"""

    def __init__(self, protocol: ConsensusProtocol):
        self.protocol = protocol
        self.call_count = 0

    async def on_round_complete(self, analyses: list) -> ConsensusDecision:
        """T1: 라운드 완료 시 호출"""
        self.call_count += 1
        return await self.protocol.check_consensus(
            analyses,
            trigger="T1_ROUND_COMPLETE"
        )

    async def on_cross_review_complete(
        self,
        analyses: list,
        reviews: list[CrossReview]
    ) -> ConsensusDecision:
        """T2: 교차 검토 완료 시 호출"""
        # 반박 항목이 0개면 합의 체크
        total_rebuttals = sum(len(r.rebuttals) for r in reviews)

        if total_rebuttals == 0:
            self.call_count += 1
            return await self.protocol.check_consensus(
                analyses,
                trigger="T2_ZERO_REBUTTALS"
            )

        return ConsensusDecision(
            level=0,
            next_action=NextAction(
                type="CONTINUE_DEBATE",
                reason=f"{total_rebuttals}개 반박 존재"
            )
        )

    async def on_position_change(
        self,
        model: str,
        old_position: str,
        new_position: str,
        all_analyses: list
    ) -> ConsensusDecision:
        """T3: 입장 변경 시 즉시 호출"""
        self.call_count += 1

        # 변경된 입장으로 업데이트된 analyses로 체크
        decision = await self.protocol.check_consensus(
            all_analyses,
            trigger=f"T3_POSITION_CHANGE_{model}"
        )

        # 조기 종료 가능 여부 체크
        if decision.level >= 2:
            decision.early_termination_possible = True

        return decision

    async def on_convergence_detected(
        self,
        convergence_score: float,
        analyses: list
    ) -> ConsensusDecision:
        """T4: 수렴 감지 시 호출"""
        if convergence_score >= 0.95:
            self.call_count += 1
            return await self.protocol.check_consensus(
                analyses,
                trigger="T4_CONVERGENCE"
            )

        return ConsensusDecision(
            level=1,
            convergence_hint=True,
            convergence_score=convergence_score
        )
```

### 3.3 합의 호출 시퀀스 다이어그램

```
                    Round N 시작
                         │
                         ▼
            ┌────────────────────────┐
            │  3 AI 병렬 분석 실행    │
            └────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────┐
        │ T1: on_round_complete() 호출   │
        │ → 3-Layer Comparison 실행      │
        └────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
         [Level 3]             [Level < 3]
              │                     │
              ▼                     ▼
     ┌──────────────┐    ┌──────────────────────┐
     │ TERMINATE    │    │ 교차 검토 실행        │
     │ 토론 종료!   │    └──────────────────────┘
     └──────────────┘                │
                                     ▼
                    ┌────────────────────────────────┐
                    │ T2: on_cross_review_complete() │
                    │ → 반박 0개면 합의 체크          │
                    └────────────────────────────────┘
                                     │
                          ┌──────────┴──────────┐
                          │                     │
                   [반박 0개]              [반박 N개]
                          │                     │
                          ▼                     ▼
               ┌──────────────┐    ┌──────────────────────┐
               │ 합의 체크    │    │ 재토론 실행           │
               └──────────────┘    └──────────────────────┘
                                               │
                                               ▼
                              ┌────────────────────────────────┐
                              │ T3: on_position_change()       │
                              │ → AI 입장 변경 시 즉시 체크    │
                              └────────────────────────────────┘
                                               │
                                    ┌──────────┴──────────┐
                                    │                     │
                               [Level ≥ 2]           [Level < 2]
                                    │                     │
                                    ▼                     │
                         ┌──────────────────┐            │
                         │ 조기 종료 가능!  │            │
                         │ (90%+ 합의)      │            │
                         └──────────────────┘            │
                                                         │
                                                         ▼
                                          ┌────────────────────────┐
                                          │ T4: Convergence 체크    │
                                          │ → 수렴 중이면 힌트 제공 │
                                          └────────────────────────┘
                                                         │
                                                         ▼
                                              Round N+1 시작 (반복)
```

---

## 4. 완전 무제한 솔루션 (Unlimited Debate Engine)

### 4.1 무제한 토론의 핵심 원칙

```
┌─────────────────────────────────────────────────────────────────────┐
│                 Unlimited Debate Engine                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  🔥 핵심 원칙: "100% 합의만이 종료 조건"                             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  ❌ 라운드 제한 없음                                         │    │
│  │  ❌ 시간 제한 없음                                           │    │
│  │  ❌ 다수결 fallback 없음                                     │    │
│  │                                                               │    │
│  │  ✅ 100% 합의 = 유일한 정상 종료                             │    │
│  │  ✅ 사용자 개입 = 유일한 강제 종료                           │    │
│  │  ✅ Convergence 실패 = 전략 변경 후 재시작                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  무한루프 방지 전략:                                                 │
│  ─────────────────────────────────────                              │
│  1. Convergence 감지: 의견이 수렴하지 않으면 전략 변경               │
│  2. Mediator 개입: N라운드 후에도 불일치면 중재자 역할 부여          │
│  3. Scope 축소: 합의 가능한 범위부터 먼저 확정                       │
│  4. Perspective Shift: 새로운 관점에서 재분석 요청                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Unlimited Debate Engine 구현

```python
class UnlimitedDebateEngine:
    """무제한 끝장토론 엔진"""

    def __init__(
        self,
        task: str,
        context: str,
        ai_clients: dict[str, BaseAIClient]
    ):
        self.task = task
        self.context = context
        self.ai_clients = ai_clients

        self.round = 0
        self.protocol = ConsensusProtocol()
        self.context_manager = DebateContextManager()
        self.convergence_tracker = ConvergenceTracker()

        # 무한루프 방지 전략
        self.strategies = [
            "NORMAL",           # 일반 토론
            "MEDIATED",         # 중재자 모드
            "SCOPE_REDUCED",    # 범위 축소
            "PERSPECTIVE_SHIFT" # 관점 변경
        ]
        self.current_strategy = 0

        # 종료 조건
        self.terminated = False
        self.termination_reason = None

    async def run(self) -> DebateResult:
        """
        무제한 토론 실행

        종료 조건:
        1. 100% 합의 도달
        2. 사용자 강제 종료

        반환:
        - 합의된 최종 전략
        - 토론 히스토리 (MD 파일 경로)
        """
        while not self.terminated:
            self.round += 1

            # 현재 전략으로 라운드 실행
            round_result = await self._run_round()

            # 합의 체크
            decision = await self.protocol.check_consensus(
                round_result.analyses
            )

            # Level 3: 완전 합의
            if decision.level == 3:
                self.terminated = True
                self.termination_reason = "FULL_CONSENSUS"
                return DebateResult(
                    status="CONSENSUS_REACHED",
                    final_strategy=round_result.dominant_strategy,
                    total_rounds=self.round,
                    history_path=self.context_manager.base_path
                )

            # Convergence 체크
            convergence = self.convergence_tracker.check(
                self.protocol.history
            )

            # 수렴 실패: 전략 변경
            if convergence.is_diverging:
                await self._change_strategy()

            # 사용자 개입 체크 (비동기)
            if await self._check_user_interrupt():
                self.terminated = True
                self.termination_reason = "USER_INTERRUPT"
                return DebateResult(
                    status="USER_TERMINATED",
                    partial_consensus=decision.comparison.aligned_steps,
                    disputed_items=decision.comparison.disputed_items
                )

    async def _run_round(self) -> RoundResult:
        """단일 라운드 실행"""

        strategy = self.strategies[self.current_strategy]

        if strategy == "NORMAL":
            return await self._normal_round()

        elif strategy == "MEDIATED":
            return await self._mediated_round()

        elif strategy == "SCOPE_REDUCED":
            return await self._scope_reduced_round()

        elif strategy == "PERSPECTIVE_SHIFT":
            return await self._perspective_shift_round()

    async def _normal_round(self) -> RoundResult:
        """일반 토론 라운드"""

        # 1. 병렬 분석
        analyses = await self._parallel_analysis()

        # 2. 교차 검토
        reviews = await self._cross_review(analyses)

        # 3. 재토론 (필요시)
        if self._has_rebuttals(reviews):
            analyses = await self._debate_round(analyses, reviews)

        return RoundResult(analyses=analyses, reviews=reviews)

    async def _mediated_round(self) -> RoundResult:
        """
        중재자 모드: 한 AI가 중재자 역할

        - Claude: 중재자 (다른 AI들의 의견 조율)
        - Gemini, GPT: 토론자
        """
        # 중재자 지정 (라운드마다 로테이션)
        mediator_idx = (self.round - 1) % 3
        mediators = ["claude", "gemini", "gpt"]
        mediator = mediators[mediator_idx]
        debaters = [m for m in mediators if m != mediator]

        # 1. 토론자들의 분석
        debater_analyses = await asyncio.gather(*[
            self.ai_clients[d].analyze(self.task)
            for d in debaters
        ])

        # 2. 중재자의 조율
        mediation = await self.ai_clients[mediator].mediate(
            self.task,
            debater_analyses,
            self.protocol.history[-3:]  # 최근 3라운드 히스토리
        )

        # 3. 중재안에 대한 동의 요청
        agreements = await asyncio.gather(*[
            self.ai_clients[d].agree_or_rebut(mediation)
            for d in debaters
        ])

        return RoundResult(
            analyses=[mediation] + list(debater_analyses),
            mediation=mediation,
            agreements=agreements
        )

    async def _scope_reduced_round(self) -> RoundResult:
        """
        범위 축소 모드: 합의 가능한 부분부터 확정

        1. 이전 라운드에서 합의된 항목 확정
        2. 미합의 항목만 집중 토론
        """
        # 합의된 항목 추출
        agreed = self.protocol.history[-1].aligned_steps
        disputed = self.protocol.history[-1].disputed_steps

        # 합의된 항목 확정 저장
        self.context_manager.save_partial_consensus(
            self.round,
            agreed_items=agreed
        )

        # 미합의 항목만 집중 토론
        reduced_task = f"""
        다음 항목에 대해서만 논의하세요:

        ## 합의 필요 항목
        {self._format_items(disputed)}

        ## 이미 합의된 항목 (변경 금지)
        {self._format_items(agreed)}
        """

        analyses = await self._parallel_analysis(reduced_task)

        return RoundResult(
            analyses=analyses,
            scope="REDUCED",
            fixed_items=agreed
        )

    async def _perspective_shift_round(self) -> RoundResult:
        """
        관점 변경 모드: 새로운 시각에서 재분석

        각 AI에게 다른 역할/관점 부여:
        - Claude: 보수적 관점 (안정성 우선)
        - Gemini: 혁신적 관점 (효율성 우선)
        - GPT: 실용적 관점 (구현 용이성 우선)
        """
        perspectives = {
            "claude": "보수적 관점 (안정성, 호환성 우선)",
            "gemini": "혁신적 관점 (효율성, 최신 기술 우선)",
            "gpt": "실용적 관점 (구현 용이성, 유지보수 우선)"
        }

        analyses = await asyncio.gather(*[
            self.ai_clients[model].analyze_with_perspective(
                self.task,
                perspective
            )
            for model, perspective in perspectives.items()
        ])

        # 관점별 분석 후 공통점 찾기
        common_ground = await self._find_common_ground(analyses)

        return RoundResult(
            analyses=analyses,
            perspectives=perspectives,
            common_ground=common_ground
        )

    async def _change_strategy(self) -> None:
        """전략 변경 (무한루프 방지)"""

        self.current_strategy = (self.current_strategy + 1) % len(self.strategies)

        # 모든 전략 시도 후에도 실패하면 사용자 알림
        if self.current_strategy == 0:
            await self._notify_user(
                "모든 토론 전략을 시도했지만 합의에 도달하지 못했습니다. "
                "토론을 계속하시겠습니까?"
            )


class ConvergenceTracker:
    """수렴 추적기"""

    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.history: list[float] = []

    def check(self, comparison_history: list[ComparisonResult]) -> ConvergenceStatus:
        """
        수렴 여부 체크

        수렴 조건:
        - 최근 N라운드의 합의율이 계속 증가
        - 또는 90% 이상 유지

        발산 조건:
        - 최근 N라운드의 합의율이 계속 감소
        - 또는 계속 동일 (정체)
        """
        if len(comparison_history) < self.window_size:
            return ConvergenceStatus(is_converging=True, is_diverging=False)

        recent = comparison_history[-self.window_size:]
        consensus_rates = [c.hash_match_ratio for c in recent]

        # 추세 계산
        trend = self._calculate_trend(consensus_rates)

        if trend > 0.01:  # 증가 추세
            return ConvergenceStatus(
                is_converging=True,
                is_diverging=False,
                trend=trend,
                estimated_rounds_to_consensus=self._estimate_rounds(consensus_rates)
            )

        if trend < -0.01:  # 감소 추세
            return ConvergenceStatus(
                is_converging=False,
                is_diverging=True,
                trend=trend,
                recommendation="STRATEGY_CHANGE"
            )

        # 정체
        return ConvergenceStatus(
            is_converging=False,
            is_diverging=False,
            trend=0,
            recommendation="STRATEGY_CHANGE"
        )

    def _calculate_trend(self, values: list[float]) -> float:
        """선형 회귀로 추세 계산"""
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        return numerator / denominator if denominator != 0 else 0

    def _estimate_rounds(self, values: list[float]) -> int:
        """100% 도달까지 예상 라운드 수"""
        if values[-1] >= 1.0:
            return 0

        trend = self._calculate_trend(values)
        if trend <= 0:
            return -1  # 도달 불가

        remaining = 1.0 - values[-1]
        return int(remaining / trend) + 1
```

### 4.3 무한루프 방지 전략 상세

```
┌─────────────────────────────────────────────────────────────────────┐
│              Infinite Loop Prevention Strategies                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Strategy 1: NORMAL (라운드 1-10)                                    │
│  ─────────────────────────────────                                  │
│  일반적인 토론 진행                                                  │
│  → 대부분의 작업은 여기서 합의 도달                                   │
│                                                                      │
│  Strategy 2: MEDIATED (라운드 11-20)                                │
│  ─────────────────────────────────                                  │
│  중재자 모드 활성화                                                  │
│  → 한 AI가 다른 AI들의 의견을 조율                                   │
│  → 중재자는 라운드마다 로테이션                                      │
│                                                                      │
│  Strategy 3: SCOPE_REDUCED (라운드 21-30)                           │
│  ─────────────────────────────────                                  │
│  합의된 부분 확정, 미합의 부분만 토론                                 │
│  → 점진적 합의 확대                                                  │
│  → 작은 성공 축적                                                    │
│                                                                      │
│  Strategy 4: PERSPECTIVE_SHIFT (라운드 31+)                         │
│  ─────────────────────────────────                                  │
│  관점 변경 후 재분석                                                 │
│  → 막힌 상황 돌파                                                    │
│  → 새로운 공통점 발견                                                │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    전략 순환 사이클                          │    │
│  │                                                               │    │
│  │  NORMAL → MEDIATED → SCOPE_REDUCED → PERSPECTIVE_SHIFT      │    │
│  │     ↑                                          │              │    │
│  │     └──────────────────────────────────────────┘              │    │
│  │                                                               │    │
│  │  모든 전략 순환 후에도 합의 실패 시:                           │    │
│  │  → 사용자에게 개입 요청                                       │    │
│  │  → "모든 전략 시도했으나 합의 실패. 계속하시겠습니까?"        │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Context 최적화 (MD 파일 시스템)

### 5.1 파일 구조

```
.claude/debates/
├── {task_id}/                          # 작업별 폴더
│   ├── TASK.md                         # 원본 작업 정의
│   ├── CONFIG.yaml                     # 토론 설정
│   │
│   ├── round_001/                      # 라운드별 폴더 (무제한)
│   │   ├── claude.md                   # Claude 분석
│   │   ├── gemini.md                   # Gemini 분석
│   │   ├── gpt.md                      # GPT 분석
│   │   ├── COMPARISON.md               # 3-Layer 비교 결과
│   │   └── CONSENSUS.md                # 합의 판정 결과
│   │
│   ├── cross_review/
│   │   ├── round_001/
│   │   │   ├── claude_reviews_gemini.md
│   │   │   ├── claude_reviews_gpt.md
│   │   │   └── ...
│   │   └── round_002/
│   │       └── ...
│   │
│   ├── debates/                        # 재토론 기록
│   │   ├── round_001/
│   │   │   ├── claude_rebuttal.md
│   │   │   └── ...
│   │   └── round_002/
│   │       └── ...
│   │
│   ├── strategies/                     # 전략 변경 기록
│   │   ├── strategy_change_011.md      # 11라운드에서 MEDIATED로
│   │   └── strategy_change_021.md      # 21라운드에서 SCOPE_REDUCED로
│   │
│   ├── PARTIAL_CONSENSUS.md            # 부분 합의 확정 내역
│   ├── CONVERGENCE.md                  # 수렴 추적 로그
│   └── FINAL.md                        # 최종 결과
│
└── index.yaml                          # 전체 토론 인덱스
```

### 5.2 Context 절약 효과

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Context 절약 분석                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  기존 방식 (Context 내 유지)                                         │
│  ───────────────────────────                                        │
│  Round 1:  ~3KB (3 AI 분석)                                         │
│  Round 2:  ~6KB (누적)                                              │
│  Round 5:  ~15KB (누적)                                             │
│  Round 10: ~30KB (누적)                                             │
│  → Context 소비: 15-30% (위험 수준)                                 │
│                                                                      │
│  MD 파일 방식 (v4.0)                                                │
│  ────────────────────                                               │
│  Round N:  ~0.5KB (요약만 Context 유지)                             │
│  → Context 소비: 3-5% (안전 수준)                                   │
│  → 97% 절약!                                                        │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Context 내 유지되는 정보 (최소화)                           │    │
│  │                                                               │    │
│  │  {                                                            │    │
│  │    "task_id": "api-refactor-001",                             │    │
│  │    "current_round": 7,                                        │    │
│  │    "current_strategy": "MEDIATED",                            │    │
│  │    "consensus_level": 2,                                      │    │
│  │    "convergence_trend": 0.03,                                 │    │
│  │    "disputed_items": ["step_2_implementation"],               │    │
│  │    "files_path": ".claude/debates/api-refactor-001/"          │    │
│  │  }                                                            │    │
│  │                                                               │    │
│  │  → 약 300 bytes만 Context 유지                                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 6. /auto 통합

### 6.1 자동 끝장토론 트리거

```python
# auto_executor.py 수정

class AutoExecutor:
    """자동 실행기 (끝장토론 통합)"""

    async def execute(self, task: str) -> ExecutionResult:
        """
        모든 /auto 작업에서 자동으로 끝장토론 실행

        Args:
            task: 실행할 작업

        Returns:
            ExecutionResult: 실행 결과
        """
        # 1. 끝장토론 엔진 초기화
        engine = UnlimitedDebateEngine(
            task=task,
            context=self._get_project_context(),
            ai_clients=self._get_ai_clients()
        )

        # 2. 무제한 토론 실행 (100% 합의까지)
        debate_result = await engine.run()

        # 3. 합의 도달 시 자동 실행
        if debate_result.status == "CONSENSUS_REACHED":
            execution = await self._execute_strategy(
                debate_result.final_strategy
            )
            return ExecutionResult(
                status="COMPLETED",
                debate=debate_result,
                execution=execution
            )

        # 4. 사용자 종료 시
        return ExecutionResult(
            status="USER_TERMINATED",
            debate=debate_result,
            partial_consensus=debate_result.partial_consensus
        )


# /auto 커맨드 옵션
"""
/auto "작업"                    # 끝장토론 + 자동 실행 (기본)
/auto "작업" --no-debate        # 토론 건너뛰기
/auto "작업" --debate-only      # 토론만, 실행 안함
/auto debate-status             # 진행 중인 토론 상태
/auto debate-log {task_id}      # 토론 로그 확인
"""
```

### 6.2 사용자 인터페이스

```
/auto "API 리팩토링"

🔥 끝장토론 시작...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Round 1 | Strategy: NORMAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 분석 중...
  Claude: ████████████████████ 완료
  Gemini: ████████████████████ 완료
  GPT:    ████████████████████ 완료

🔍 3-Layer 비교 중...
  Layer 1 (의미): 95% ✅
  Layer 2 (구조): 75% ⚠️
  Layer 3 (해시): 67% ⚠️

📋 합의 상태: Level 1 (PARTIAL_CONSENSUS)
  - 합의: 3개 항목
  - 불일치: 1개 항목 (Step 2 구현 방식)

→ 교차 검토 시작...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Round 2 | Strategy: NORMAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 재토론 중...
  - 논쟁: Step 2 구현 방식
  - Claude/GPT: 데코레이터 패턴
  - Gemini: 라우터 직접 수정

💬 Gemini 입장 변경 감지!
  이전: "라우터 직접 수정"
  현재: "데코레이터 패턴에 동의"

🎯 T3 트리거: 즉시 합의 체크...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 100% 합의 도달! (Round 2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 최종 전략 (3 AI 만장일치)

1. ✅ auth_middleware.py 생성
2. ✅ 데코레이터 패턴으로 권한 적용
3. ✅ 기존 엔드포인트 리팩토링
4. ✅ 테스트 커버리지 80% 확보

📁 토론 로그: .claude/debates/api-refactor-001/

→ 자동 실행 시작...
```

---

## 7. 저장 방식 및 청킹 전략 (Storage & Chunking Strategy)

### 7.1 프로젝트/스킬 정의 (Identity Decision)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Ultimate Debate: 정체성 정의                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ❓ 별도 프로젝트인가? 스킬인가?                                     │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                                                               │    │
│  │  🎯 결론: **Hybrid Architecture (하이브리드 아키텍처)**       │    │
│  │                                                               │    │
│  │  ┌─────────────────┐      ┌─────────────────┐                │    │
│  │  │   Core Engine   │      │   Skill Layer   │                │    │
│  │  │   (독립 패키지)  │ ───► │   (통합 인터페이스) │                │    │
│  │  └─────────────────┘      └─────────────────┘                │    │
│  │          │                        │                           │    │
│  │          │                        │                           │    │
│  │          ▼                        ▼                           │    │
│  │  ┌─────────────────┐      ┌─────────────────┐                │    │
│  │  │ 재사용 가능한    │      │ Claude Code     │                │    │
│  │  │ Python 패키지   │      │ /auto 통합      │                │    │
│  │  └─────────────────┘      └─────────────────┘                │    │
│  │                                                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  이유:                                                               │
│  ─────                                                              │
│  1. Core Engine은 다른 프로젝트에서도 재사용 가능해야 함              │
│  2. Claude Code 통합은 Skill 형태가 가장 자연스러움                  │
│  3. 독립 실행도, /auto 통합도 모두 지원 필요                         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 디렉토리 구조 (최종)

```
C:\claude\
├── packages/                              # 📦 독립 패키지 (Core Engine)
│   └── ultimate-debate/
│       ├── pyproject.toml                 # 패키지 설정
│       ├── README.md
│       ├── src/
│       │   └── ultimate_debate/
│       │       ├── __init__.py
│       │       ├── engine.py              # UnlimitedDebateEngine
│       │       ├── comparison/
│       │       │   ├── __init__.py
│       │       │   ├── semantic.py        # Layer 1
│       │       │   ├── structural.py      # Layer 2
│       │       │   └── hash.py            # Layer 3
│       │       ├── consensus/
│       │       │   ├── __init__.py
│       │       │   ├── protocol.py        # ConsensusProtocol
│       │       │   └── tracker.py         # ConvergenceTracker
│       │       ├── strategies/
│       │       │   ├── __init__.py
│       │       │   ├── normal.py
│       │       │   ├── mediated.py
│       │       │   ├── scope_reduced.py
│       │       │   └── perspective_shift.py
│       │       └── storage/
│       │           ├── __init__.py
│       │           ├── context_manager.py # MD 파일 관리
│       │           └── chunker.py         # 청킹 전략
│       └── tests/
│           └── ...
│
├── .claude/
│   ├── skills/
│   │   └── ultimate-debate/               # 🔌 Skill Layer (통합)
│   │       ├── SKILL.md
│   │       └── scripts/
│   │           ├── __init__.py
│   │           ├── main.py                # CLI + /auto 통합
│   │           └── adapter.py             # Core Engine 어댑터
│   │
│   └── debates/                           # 💾 토론 데이터 저장소
│       ├── index.yaml                     # 전체 인덱스
│       └── {task_id}/                     # 작업별 폴더
│           └── ...
```

### 7.3 저장 방식 상세

#### 7.3.1 파일 유형별 저장 전략

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Storage Strategy by File Type                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Type 1: Analysis Files (분석 파일)                                  │
│  ──────────────────────────────────                                 │
│  위치: .claude/debates/{task_id}/round_{N}/{model}.md               │
│  크기: 평균 2-5KB                                                   │
│  보관: 영구 (토론 히스토리)                                          │
│                                                                      │
│  Type 2: Comparison Files (비교 결과)                                │
│  ──────────────────────────────────                                 │
│  위치: .claude/debates/{task_id}/round_{N}/COMPARISON.md            │
│  크기: 평균 1-2KB                                                   │
│  보관: 영구                                                          │
│                                                                      │
│  Type 3: State Files (상태 파일)                                     │
│  ──────────────────────────────────                                 │
│  위치: .claude/debates/{task_id}/STATE.yaml                         │
│  크기: ~500 bytes                                                   │
│  보관: 토론 진행 중에만 (완료 후 FINAL.md로 통합)                     │
│                                                                      │
│  Type 4: Index Files (인덱스)                                        │
│  ──────────────────────────────────                                 │
│  위치: .claude/debates/index.yaml                                   │
│  크기: 토론 개수 × ~100 bytes                                       │
│  보관: 영구 (전체 토론 목록)                                         │
│                                                                      │
│  Type 5: Cache Files (캐시)                                          │
│  ──────────────────────────────────                                 │
│  위치: .claude/debates/.cache/                                      │
│  크기: 가변                                                          │
│  보관: 7일 후 자동 삭제                                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 7.3.2 MD 파일 포맷 표준

```markdown
---
# YAML Frontmatter (메타데이터)
task_id: "api-refactor-001"
round: 3
model: "claude"
timestamp: "2026-01-18T15:30:00Z"
hash: "abc123..."
status: "completed"
---

# Round 3 - Claude Analysis

## Summary (요약 - Context 로딩용)
<!-- CHUNK:SUMMARY:START -->
인증 미들웨어 통합 제안. 데코레이터 패턴 권장.
<!-- CHUNK:SUMMARY:END -->

## Full Analysis (전체 분석)
<!-- CHUNK:FULL:START -->
### 1. 현황 분석
- 현재 15개 엔드포인트에 인증 로직 분산
- 코드 중복률 40%
...

### 2. 제안 전략
1. auth_middleware.py 신규 생성
2. 데코레이터 패턴으로 권한 적용
...
<!-- CHUNK:FULL:END -->

## Conclusion (결론)
<!-- CHUNK:CONCLUSION:START -->
auth_middleware.py로 인증 통합, 데코레이터 패턴 적용
<!-- CHUNK:CONCLUSION:END -->
```

### 7.4 청킹 전략 (Chunking Strategy)

#### 7.4.1 청크 유형

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Chunking Strategy                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  청크 유형 및 용도:                                                  │
│  ──────────────────                                                 │
│                                                                      │
│  ┌─────────────┬──────────┬────────────────────────────────────┐   │
│  │ 청크 유형   │ 크기     │ 용도                                │   │
│  ├─────────────┼──────────┼────────────────────────────────────┤   │
│  │ SUMMARY     │ ~200자   │ Context 유지 (항상 로드)            │   │
│  │ CONCLUSION  │ ~500자   │ 합의 비교용 (비교 시 로드)          │   │
│  │ FULL        │ ~3000자  │ 상세 분석 (필요 시 로드)            │   │
│  │ METADATA    │ ~100자   │ 인덱싱용 (항상 로드)                │   │
│  └─────────────┴──────────┴────────────────────────────────────┘   │
│                                                                      │
│  로딩 전략:                                                          │
│  ──────────                                                         │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                                                                │   │
│  │  Level 0: METADATA only (~100 bytes/file)                     │   │
│  │  └─ 인덱스 조회, 상태 확인                                     │   │
│  │                                                                │   │
│  │  Level 1: METADATA + SUMMARY (~300 bytes/file)                │   │
│  │  └─ Context 유지, 진행 상황 표시                               │   │
│  │                                                                │   │
│  │  Level 2: + CONCLUSION (~800 bytes/file)                      │   │
│  │  └─ 합의 비교, 해시 계산                                       │   │
│  │                                                                │   │
│  │  Level 3: + FULL (~4000 bytes/file)                           │   │
│  │  └─ 상세 분석 필요 시에만                                      │   │
│  │                                                                │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### 7.4.2 청킹 구현

```python
class ChunkManager:
    """청크 기반 파일 관리"""

    CHUNK_MARKERS = {
        "SUMMARY": ("<!-- CHUNK:SUMMARY:START -->", "<!-- CHUNK:SUMMARY:END -->"),
        "CONCLUSION": ("<!-- CHUNK:CONCLUSION:START -->", "<!-- CHUNK:CONCLUSION:END -->"),
        "FULL": ("<!-- CHUNK:FULL:START -->", "<!-- CHUNK:FULL:END -->"),
    }

    def __init__(self, base_path: Path):
        self.base_path = base_path

    def load_chunk(self, file_path: Path, chunk_type: str) -> str:
        """특정 청크만 로드

        Args:
            file_path: MD 파일 경로
            chunk_type: SUMMARY | CONCLUSION | FULL

        Returns:
            청크 내용
        """
        content = file_path.read_text(encoding="utf-8")
        start_marker, end_marker = self.CHUNK_MARKERS[chunk_type]

        start_idx = content.find(start_marker)
        end_idx = content.find(end_marker)

        if start_idx == -1 or end_idx == -1:
            return ""

        return content[start_idx + len(start_marker):end_idx].strip()

    def load_level(self, file_path: Path, level: int) -> dict[str, str]:
        """레벨별 청크 로드

        Args:
            file_path: MD 파일 경로
            level: 0-3

        Returns:
            청크 딕셔너리
        """
        result = {"metadata": self._load_frontmatter(file_path)}

        if level >= 1:
            result["summary"] = self.load_chunk(file_path, "SUMMARY")

        if level >= 2:
            result["conclusion"] = self.load_chunk(file_path, "CONCLUSION")

        if level >= 3:
            result["full"] = self.load_chunk(file_path, "FULL")

        return result

    def load_for_comparison(self, task_id: str, round_num: int) -> list[dict]:
        """비교용 로드 (Level 2)

        3개 AI의 결론만 로드하여 비교 수행
        """
        models = ["claude", "gemini", "gpt"]
        results = []

        for model in models:
            file_path = self.base_path / task_id / f"round_{round_num:03d}" / f"{model}.md"
            if file_path.exists():
                data = self.load_level(file_path, level=2)
                data["model"] = model
                results.append(data)

        return results

    def load_for_context(self, task_id: str) -> dict:
        """Context 유지용 로드 (Level 1)

        최소한의 정보만 로드하여 Context 절약
        """
        task_path = self.base_path / task_id

        # STATE.yaml에서 현재 상태 로드
        state_file = task_path / "STATE.yaml"
        if state_file.exists():
            state = yaml.safe_load(state_file.read_text())
        else:
            state = {}

        # 최신 라운드의 요약만 로드
        current_round = state.get("current_round", 0)
        summaries = {}

        for model in ["claude", "gemini", "gpt"]:
            file_path = task_path / f"round_{current_round:03d}" / f"{model}.md"
            if file_path.exists():
                summaries[model] = self.load_chunk(file_path, "SUMMARY")

        return {
            "task_id": task_id,
            "state": state,
            "current_summaries": summaries,
            # 전체 내용은 로드하지 않음 (Context 절약)
        }


class ContextOptimizer:
    """Context 최적화 관리"""

    # Context 내 유지되는 최대 크기
    MAX_CONTEXT_SIZE = 500  # bytes

    def __init__(self, chunk_manager: ChunkManager):
        self.chunk_manager = chunk_manager

    def get_context_snapshot(self, task_id: str) -> dict:
        """Context에 유지할 최소 스냅샷 생성

        Returns:
            ~300 bytes 크기의 스냅샷
        """
        data = self.chunk_manager.load_for_context(task_id)

        # 요약 압축 (각 모델당 50자 제한)
        compressed_summaries = {
            model: summary[:50] + "..." if len(summary) > 50 else summary
            for model, summary in data.get("current_summaries", {}).items()
        }

        return {
            "task_id": task_id,
            "round": data["state"].get("current_round", 0),
            "strategy": data["state"].get("current_strategy", "NORMAL"),
            "consensus_level": data["state"].get("consensus_level", 0),
            "summaries": compressed_summaries,
            "files_path": f".claude/debates/{task_id}/"
        }

    def estimate_context_usage(self, snapshot: dict) -> int:
        """Context 사용량 추정"""
        import json
        return len(json.dumps(snapshot, ensure_ascii=False))
```

#### 7.4.3 자동 정리 전략

```python
class StorageCleaner:
    """저장소 자동 정리"""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.cache_path = base_path / ".cache"

    async def cleanup(self) -> CleanupResult:
        """정리 작업 실행

        1. 7일 이상 된 캐시 삭제
        2. 완료된 토론의 STATE.yaml → FINAL.md 통합
        3. 오래된 토론 아카이브 (30일+)
        """
        deleted_cache = await self._cleanup_cache(days=7)
        merged_states = await self._merge_completed_states()
        archived = await self._archive_old_debates(days=30)

        return CleanupResult(
            deleted_cache_files=deleted_cache,
            merged_state_files=merged_states,
            archived_debates=archived
        )

    async def _cleanup_cache(self, days: int) -> int:
        """오래된 캐시 삭제"""
        if not self.cache_path.exists():
            return 0

        cutoff = datetime.now() - timedelta(days=days)
        deleted = 0

        for file in self.cache_path.glob("**/*"):
            if file.is_file():
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                if mtime < cutoff:
                    file.unlink()
                    deleted += 1

        return deleted

    async def _archive_old_debates(self, days: int) -> int:
        """오래된 토론 아카이브"""
        archive_path = self.base_path / "archive"
        archive_path.mkdir(exist_ok=True)

        cutoff = datetime.now() - timedelta(days=days)
        archived = 0

        for task_dir in self.base_path.iterdir():
            if not task_dir.is_dir() or task_dir.name.startswith("."):
                continue

            final_file = task_dir / "FINAL.md"
            if final_file.exists():
                mtime = datetime.fromtimestamp(final_file.stat().st_mtime)
                if mtime < cutoff:
                    # ZIP으로 압축 후 이동
                    archive_file = archive_path / f"{task_dir.name}.zip"
                    shutil.make_archive(
                        str(archive_file.with_suffix("")),
                        "zip",
                        task_dir
                    )
                    shutil.rmtree(task_dir)
                    archived += 1

        return archived
```

### 7.5 인덱스 관리

```yaml
# .claude/debates/index.yaml

version: "1.0"
last_updated: "2026-01-18T15:30:00Z"

debates:
  - task_id: "api-refactor-001"
    created_at: "2026-01-18T10:00:00Z"
    status: "completed"  # running | completed | archived
    total_rounds: 2
    final_consensus: true
    strategy_used: ["NORMAL"]
    summary: "API 인증 미들웨어 통합"

  - task_id: "db-migration-002"
    created_at: "2026-01-18T14:00:00Z"
    status: "running"
    current_round: 5
    current_strategy: "MEDIATED"
    consensus_level: 2

statistics:
  total_debates: 15
  completed: 12
  running: 2
  archived: 1
  avg_rounds_to_consensus: 2.8
  strategy_effectiveness:
    NORMAL: 0.85
    MEDIATED: 0.92
    SCOPE_REDUCED: 0.78
    PERSPECTIVE_SHIFT: 0.65
```

---

## 8. 프로젝트 vs 스킬 아키텍처 결정

### 8.1 하이브리드 아키텍처 상세

```
┌─────────────────────────────────────────────────────────────────────┐
│              Hybrid Architecture Decision                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Why Hybrid?                               │    │
│  │                                                               │    │
│  │  Option A: 순수 스킬 (Pure Skill)                            │    │
│  │  ────────────────────────────────                           │    │
│  │  ✅ Claude Code 통합 간단                                    │    │
│  │  ❌ 다른 프로젝트에서 재사용 불가                             │    │
│  │  ❌ 패키지 배포 불가                                         │    │
│  │                                                               │    │
│  │  Option B: 순수 패키지 (Pure Package)                        │    │
│  │  ────────────────────────────────                           │    │
│  │  ✅ pip install 가능                                         │    │
│  │  ✅ 다른 프로젝트에서 재사용 가능                             │    │
│  │  ❌ Claude Code /auto 통합 번거로움                          │    │
│  │                                                               │    │
│  │  Option C: 하이브리드 (Hybrid) ✅ 선택                       │    │
│  │  ────────────────────────────────                           │    │
│  │  ✅ Core Engine은 독립 패키지로 재사용 가능                   │    │
│  │  ✅ Skill Layer로 Claude Code 자연스럽게 통합                │    │
│  │  ✅ 두 가지 사용 방식 모두 지원                               │    │
│  │                                                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 사용 방식

```python
# 방식 1: 독립 패키지로 사용 (다른 프로젝트)
# ──────────────────────────────────────────

from ultimate_debate import UnlimitedDebateEngine
from ultimate_debate.clients import ClaudeClient, GeminiClient, GPTClient

engine = UnlimitedDebateEngine(
    task="API 리팩토링 전략",
    clients={
        "claude": ClaudeClient(api_key="..."),
        "gemini": GeminiClient(api_key="..."),
        "gpt": GPTClient(api_key="...")
    }
)

result = await engine.run()
print(result.final_strategy)


# 방식 2: Claude Code 스킬로 사용
# ──────────────────────────────────────────

# /auto "API 리팩토링"
# → 자동으로 Ultimate Debate 실행
# → 100% 합의 후 자동 구현


# 방식 3: CLI 직접 실행
# ──────────────────────────────────────────

# python -m ultimate_debate --task "API 리팩토링"
# python -m ultimate_debate --status --task-id debate_001
# python -m ultimate_debate --resume --task-id debate_001
```

### 8.3 패키지 구조

```toml
# packages/ultimate-debate/pyproject.toml

[project]
name = "ultimate-debate"
version = "1.0.0"
description = "Multi-AI Unlimited Debate Engine with 100% Consensus"
authors = [
    {name = "Claude Code", email = "noreply@anthropic.com"}
]
requires-python = ">=3.12"

dependencies = [
    "httpx>=0.27.0",
    "pyyaml>=6.0",
    "rich>=13.0",  # CLI 출력용
]

[project.optional-dependencies]
claude = ["anthropic>=0.40.0"]
openai = ["openai>=1.50.0"]
google = ["google-generativeai>=0.8.0"]
all = ["anthropic>=0.40.0", "openai>=1.50.0", "google-generativeai>=0.8.0"]

[project.scripts]
ultimate-debate = "ultimate_debate.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 8.4 Skill Adapter

```python
# .claude/skills/ultimate-debate/scripts/adapter.py

"""Skill Layer: Core Engine을 Claude Code에 통합"""

import sys
from pathlib import Path

# Core Engine import (packages/ 또는 pip install)
try:
    from ultimate_debate import UnlimitedDebateEngine
    from ultimate_debate.storage import ChunkManager
except ImportError:
    # 로컬 개발 환경: packages/ 경로 추가
    packages_path = Path(__file__).parent.parent.parent.parent.parent / "packages" / "ultimate-debate" / "src"
    sys.path.insert(0, str(packages_path))
    from ultimate_debate import UnlimitedDebateEngine
    from ultimate_debate.storage import ChunkManager


class SkillAdapter:
    """Claude Code Skill Adapter"""

    def __init__(self):
        self.engine = None
        self.chunk_manager = ChunkManager(Path(".claude/debates"))

    async def start_debate(self, task: str) -> dict:
        """새 토론 시작 (/auto 연동)"""
        self.engine = UnlimitedDebateEngine(
            task=task,
            storage_path=Path(".claude/debates")
        )

        result = await self.engine.run()

        return {
            "status": result.status,
            "task_id": result.task_id,
            "total_rounds": result.total_rounds,
            "final_strategy": result.final_strategy,
            "history_path": str(result.history_path)
        }

    def get_context_snapshot(self, task_id: str) -> dict:
        """Context 최소화 스냅샷 (Main Context 유지용)"""
        from ultimate_debate.storage import ContextOptimizer

        optimizer = ContextOptimizer(self.chunk_manager)
        return optimizer.get_context_snapshot(task_id)

    async def resume_debate(self, task_id: str) -> dict:
        """중단된 토론 재개"""
        state = self.chunk_manager.load_for_context(task_id)

        self.engine = UnlimitedDebateEngine.from_state(
            state,
            storage_path=Path(".claude/debates")
        )

        return await self.engine.run()
```

### 8.5 배포 전략

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Deployment Strategy                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Phase 1: 로컬 개발 (✅ 완료)                                        │
│  ─────────────────────────────                                      │
│  - ultimate-debate/ 서브 레포에 Core Engine (독립 Git)              │
│  - .claude/skills/ultimate-debate/ 에 Skill Adapter 개발            │
│  - adapter.py를 통한 경로 import                                     │
│                                                                      │
│  Phase 2: PyPI 배포 (선택적)                                         │
│  ─────────────────────────────                                      │
│  - pip install ultimate-debate                                      │
│  - 다른 프로젝트에서 import 가능                                     │
│  - Skill Adapter는 pip install 버전 사용                            │
│                                                                      │
│  Phase 3: Claude Code 기본 통합 (미래)                               │
│  ─────────────────────────────                                      │
│  - /auto --debate 기본 옵션으로 제공                                 │
│  - 별도 스킬 설치 없이 사용 가능                                     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 9. 체크리스트

### 구현 체크리스트 (2026-01-18 업데이트)

- [x] 3-Layer Comparison System 구현 (⚠️ 부분 완료)
  - [x] Semantic Comparator (의미 비교) - `comparison/semantic.py` TF-IDF 구현
  - [ ] Structural Comparator (구조 비교) - `comparison/structural.py` placeholder
  - [x] Hash Comparator (해시 비교) - `consensus/protocol.py` 내장
- [x] Consensus Protocol 구현 (✅ 완료)
  - [x] ConsensusChecker (4단계 합의) - `consensus/protocol.py`
  - [x] ConsensusResult 데이터 구조 - FULL/PARTIAL/NO_CONSENSUS
- [x] Unlimited Debate Engine 구현 (⚠️ 부분 완료)
  - [x] 5-Phase 토론 루프 - `engine.py`
  - [x] NORMAL 전략 - `strategies/normal.py`
  - [ ] MEDIATED 전략 - 파일만 존재
  - [ ] SCOPE_REDUCED 전략 - 파일만 존재
  - [ ] PERSPECTIVE_SHIFT 전략 - 파일만 존재
  - [x] ConvergenceTracker - `consensus/tracker.py`
- [x] Storage & Chunking 구현 (✅ 완료)
  - [x] ChunkManager (4-Level 청킹) - `storage/chunker.py`
  - [x] DebateContextManager (MD 저장) - `storage/context_manager.py`
  - [ ] StorageCleaner (자동 정리) - 미구현
- [x] Hybrid Architecture 구현 (✅ 완료)
  - [x] ultimate-debate/ 서브 레포 Core Engine (독립 Git)
  - [x] .claude/skills/ultimate-debate/ Skill Adapter
  - [x] adapter.py 브릿지 패턴
- [ ] /auto 통합
  - [ ] 자동 끝장토론 트리거
  - [ ] 사용자 인터페이스
- [ ] 실제 AI 클라이언트 연동
  - [ ] GPT 클라이언트 (multi-ai-auth 연동)
  - [ ] Gemini 클라이언트 (multi-ai-auth 연동)

### 검증 체크리스트

- [ ] 100% 합의 도달 테스트
- [ ] 무한루프 방지 테스트 (전략 순환)
- [ ] Context 소비량 측정 (<5%)
- [ ] 10라운드 이상 지속 토론 테스트
- [ ] 사용자 강제 종료 테스트
- [ ] 청킹 로드/저장 테스트
- [ ] 자동 정리 테스트

---

## 10. 구현 상태 (Implementation Status)

> **마지막 업데이트**: 2026-01-18

### 10.1 전체 구현율: 75.5%

| 구성 요소 | 상태 | 구현율 |
|----------|------|--------|
| 5-Phase 워크플로우 | ✅ 완료 | 100% |
| 합의 프로토콜 | ✅ 완료 | 100% |
| 3-Layer 비교 시스템 | ⚠️ 부분 | 67% |
| 4가지 전략 | ⚠️ 부분 | 25% |
| 청킹 시스템 | ✅ 완료 | 100% |
| Hybrid Architecture | ✅ 완료 | 100% |
| AI 클라이언트 연동 | ❌ 미구현 | 0% |

### 10.2 스킬-엔진 인과관계 맵

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SKILL LAYER (Claude Code 통합)                    │
│                                                                      │
│   C:\claude\.claude\skills\ultimate-debate\                         │
│   ├── SKILL.md           (스킬 정의 문서)                            │
│   └── scripts/                                                       │
│       ├── main.py        (CLI 진입점)                                │
│       ├── adapter.py     (★ 핵심 브릿지)                             │
│       └── debate/        (레거시 fallback)                           │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                    adapter.py   │   레거시 모드
                    성공 시      │   (fallback)
                         ┌──────┴──────┐
                         │             │
                         ▼             ▼
┌─────────────────────────────┐  ┌──────────────────────────┐
│      CORE ENGINE            │  │  LEGACY (debate/)        │
│  (독립 서브 레포)           │  │  동일 구조, 직접 포함    │
│                             │  │                          │
│  C:\claude\ultimate-debate\ │  │  scripts/debate/         │
│  ├── .git/                  │  │  ├── orchestrator.py     │
│  ├── src/ultimate_debate/   │  │  ├── consensus_checker.py│
│  │   ├── engine.py          │  │  └── context_manager.py  │
│  │   ├── consensus/         │  │                          │
│  │   ├── comparison/        │  └──────────────────────────┘
│  │   ├── strategies/        │
│  │   └── storage/           │
│  └── tests/                 │
└─────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        STORAGE (MD 파일)                             │
│                                                                      │
│   .claude/debates/{task_id}/                                        │
│   ├── TASK.md              (작업 정의)                              │
│   ├── round_00/            (라운드별 저장)                          │
│   │   ├── claude.md        (Claude 분석)                            │
│   │   ├── gpt.md           (GPT 분석)                               │
│   │   ├── gemini.md        (Gemini 분석)                            │
│   │   ├── CONSENSUS.md     (합의 결과)                              │
│   │   └── reviews/         (교차 검토)                              │
│   ├── round_01/                                                     │
│   └── FINAL.md             (최종 결론)                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 10.3 실행 흐름

```
사용자 실행: /auto --debate "API 리팩토링"
         │
         ▼
┌─────────────────────────────────────┐
│ main.py (CLI)                       │
│ 1. adapter.py import 시도           │
│ 2. CORE_AVAILABLE 확인              │
└─────────────────────────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
[성공]     [실패]
    │         │
    ▼         ▼
adapter.py  debate/orchestrator.py
    │         │
    └────┬────┘
         │
         ▼
┌─────────────────────────────────────┐
│ engine.py (5-Phase)                 │
│ Phase 1: 병렬 분석 (3 AI)           │
│ Phase 2: 합의 체크 (Hash)           │
│ Phase 3: 교차 검토 (if needed)      │
│ Phase 4: 재토론 (if needed)         │
│ Phase 5: 최종 전략 결정             │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ ConsensusChecker (protocol.py)      │
│ - FULL_CONSENSUS: 종료              │
│ - PARTIAL_CONSENSUS: CROSS_REVIEW   │
│ - NO_CONSENSUS: DEBATE              │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ ContextManager (storage)            │
│ - MD 파일 저장                      │
│ - 4-Level 청킹 로드                 │
└─────────────────────────────────────┘
```

### 10.4 다음 단계 (Phase 3)

| 우선순위 | 작업 | 예상 복잡도 |
|---------|------|------------|
| P0 | 실제 AI 클라이언트 연동 (multi-ai-auth) | 높음 |
| P1 | Structural Comparison 구현 | 중간 |
| P1 | 3가지 추가 전략 구현 | 중간 |
| P2 | /auto --debate 통합 | 낮음 |
| P2 | StorageCleaner 구현 | 낮음 |

---

## 11. 참조

- PRD-0035 v3.0 (끝장토론 초안)
- [Multi-Agent Debate Framework](https://www.emergentmind.com/topics/multiagent-debate-framework)
- [Diverse Multi-Agent Debate](https://openreview.net/forum?id=t6QHYUOQL7)
