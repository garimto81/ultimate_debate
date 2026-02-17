# Plan: GPT/Gemini 토론 결과물 품질 개선

## 배경
실제 토론 실행 시 결과물 품질이 형편없는 5가지 근본 원인 발견:
1. SHA-256 해시 기반 합의 판정 → 의미 동일해도 항상 불일치
2. GPT 참여 실패 시 조용히 무시
3. Claude 리뷰가 플레이스홀더 그대로 출력
4. 프롬프트가 너무 일반적
5. updated_position dict 처리 버그

## 구현 범위

### Fix 1: 합의 판정을 Semantic Similarity로 전환
- **파일**: `src/ultimate_debate/consensus/protocol.py`
- **변경**: SHA-256 해시 비교 → SemanticComparator (TF-IDF cosine similarity) 사용
- **상세**:
  - `SemanticComparator`는 이미 `comparison/semantic.py`에 구현됨
  - `check_consensus()`에서 해시 대신 cosine similarity로 conclusion 클러스터링
  - 동일 클러스터 내 결론들을 agreed_items로 처리
  - threshold 0.6 (해시의 1.0 대신) — 의미적으로 유사하면 합의로 인정

### Fix 2: AI 클라이언트 실패 가시성 향상
- **파일**: `src/ultimate_debate/engine.py`
- **변경**: `run_parallel_analysis()`에서 실패한 클라이언트 정보를 결과에 포함
- **상세**:
  - `self.failed_clients: dict[str, str]` 속성 추가
  - 실패 시 logger.warning 외에 failed_clients에 기록
  - `get_status()`에서 failed_clients 노출

### Fix 3: Claude 플레이스홀더 리뷰 방지
- **파일**: `src/ultimate_debate/engine.py`
- **변경**: `requires_input=True`인 플레이스홀더 리뷰를 합의 체크에서 제외
- **상세**:
  - `run_cross_review()`에서 `requires_input` 플래그가 있는 리뷰 필터링
  - `check_cross_review_consensus()`에 전달 시 플레이스홀더 제외

### Fix 4: 프롬프트 품질 개선
- **파일**: `src/ultimate_debate/clients/openai_client.py`, `gemini_client.py`
- **변경**:
  - system prompt에 역할과 맥락 강화
  - peer_analysis를 dict dump 대신 정리된 텍스트로 전달
  - JSON 응답만 요구하되, 순수 JSON만 출력하도록 명확히
  - temperature 0.7 → 0.3 (일관성 향상, 합의 수렴 촉진)

### Fix 5: updated_position dict 처리 버그 수정
- **파일**: `src/ultimate_debate/engine.py`
- **변경**: `run()` 메서드의 debate 결과 처리
- **상세**:
  - `updated_position`이 dict이면 `["conclusion"]` 추출
  - str이면 그대로 사용

## 영향 파일
1. `src/ultimate_debate/consensus/protocol.py` (핵심)
2. `src/ultimate_debate/engine.py` (핵심)
3. `src/ultimate_debate/clients/openai_client.py`
4. `src/ultimate_debate/clients/gemini_client.py`
5. `tests/test_engine.py` (테스트 업데이트)

## 위험 요소
- SemanticComparator의 sklearn 의존성 (이미 코드베이스에 존재)
- 기존 테스트가 해시 기반 합의에 의존할 수 있음 → 테스트도 함께 수정
- temperature 변경이 기존 동작에 영향 → 0.3으로 충분히 보수적
