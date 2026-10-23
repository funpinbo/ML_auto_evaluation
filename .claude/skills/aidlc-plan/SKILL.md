---
name: aidlc-plan
description: 분석서와 팀 구성으로 Plan(Phase 로드맵)과 Task 목록을 생성해 실행 메모리 계층(Plan-Task-LTM-STM)을 시작한다.
disable-model-invocation: true
---
# /aidlc-plan — 4단계: Plan & Task 생성

## 입력
`workspace/project/` 의 00~40 문서 전체, `workspace/teams/*/charter.md`.

## 절차
1. **plan.md** (`workspace/memory/plan.md`, 템플릿 구조 유지)
   - Phase 초안은 10 §5 "권장 Phase" 를 따른다. P1 은 MVP.
   - 각 Phase 에 종료 조건(측정 가능), 포함 FR, 담당 팀을 쓴다.
   - frontmatter: `current_phase: P1`, `completed_phases: []`
2. **tasks.md** (`workspace/memory/tasks.md`)
   - Phase 별 `## P<n> — 이름` 섹션에 Task 를 쓴다. 형식:
     `- [ ] T-001 [team-id] 제목 — FR-xxx | deps: T-xxx | DoD: 완료 조건`
   - Task 크기: STM 하나(한 세션)에서 끝낼 수 있는 크기. 크면 쪼갠다.
   - **P1 앞쪽에 core 팀 기반 Task 를 반드시 넣는다** (생성된 팀만):
     | 팀 | 기반 Task |
     |----|-----------|
     | product | P1 FR 의 stories/FR-xxx.md (수용 기준 상세화) |
     | architecture | 저장소 구조·모듈 경계, 핵심 계약(contracts/) 초안 |
     | qa | test-strategy.md, 수용 기준 → test-cases 추적표 |
     | cicd | PR 게이트 CI (lint/type/test/보안 스캔) |
     | ops | slo.md (NFR → SLI/SLO), 로깅·메트릭 계측 규칙 |
     | security | threat-model.md, privacy.md |
   - 각 Phase 의 마지막 Task 로 문서화 Task 를 둔다: `- [ ] T-xxx [docs|product] Phase 문서 갱신 — /aidlc-docs | deps: (Phase 기능 Task들) | DoD: aidlc.py check docs 통과` (docs 팀이 없으면 product).
   - 기능 Task 의 deps 에는 관련 기반 Task 를 건다 (예: 기능 구현 → contracts 초안, qa test-cases).
   - 각 Task 의 `[team]` 은 40 팀 구성서에 있는 팀 id 만 사용한다.
   - 예시 Task(T-001 예시 Task)는 지운다.
   - frontmatter: `rev: 1`, `synced_ltm_rev: 0`
3. **long-term.md** — 20 의 ADR 결정과 02 의 핵심 규칙을 "결정 사항"에 시드(seed)로 넣고 출처를 `(ADR-xxx)` / `(user/02§n)` 로 단다. frontmatter 는 `rev: 0`, `last_merged_stm: 0` 그대로 둔다 (시드는 cascade 대상이 아님).
4. `python3 aidlc/scripts/aidlc.py status` 로 상태를 출력한다.

## 보고
Phase 표, Phase 별 Task 수, 팀별 Task 수(모든 팀이 최소 1개 Task 를 갖는지 확인 — 없으면 이유 명시). 다음 단계 `/aidlc-run`.
