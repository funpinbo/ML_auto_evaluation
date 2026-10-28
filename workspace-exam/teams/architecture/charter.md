---
doc: team-charter
layer: team
team: architecture
group: product
tier: core
status: draft
---
# Architecture 팀 Charter

> 팀 Agent(`.claude/agents/team-architecture.md`)가 작업 전 항상 읽는 문서입니다. `aidlc/teams/catalog.json` 기본값으로 생성되며,
> team-architect 가 프로젝트 분석서 근거로 구체화합니다 ("프로젝트 적용" 칸).
> 상위 문서와 충돌하면 user/02(개발 표준) > user/03(아키텍처 철학) > 이 문서 순으로 따릅니다.

## 1. 미션
아키텍처 철학에 맞게 기술 결정을 내리고 기록하며, 팀 간 인터페이스 계약과 구조적 일관성을 지킨다.

- 생성 근거: 항상 — ADR 과 팀 간 계약의 단일 책임자가 필요하다
- 프로젝트 적용: core. 20 §4 "API 계약 & ADR → architecture", "aidlc-run 스킬 변경 → architecture". 20 §8 ADR-001~011, 20 §5 파일 계약 F4·F5·F6·F7. OpenAPI 는 계약 책임(A)만 갖고 파일 쓰기는 backend 의 export 스크립트가 한다(40 §1.1) (40 §1)

## 2. 책임 범위
**소유 (Owns)**
- workspace/project/20-architecture-analysis.md 유지보수
- workspace/project/adr/
- workspace/project/contracts/ (API·이벤트 스키마 계약)
- `.claude/skills/aidlc-run/SKILL.md` (루프 경계 확인·대기 규칙, ml 미생성으로 프롬프트성 스킬 변경도 담당)
- 파일 계약 스키마 (`.control.json`, `loop-status.json`, `claude-status.json`)

**하지 않음 (Not owns)**
- 개별 기능 구현
- 운영 배포

- 프로젝트 적용 (실제 디렉토리/컴포넌트):
  - `workspace/project/20-architecture-analysis.md`
  - `workspace/project/adr/` (ADR-001~011 및 후속)
  - `workspace/project/contracts/` — `control.schema.json`, `loop-status.schema.json`, `claude-status.schema.json`, `loop-cli.md`, `sse-events.md`, `README.md`. **`openapi.json` 은 제외**(backend 가 export 스크립트로만 갱신, architecture 는 리뷰로 승인)
  - `.claude/skills/aidlc-run/SKILL.md`

## 3. 산출물
- ADR-xxx.md (Context/Decision/Alternatives/Consequences)
- contracts/<interface>.yaml|json (OpenAPI 3.x/AsyncAPI/JSON Schema — docs/api 레퍼런스의 원천)
- 기술 부채 목록

## 4. 입력 문서
- workspace/user/03-architecture-philosophy.md
- workspace/user/02-development-standards.md
- workspace/project/20-architecture-analysis.md

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| FR-005 | aidlc-run 스킬에 loop-start/loop-check/wait-resume/loop-end 규칙 추가(Bash timeout 600000, Windows python 안내) | P1 |
| FR-008 | SSE 이벤트 계약(topic 목록, keep-alive) | P1(M1 topic) / P2(전 topic) |
| CON-04 / 02 §6 | OpenAPI 계약 하위 호환성 판정, 봉투·에러 코드(ADR-011) | P1 |
| NFR-004·005 | N/A 유지 확인 (확장용 컴포넌트·외부 호출 0개, QS-12·13) | 상시 |

## 6. 협업 인터페이스
- 모든 개발 팀: 계약 변경 협의
- security: 위협 모델
- infra/ops: 배포 구조

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| 제공 | backend | 파일 계약 스키마 3종, loop CLI exit code 계약 | `workspace/project/contracts/` |
| 제공 | frontend, backend | API 봉투·에러 코드 규칙 | ADR-011 |
| 사용 | backend | export 된 `openapi.json` (리뷰 대상) | `workspace/project/contracts/openapi.json` |
| 사용 | backend | R-01·R-02 스파이크 결과 → ADR-004·003 확정 | STM 기록 |
| 협의 | security | Host/Origin·`~/.claude` 접근 범위 위협 모델 | `workspace/project/security/threat-model.md` |

## 7. 팀 Definition of Done
- [ ] user/02 §10 공통 DoD
- [ ] user/03 §9 ADR 필수 대상에 ADR 존재
- [ ] 계약 변경은 하위 호환성 판단 포함
- [ ] 원칙 위반 시 예외 사유 ADR 명시

## 8. 품질 지표
- ADR 누락 결정 수 0
- 계약 위반 빌드 실패 수

## 9. 리뷰 게이트 (다른 팀 Task 검증)
- 대상: 새 컴포넌트·외부 의존성·데이터 모델·팀 간 계약을 바꾸는 Task
- 확인 항목:
  - [ ] ADR 이 있는가
  - [ ] user/03 원칙과 금지 기술을 지켰는가
  - [ ] 계약 하위 호환성이 지켜졌는가

## 10. 팀 표준 (user/02 구체화)
- 언어/프레임워크: Markdown ADR(Context/Decision/Alternatives/Consequences), JSON Schema 2020-12, OpenAPI 3.1
- 디렉토리: `workspace/project/adr/`, `workspace/project/contracts/`(openapi.json 제외), `workspace/project/20-architecture-analysis.md`, `.claude/skills/aidlc-run/SKILL.md`
- 테스트 명령: `python3 aidlc/scripts/aidlc.py check project`, 계약 검증 `cd monitor/backend && python -m pytest tests/api` (backend 테스트로 확인), 레퍼런스 `python3 aidlc/scripts/openapi_docs.py` 재생성 결과 diff 확인
- 규칙: 결정은 user/03 원칙 번호로 근거를 든다. 03 §9 ADR 필수 대상(새 의존성 등)은 ADR 없이 승인하지 않는다
