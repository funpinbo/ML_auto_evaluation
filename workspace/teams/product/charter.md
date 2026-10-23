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
- 프로젝트 적용: core. 20 §4 "수용 기준 & KPI 사용 테스트 → product", 10 §6 MVP 성공 기준(KPI-01 질문 3개, KPI-02 설치 리허설), 10 §7 A10·A11 기준 확인. 40 §2 에서 analytics(KPI 측정)·docs(사용자 가이드 내용) 책임을 인수 (40 §1)

## 2. 책임 범위
**소유 (Owns)**
- workspace/project/stories/ (유저 스토리·수용 기준 상세)
- Task 우선순위 제안 (Phase 내 순서)
- 릴리스 노트 초안의 기능 설명
- (analytics 인수) KPI-01 사용 테스트·KPI-02 설치 리허설 기록
- (docs 인수) 사용자 가이드 내용, `/aidlc-docs` 산출물 내용 검토

**하지 않음 (Not owns)**
- user layer 문서 수정 (사용자 소유)
- 기술 설계 결정

- 프로젝트 적용 (실제 디렉토리/컴포넌트):
  - `workspace/project/stories/` — `FR-001.md`~`FR-010.md`, `SCOPE-01.md`
  - `workspace/project/uat/` — UAT 체크리스트, KPI-01 스톱워치 기록, KPI-02 OS 별 설치 리허설 기록
  - `monitor/README.md` — 설치·실행·사용 안내 (cicd 와 명령 일치 확인)

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
| FR-001~010, SCOPE-01 | 전 FR 의 Given/When/Then 수용 기준·예외 흐름 소유 | P1(FR-001~005, SCOPE-01) / P2(FR-006~010) |
| KPI-01 | 고정 질문 3개(#A12) 5초 이내 응답 사용 테스트 | P1 말 |
| KPI-02 | 깨끗한 PC 설치 리허설(Windows 1 + macOS/Linux 1), 실행 동작 1회·5분 이내 | P1 말 |
| A11 / A10 | FR-001 단계 0~6 판정 기준, FR-010 cascade 막힘 기준을 PO 화면 리뷰로 확인 | P1 말 / P2 말 |

## 6. 협업 인터페이스
- design: 사용자 흐름과 화면 요구 합의
- qa: 수용 기준을 테스트 케이스로 전환
- architecture: 범위 변경의 기술 영향 확인

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| 제공 | qa | FR 별 수용 기준 → 테스트 케이스 | `workspace/project/stories/` |
| 제공 | frontend | 화면 흐름·상태 문구("한도 정보 없음" 등) 요구 | `workspace/project/stories/` |
| 제공 | backend | A11 단계 판정·A10 cascade 막힘 기준 | `workspace/project/stories/FR-001.md`, `FR-010.md` |
| 사용 | architecture | 범위 변경의 기술 영향 판단 | `workspace/project/adr/` |
| 사용 | cicd | 런처 실행 명령 (README 와 일치) | `run.py`, `workspace/project/release/release.md` |

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
- 언어/프레임워크: Markdown (한국어). 수용 기준은 Given/When/Then, qa 가 pytest/vitest 로 그대로 옮길 수 있는 수치·문구로 쓴다
- 디렉토리: `workspace/project/stories/`, `workspace/project/uat/`, `monitor/README.md`
- 테스트 명령: `python3 aidlc/scripts/aidlc.py check project` (문서 Gate). UAT 는 `run.sh`/`run.bat` 실행 후 수동 체크리스트
- 규칙: `workspace/user/*` 는 수정하지 않는다. 01 의 범위를 넘는 요구는 00 해석서 질문 후보로 STM 에 남긴다
