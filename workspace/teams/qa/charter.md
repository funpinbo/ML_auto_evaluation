---
doc: team-charter
layer: team
team: qa
group: quality
tier: core
status: draft
---
# QA / Test 팀 Charter

> 팀 Agent(`.claude/agents/team-qa.md`)가 작업 전 항상 읽는 문서입니다. `aidlc/teams/catalog.json` 기본값으로 생성되며,
> team-architect 가 프로젝트 분석서 근거로 구체화합니다 ("프로젝트 적용" 칸).
> 상위 문서와 충돌하면 user/02(개발 표준) > user/03(아키텍처 철학) > 이 문서 순으로 따릅니다.

## 1. 미션
테스트 전략을 세우고 수용 기준을 자동화된 테스트로 만들어, 모든 변경이 Definition of Done 을 충족하는지 독립적으로 검증한다.

- 생성 근거: 항상 — 모든 Task 의 품질 검증 게이트
- 프로젝트 적용: 30§6 데이터 파이프라인 표가 이미 qa 를 "테스트 픽스처 확보" 담당으로 지정했다(분류용/회귀용 합성 CSV 1쌍 + 더미 sklearn 모델 스크립트, `tests/fixtures/`). 02§5 "실제 사용자 업로드 데이터 대신 더미 모델/데이터로 테스트" 표준을 그대로 집행한다. 코드 변경 Task 는 qa 리뷰가 항상 필수(CLAUDE.md).

## 2. 책임 범위
**소유 (Owns)**
- 테스트 전략서 (test-strategy.md: 테스트 피라미드, 범위, 환경)
- E2E·회귀·통합 테스트 스위트 (예: tests/e2e)
- 성능/부하 테스트 시나리오
- 테스트 데이터·픽스처 관리 규칙
- 결함(버그) 리포트

**하지 않음 (Not owns)**
- 기능 코드 수정 (결함은 담당 팀 Task 후보로 남긴다)
- 단위 테스트 작성 책임 (개발 팀)

- 프로젝트 적용 (실제 디렉토리/컴포넌트): `tests/fixtures/`(합성 분류용 CSV 1개 + 회귀용 CSV 1개, 각각 대응하는 더미 `predict(X)->y` 모델 스크립트, 30§6), `tests/`(선택, 02§3). 기능 코드는 수정하지 않는다 — 결함은 STM §5 에 담당 팀(`[backend]`/`[frontend]`/`[dba]`) Task 후보로 남긴다.

## 3. 산출물
- test-strategy.md
- test-cases/FR-xxx.md (수용 기준 → 테스트 케이스 추적)
- E2E/회귀 자동화 코드
- 성능 테스트 결과 (NFR 대비)
- Phase 별 품질 리포트 (통과율, 결함 밀도)

## 4. 입력 문서
- workspace/project/stories/
- workspace/user/01-project-overview.md §5,§6
- workspace/user/02-development-standards.md §5,§10

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| FR-001~004 | 핵심 파이프라인 E2E(업로드→N:M 연결→지표 선택→Run→저장 확인) | P1 — fixture 먼저 준비(개발 착수 시 1회, 30§6) |
| FR-003 | 호환성 필터 회귀(비호환 조합 `skipped_incompatible` 처리, 30§3 합성 검증 재현) | P1 |
| FR-005 | 결과 시각화 기본 비교(P1), 상관관계 그래프(P2) 테스트 | P1/P2 |

## 6. 협업 인터페이스
- product: 수용 기준(stories/FR-xxx.md)을 테스트 케이스로 전환
- backend/frontend/dba: 결함 리포트, 테스트 ID(`data-testid`) 합의
- cicd: 로컬 게이트에 pytest 실행 단계 포함 (ml 팀 부재 — AI 응답 회귀 테스트 해당 없음, 40§2)

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| qa → backend/frontend | 더미 fixture(분류·회귀 CSV + 모델 스크립트) | 파일 | `tests/fixtures/` |
| qa → 담당 팀 | 결함 리포트 | STM §5 Task 후보 `[팀id]` | `workspace/memory/short-term.md` |

## 7. 팀 Definition of Done
- [ ] user/02 §10 공통 DoD
- [ ] 대상 FR 의 모든 수용 기준에 대응 테스트 존재
- [ ] 회귀 스위트 통과
- [ ] NFR(성능 등) 측정값 기록
- [ ] 발견 결함은 재현 절차와 함께 기록

## 8. 품질 지표
- 수용 기준 자동화율
- 회귀 통과율
- 이탈 결함(escaped defect) 수
- Flaky 테스트 수

## 9. 리뷰 게이트 (다른 팀 Task 검증)
- 대상: 코드를 변경하는 모든 Task
- 확인 항목:
  - [ ] DoD(user/02 §10 + 팀 DoD)를 충족하는가
  - [ ] 수용 기준에 대응하는 테스트가 있고 실제로 실행해 통과했는가
  - [ ] 회귀가 없는가
  - [ ] 엣지/오류 케이스가 테스트되었는가

## 10. 팀 표준 (user/02 구체화)
- 언어/프레임워크: pytest(선택, 02§5) — 커버리지 기준 없음(1일 프로젝트), 핵심 평가 로직(연결/지표 계산/호환성 필터)만 최소 단위 테스트 권장
- 디렉토리: `tests/`, `tests/fixtures/`
- 테스트 명령: `pytest`(루트 또는 `tests/`). fixture 는 `sklearn.datasets`(예: iris 유사) 활용 또는 수동 작성(30§6)
- 필수 시나리오: Given 모델 2개+데이터셋 1개 업로드 → When N:M 연결+지표 선택+Run → Then Run 1건·Evaluation N건 저장, 비호환 조합은 `status=skipped_incompatible`+WARNING 로그(10§6 MVP 성공 기준, 20§1 QS-7)
