---
doc: uat-checklist
layer: project
team: product
status: draft
source: 10-business-analysis.md §6 (MVP 정의/성공 판단 기준), stories/FR-001~005.md
---
# UAT — MVP 수용 테스트 체크리스트

> 목적: 10§6 "MVP 성공 판단 기준"을 그대로 qa 가 자동화할 수 있는 체크리스트로 옮긴다. 각 항목은 stories/FR-xxx.md 의 AC 를 근거로 한다.
> 이 문서는 수용 "기준"의 요약이며, 세부 Given/When/Then 은 각 FR story 원문이 우선한다(불일치 시 FR story 를 따른다).

## 1. End-to-End 시나리오 (10§6 MVP 성공 판단 기준 원문)
Given 2개 이상의 모델과 1개 이상의 데이터셋이 업로드된 상태,
When 사용자가 UI 에서 N:M 조합을 만들고 지표를 선택해 Run 을 클릭하면,
Then Run 레코드 1건과 그에 속한 Evaluation 레코드들이 저장되고(KPI-02 = 완료 모델 수/입력 모델 수), 결과 화면에서 모델별 지표 비교 그래프가 렌더링된다.

- [ ] UAT-01: 모델 2개(A: classification, B: regression) + 데이터셋 1개(X) 업로드 성공 (FR-002 AC-1/AC-2)
- [ ] UAT-02: Link(A,X), Link(B,X) 2건 생성 — 1개 데이터셋을 2개 모델에 N:M 연결 (FR-001 AC-3)
- [ ] UAT-03: Link(A,X)에 Accuracy 선택, Link(B,X)에 RMSE 선택 (FR-003 AC-1, AC-2)
- [ ] UAT-04: Run 버튼 1회 클릭 → run_id 1건 생성, Evaluation 2건(A/Accuracy, B/RMSE) 생성 (FR-004 AC-1/AC-2)
- [ ] UAT-05: 두 Evaluation 모두 `status=success` 인 경우 KPI-02 = 2/2 = 100%로 집계됨 (FR-004 "KPI-02 해석", D-04)
- [ ] UAT-06: 결과 화면(`GET /runs/{run_id}/results`) 접속 시 모델 A, B 의 지표 비교 그래프가 렌더링됨 (FR-005 AC-1/AC-2)

## 2. P1 범위 — Must 전체 FR 체크리스트
- [ ] FR-001: AC-1~AC-5 (stories/FR-001.md)
- [ ] FR-002: AC-1~AC-6 (stories/FR-002.md)
- [ ] FR-003: AC-1~AC-4, AC-6 (P1 범위, AC-5 는 P2) (stories/FR-003.md)
- [ ] FR-004: AC-1~AC-6 (stories/FR-004.md)
- [ ] FR-005: AC-1~AC-4 (P1 범위, AC-5 는 P2, AC-6 은 Fallback 적용 시에만) (stories/FR-005.md)

## 3. P2 범위 — 호환성 강화 & 상관관계 (일정이 허락할 때)
- [ ] FR-003 AC-5: problem_type 비호환 지표 UI 비활성화 + `status=skipped_incompatible` (stories/FR-003.md)
- [ ] FR-005 AC-5: 상관관계 그래프 (stories/FR-005.md)

## 4. 10§6 Fallback 경로 (P1 전체를 "하루" 안에 못 끝낼 경우에만 적용)
- [ ] FB-01: FR-001 + FR-002 + FR-004 만으로 업로드 → 연결 → Run 자동 평가까지 동작 (지표는 고정 기본값 1종 임시 처리)
- [ ] FB-02: 결과는 그래프 대신 raw 표로만 노출 (FR-005 AC-6)
- [ ] FB-03: 시간이 허락하면 FR-003(지표 선택 UI) → FR-005(그래프) 순서로 추가
- [ ] FB-04: Fallback 적용 여부와 무관하게 01§5 의 FR Must 지정 자체는 변경하지 않음(Task 순서/완성도만 조정 — 10§6)

## 5. 범위 경계 확인 (리뷰용)
- [ ] 본 체크리스트와 FR story 어디에도 매출/마케팅/CS/외부 파트너 관련 수용 기준이 없음 (10§2 N/A 항목 — 범위 밖 미포함 확인)
- [ ] 서버 바인딩(127.0.0.1)·인증 없음 등 NFR 은 security/architecture 팀 체크리스트에서 별도 검증(본 문서 범위 아님, D-05)
