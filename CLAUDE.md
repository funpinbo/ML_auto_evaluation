# AI-DLC 운영 규칙

이 저장소는 **AI-DLC (AI-Driven Development Life Cycle)** 로 운영된다. 모든 작업은 아래 계층과 소유권 규칙을 따른다.

## 계층 (Layer)
| Layer | 위치 | 작성자 | 역할 |
|-------|------|--------|------|
| User | `workspace/user/` | **사용자만** | 개요·기능 요구, 개발 표준, 아키텍처 철학, 데이터 정의 |
| Project | `workspace/project/` | 분석 Agent | 해석서(00), 비즈니스(10), 아키텍처(20)+ADR, 데이터 EDA(30), 팀 구성(40) |
| Team | `workspace/teams/<id>/`, `.claude/agents/team-<id>.md` | team-architect | 팀 charter, 팀 실행 Agent (카탈로그: `aidlc/teams/catalog.json`) |
| Memory | `workspace/memory/` | 오케스트레이터 + Hook | Plan > Tasks > Long-term > Short-term |

규칙 우선순위: user/02 개발 표준 > user/03 아키텍처 철학 > project 분석서 > team charter > LTM.

## 파이프라인
`/aidlc-init` → (사용자 작성) → `/aidlc-interpret` → `/aidlc-analyze` → `/aidlc-teams` → `/aidlc-plan` → `/aidlc-run [N]` 반복. 언제든 `/aidlc-status`.

## 팀 운영
- 카탈로그 17개 팀: product, design, architecture / backend, frontend, mobile, integration, dba / data, analytics, ml / qa / cicd, infra, ops / security, docs
- **core 6팀은 항상 생성:** product, architecture, qa(Test), cicd, ops, security. 나머지는 분석서 근거가 있을 때만.
- 팀 Agent 는 두 모드: **작업 모드**(자기 소유 범위만 수정) / **리뷰 모드**(수정 없이 charter §9 기준 검증, STM §7 에 PASS/FAIL).
- Task 완료 전 리뷰 게이트: 변경이 해당하는 리뷰 팀 전체가 검증한다. 코드 변경 Task 는 qa 리뷰가 항상 필수.
- 다른 팀 소유 범위가 필요하면 직접 고치지 말고 STM §5 에 `[팀id]` Task 후보로 남긴다.

## 쓰기 소유권 (반드시 지킬 것)
- `workspace/user/*` 는 Agent 가 **수정하지 않는다**. 문제는 00 해석서의 질문으로 남긴다. (사용자가 직접 요청한 경우만 예외)
- `short-term.md` — 작업 중 기록은 여기에만. 한 번에 하나의 Task.
- `long-term.md` — cascade 1/3 에서만 수정.
- `tasks.md` — `/aidlc-plan` 또는 cascade 2/3 에서만 수정. 작업 도중 체크박스를 직접 치지 않는다.
- `plan.md` — `/aidlc-plan` 또는 cascade 3/3 에서만 수정.
- `archive/` — Hook 이 관리. 수정 금지.

## 메모리 cascade (Hook: `aidlc/hooks/memory_cascade.py`)
1. STM frontmatter `status: closed` → Hook 이 아카이브 후 STM 초기화 → **LTM 갱신 요구**
2. LTM `rev` 가 tasks.md `synced_ltm_rev` 보다 큼 → **Task 갱신 요구**
3. tasks.md 의 `## P<n>` 섹션이 모두 `[x]` 인데 plan.md `completed_phases` 에 없음 → **Plan 갱신 요구**

Hook 이 `[AI-DLC cascade n/3]` 메시지를 주면 다른 일보다 먼저 그 절차를 수행한다. Stop Hook 은 미처리 cascade 가 있으면 종료를 막는다(최대 3회).
frontmatter 값(rev, last_merged_stm, synced_ltm_rev, completed_phases)은 Hook 이 판정에 쓰므로 정확히 갱신한다.

## 검증
- Hook 엔진 테스트: `python3 -m unittest discover -s aidlc/tests -v`
- 문서 Gate: `python3 aidlc/scripts/aidlc.py check [user|project]`
