---
name: aidlc-analyze
description: 비즈니스 모델 분석, 아키텍처 분석, 데이터(EDA) 분석을 각 분석 Agent 로 수행해 Project Layer 분석서 3종을 만든다.
disable-model-invocation: true
argument-hint: "[business|architecture|data] (생략 시 전체)"
---
# /aidlc-analyze — 2단계: 분석

## 전제 확인
- `workspace/project/00-interpretation.md` 가 있고 §6 판단이 GO 인지 확인한다. 아니면 `/aidlc-interpret` 를 먼저 하라고 안내하고 멈춘다.

## 실행 순서
인자 `$ARGUMENTS` 가 있으면 해당 분석만, 없으면 아래 전체를 실행한다.

1. **병렬 1차:** 아래 두 서브에이전트를 **동시에** 호출한다.
   - `business-analyst` → `workspace/project/10-business-analysis.md`
   - `data-analyst` → `workspace/project/30-data-analysis.md`
2. **2차:** `architecture-analyst` 호출 → `workspace/project/20-architecture-analysis.md` + ADR.
   프롬프트에 1차 결과 요약(MVP FR, 비즈니스 리스크, 데이터 파이프라인 제약)을 함께 전달한다.
3. **교차 검증 (직접 수행):**
   - 10 §5 의 모든 FR 이 20 §4 컴포넌트 중 하나에 매핑되는가
   - 30 §6 파이프라인 단계가 20 의 컴포넌트/저장소와 일치하는가
   - 불일치가 있으면 해당 Agent 를 다시 호출해 수정한다 (최대 2회)
4. `python3 aidlc/scripts/aidlc.py check project` 로 템플릿 플레이스홀더 미작성 여부를 확인한다 (40 팀 구성서는 아직 없으므로 MISSING 은 정상).

## 보고
분석서별 핵심 3줄, 교차 검증 결과, 다음 단계 `/aidlc-teams` 안내.
