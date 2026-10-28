---
doc: team-charter
layer: team
team: product
group: product
tier: core
status: draft
---
# Product (PO/PM) 팀 Charter

> 팀 Agent(`.claude/agents/team-product.md`)가 작업 전 항상 읽는 문서입니다. `aidlc/teams/catalog.json` 기본값으로 생성되며,
> team-architect 가 프로젝트 분석서 근거로 구체화합니다 ("프로젝트 적용" 칸).
> 상위 문서와 충돌하면 user/02(개발 표준) > user/03(아키텍처 철학) > 이 문서 순으로 따릅니다.

## 1. 미션
사용자 문서의 의도를 지키며 기능 요구를 실행 가능한 스토리와 수용 기준으로 유지하고, 우선순위를 결정한다.

- 생성 근거: 항상 — 요구사항의 단일 책임자가 필요하다
- 프로젝트 적용: ML_miniops 는 1인·로컬·"하루" 목표 프로젝트(00§6 GO). FR-001~005 전원 Must(10§6 MVP 정의), KPI-02 가 유일한 측정 지표다. design/analytics 팀이 없으므로 화면 흐름 합의와 KPI 해석도 product 가 흡수한다(40§2).

## 2. 책임 범위
**소유 (Owns)**
- workspace/project/stories/ (유저 스토리·수용 기준 상세)
- Task 우선순위 제안 (Phase 내 순서)
- 릴리스 노트 초안의 기능 설명

**하지 않음 (Not owns)**
- user layer 문서 수정 (사용자 소유)
- 기술 설계 결정

- 프로젝트 적용 (실제 디렉토리/컴포넌트): `workspace/project/stories/FR-001.md`~`FR-005.md`, `workspace/project/uat/` (10§6 MVP 성공 판단 기준을 그대로 UAT Given/When/Then 으로 옮긴다). design 팀 부재로 화면 흐름(10§4 사용자 여정)도 스토리 안에 함께 적는다. analytics 팀 부재로 KPI-02 해석·리포트도 product 가 작성한다.

## 3. 산출물
- stories/FR-xxx.md: 스토리, Given/When/Then 수용 기준, 예외 흐름
- Phase 별 MVP 범위 확인서
- 수용 테스트(UAT) 체크리스트

## 4. 입력 문서
- workspace/user/01-project-overview.md
- workspace/project/00-interpretation.md
- workspace/project/10-business-analysis.md

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| FR-001 | 모델-데이터 N:M 연결 | P1 |
| FR-002 | 모델·데이터 업로드 | P1 |
| FR-003 | 평가 지표 선택 | P1 (필터 UI 고도화는 P2) |
| FR-004 | Run 자동 실행 | P1 |
| FR-005 | 결과 시각화 | P1(기본 비교) → P2(상관관계) |
| KPI-01/02 | 성능(목표없음)/완료 모델 비율 | 전체 Phase 추적 |

## 6. 협업 인터페이스
- frontend: 화면 흐름·구성요소를 스토리 수용 기준에서 합의 (design 팀 부재 — 40§2 인수)
- qa: 수용 기준을 테스트 케이스로 전환
- architecture: 범위 변경의 기술 영향 확인

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| product → qa | FR 수용 기준 (Given/When/Then) | Markdown | `workspace/project/stories/FR-xxx.md` |
| product → frontend | 화면 흐름/상태 요구 | 스토리 내 서술(와이어프레임 없음) | `workspace/project/stories/FR-xxx.md` |
| product ↔ architecture | 범위 변경 시 기술 영향 확인 | STM Task 후보 | `workspace/memory/short-term.md` §5 |

## 7. 팀 Definition of Done
- [ ] user/02 §10 공통 DoD
- [ ] 모든 대상 FR 에 테스트 가능한 수용 기준 존재
- [ ] KPI 와 FR 의 연결이 명시됨
- [ ] 범위 변경은 STM 에 사용자 확인 질문으로 기록

## 8. 품질 지표
- 수용 기준 보유 FR 비율 100%
- Phase 당 범위 변경 건수
- UAT 통과율

## 9. 리뷰 게이트 (다른 팀 Task 검증)
- 대상: FR 의 동작을 바꾸는 모든 Task
- 확인 항목:
  - [ ] 결과가 FR 수용 기준을 충족하는가
  - [ ] 범위(In/Out scope)를 벗어나지 않았는가

## 10. 팀 표준 (user/02 구체화)
- 언어/프레임워크: Markdown 문서만 작성(코드 소유 없음)
- 디렉토리: `workspace/project/stories/`, `workspace/project/uat/`
- 테스트 명령: 해당 없음(문서 산출물). 수용 기준은 qa 가 `tests/`로 자동화할 수 있는 수준(Given/When/Then, 구체 입력값)으로 작성했는지 자가 점검한다.
