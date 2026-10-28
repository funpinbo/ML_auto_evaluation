---
current_phase: P1
completed_phases: []
---
# Plan

> **계층 최상위.** Phase 단위의 목표·범위·종료 조건을 정의한다.
> 갱신 시점: (1) `/aidlc-plan` 최초 생성 (2) Hook cascade 3/3 — Phase 의 모든 Task 완료 시.
> Task 상세는 `tasks.md`, 학습 내용은 `long-term.md` 에 둔다. 여기에는 중복하지 않는다.

## 1. 전체 목표
- 제품 목표: 1인 사용자가 로컬 FastAPI 도구에서 PyTorch/scikit-learn 모델과 CSV 데이터를 업로드해 다대다로 연결하고, Accuracy/F1/RMSE 중 지표를 선택해 Run 1클릭으로 자동 평가한 뒤 pandas 기반 그래프로 결과를 비교한다 (00-interpretation.md §1).
- 성공 지표: KPI-02 (1회 Run 에서 완료된 모델 수 / 입력된 모델 수 = 100% 목표, ADR-003 산식: 분자 = status='success' 레코드가 있는 모델 수)

## 2. Phase 로드맵

| Phase | 이름 | 목표 | 포함 FR | 담당 팀 | 종료 조건 (Exit Criteria) | 상태 |
|-------|------|------|---------|---------|---------------------------|------|
| P1 | MVP 핵심 파이프라인 | 업로드→연결→지표선택(기본)→Run 자동평가→결과 기본 그래프까지 끊김없이 동작 | FR-001, FR-002, FR-003(기본), FR-004, FR-005(기본 비교 그래프) | product, architecture, dba, qa, cicd, ops, security, backend, frontend | 10-business-analysis.md §6 MVP 성공 판단 기준 충족: 모델 2개+데이터셋 1개 업로드 → N:M 연결 → 지표 선택 → Run 클릭 → Run/Evaluation 레코드 저장 + 모델별 지표 비교 그래프 렌더링 (E2E, 더미 fixture 기준) | 진행중 |
| P2 | 호환성 강화 & 시각화 고도화 | 지표-문제유형 호환성 사전 필터링(00§3.2#10) 활성화, 결과 화면에 상관관계 그래프 추가 | FR-003(호환성 필터 고도화), FR-005(상관관계 그래프) | backend, frontend, qa, product | 비호환 지표(예: 회귀 모델+accuracy) 선택 시 UI 에서 사전 차단(비활성화)되고 `status='skipped_incompatible'` 로 기록됨, 결과 화면에 상관관계 그래프 렌더링, P1 회귀 없음(qa 확인) | 대기 |

## 3. 마일스톤 & 의존성
- P2 는 P1 전체(핵심 파이프라인 E2E 동작)가 끝난 뒤에만 시작한다 — Compatibility Filter/상관관계 그래프는 20-architecture-analysis.md §0·§9(R3) 설계상 Evaluation Engine/기본 그래프와 분리된 모듈이라 P1 완료 전에도 병행 설계는 가능하지만, 통합은 P1 완료 후.
- 외부 의존성 없음 (로컬 단일 프로세스, 클라우드/외부 서비스 미사용 — 03§6).
- 일정 리스크(00§3.2#9, Q9): "하루"(2026-10-27) 안에 P1 까지만 완료해도 10-business-analysis.md §6 의 Fallback(FR-001+002+004 핵심 파이프라인, 지표는 고정 기본값, 결과는 raw 표)을 최소 성공으로 인정한다.

## 4. 리스크 & 대응
| ID | 리스크 | 영향 | 대응 | 관련 Phase |
|----|--------|------|------|-----------|
| RISK-01 | "하루" 일정 내 P1 전체를 못 끝낼 수 있음 (00§3.2#9, Q9) | P2 착수 지연 또는 P1 범위 축소 | FR-001/002/004(핵심 파이프라인)를 P1 내에서도 최우선 순서로 두고, FR-003/005 는 최소 기능(지표 선택 가능, 기본 그래프 1종)까지만 — 10§6 Fallback 적용 | P1 |
| RISK-02 | 모델 `predict(X)->y` 계약(ADR-002) 미준수 스크립트 업로드 | FR-002/004 실패 | 업로드 시 import+hasattr 검증으로 fail fast (QS-6, T-010) | P1 |
| RISK-03 | 지표-문제유형 불일치를 사전 차단하지 않고 P1에서 넘어감 | 회귀 모델에 accuracy 선택 등으로 결과 신뢰도 저하 | P1에서는 예외를 `status='error'` 로 기록(사후 감지), P2에서 사전 차단(Compatibility Filter, ADR-003)으로 보강 | P1→P2 |

## 5. 진행 로그 (Phase 회고)
<!-- cascade 3/3 에서 Phase 완료 시 append: 날짜 / Phase / 목표 대비 결과 / LTM 핵심 교훈 / 다음 Phase 조정 사항 -->
