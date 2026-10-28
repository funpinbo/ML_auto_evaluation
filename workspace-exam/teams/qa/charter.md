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
- 프로젝트 적용: core. 20 §4 "테스트 스위트 & fixture → qa", 02 §5 필수 테스트(일시정지/재개 시나리오, 깨진 파일·빈 workspace), 30 §6 "fixture 생성기·성능 테스트는 qa". 단위·API 테스트는 user/02 §10 DoD 에 따라 개발 팀이 쓴다(40 §1.1) (40 §1)

## 2. 책임 범위
**소유 (Owns)**
- 테스트 전략서 (test-strategy.md: 테스트 피라미드, 범위, 환경)
- E2E·회귀·통합 테스트 스위트 (예: tests/e2e)
- 성능/부하 테스트 시나리오
- 테스트 데이터·픽스처 관리 규칙
- 결함(버그) 리포트
- (data 인수) 가짜 JSONL 생성기(30 EDA `bench_synthetic.py` 이식), 본문 표식 문자열 fixture

**하지 않음 (Not owns)**
- 기능 코드 수정 (결함은 담당 팀 Task 후보로 남긴다)
- 단위 테스트 작성 책임 (개발 팀)

- 프로젝트 적용 (실제 디렉토리/컴포넌트):
  - `monitor/backend/tests/conftest.py`, `tests/fixtures/`(가짜 workspace 빈/일부/전체/깨짐/closed STM, 30일 JSONL, 스냅샷), `tests/scenarios/`(일시정지/재개, 깨진 입력, 해시 불변, 본문 비노출, Hook 규칙 대조), `tests/perf/`(Task 100 + 30일)
  - `monitor/frontend/tests/` (fixture API 응답, 통합 spec)
  - `workspace/project/qa/` — `test-strategy.md`, `test-cases/FR-xxx.md`, Phase 품질 리포트
  - **하지 않음:** `monitor/backend/tests/unit/`, `tests/api/`(backend), `monitor/frontend/src/**/*.spec.ts`(frontend)

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
| NFR-001 | 첫 화면 ≤ 2초, 변경 반영 ≤ 5초 성능 테스트(QS-01·02) | P1 |
| NFR-002 | 깨진 파일·빈 workspace·스냅샷 없음에서 HTTP 500 0건(QS-03·04) | P1 |
| FR-005 | 일시정지/재개/2시간 초과/heartbeat 만료 시나리오(QS-11) | P1 |
| CON-03 | 조회 API 전후 workspace 해시 불변(closed STM fixture 포함, QS-07) | P1 |
| NFR-003 | fixture 본문 표식 문자열이 응답·로그에 0건(QS-06) | P1 |
| FR-003 | `aidlc.py status` 와 같은 결론인지 Hook 규칙 대조 | P1 |
| FR-006~010 | P2 기능 수용 기준 테스트 케이스 | P2 |

## 6. 협업 인터페이스
- product: 수용 기준
- 모든 개발 팀: 결함 수정·테스트 ID
- cicd: 테스트 게이트 파이프라인
- ml: AI 응답 회귀 테스트

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| 사용 | product | 수용 기준 | `workspace/project/stories/` |
| 제공 | backend, frontend | fixture 생성기·본문 표식 문자열 | `monitor/backend/tests/fixtures/`, `monitor/frontend/tests/fixtures/` |
| 제공 | cicd | 테스트 명령·커버리지 기준(≥ 70%) | `workspace/project/qa/test-strategy.md` |
| 사용 | security | 허용 필드 체크리스트(본문 비노출 테스트 기준) | `workspace/project/security/privacy.md` |

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
- 언어/프레임워크: pytest + FastAPI TestClient + pytest-cov, vitest + @vue/test-utils + jsdom
- 디렉토리: 위 "프로젝트 적용" 목록
- 테스트 명령: `cd monitor/backend && python -m pytest` (커버리지 `python -m pytest --cov=app --cov-report=term-missing`, 라인 ≥ 70%), `cd monitor/frontend && npm test`
- 규칙: 실제 `~/.claude` 를 테스트에 쓰지 않는다(02 §5). 경로는 `AIDLC_ROOT`·`CLAUDE_HOME` 환경 변수로 fixture 경로 주입. fixture 생성은 결정적(seed 고정)
