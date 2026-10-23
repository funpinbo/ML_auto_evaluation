---
name: aidlc-run
description: 다음 Task 를 골라 Short-term memory 를 열고 팀 Agent 에 위임한 뒤 STM 을 닫아 Hook cascade(STM→LTM→Task→Plan)를 돌린다. 인자로 반복 횟수 지정.
disable-model-invocation: true
argument-hint: "[반복 횟수, 기본 1] [T-ID 지정 가능]"
---
# /aidlc-run — 5단계: 실행 루프

인자: `$ARGUMENTS` — 숫자면 반복 횟수(기본 1, 최대 10), `T-xxx` 면 그 Task 를 지정.

## 한 사이클
```
[0 정리] → [1 Task 선택] → [2 STM 열기] → [3 팀 Agent 실행] → [4 STM 닫기]
   → Hook: STM 보관 + LTM 갱신 요구 → [5 LTM 갱신] → Hook: Task 갱신 요구 → [6 Task 갱신]
   → (Phase 완료 시) Hook: Plan 갱신 요구 → [7 Plan 갱신] → 다음 사이클
```

### 0. 정리
`python3 aidlc/scripts/aidlc.py status` 실행. "미처리 cascade" 가 있으면 그것부터 처리한다(5~7단계 규칙).
STM 이 `active` 면 새로 열지 말고 그 Task 를 이어서 3단계부터 진행한다.

### 1. Task 선택
`workspace/memory/tasks.md` 의 `current_phase`(plan.md) 섹션에서 deps 가 모두 `[x]` 인 첫 번째 `[ ]` Task. Blocked 섹션의 Task 는 고르지 않는다.
선택 가능한 Task 가 없으면 이유(의존성/blocked)를 보고하고 종료한다.

### 2. STM 열기
`workspace/memory/short-term.md` 를 작성한다:
- frontmatter: `status: active`, `task: T-xxx`, `team: <team-id>`, `outcome: none`, `opened_at: <ISO 시각>`
- §1 목표/DoD (tasks.md 그대로 + user/02 §10 공통 DoD)
- §2 로드한 컨텍스트: 관련 FR(00 해석서), 팀 charter, LTM 의 관련 결정/패턴/팀 지식을 **요약해서** 적는다.

### 3. 팀 Agent 실행
`team-<team-id>` 서브에이전트에 위임: "workspace/memory/short-term.md 의 Task 를 수행하라."
팀 Agent 가 없으면 charter 를 읽고 직접 수행하되 같은 규칙(STM 에 기록, tasks/ltm/plan 수정 금지)을 따른다.
반환 후 STM §3~§6 이 채워졌는지, `outcome` 이 설정되었는지 확인한다.

### 4. STM 닫기
STM frontmatter 를 `status: closed` 로 바꾼다. → Hook 이 자동으로 `archive/STM-xxxx_<task>.md` 로 보관하고 short-term.md 를 초기화한 뒤 LTM 갱신을 요구한다.

### 5. LTM 갱신 (Hook cascade 1/3)
Hook 메시지의 절차대로 `long-term.md` 를 갱신한다 (`memory-curator` 위임 가능). `rev` +1, `last_merged_stm` 설정.

### 6. Task 갱신 (Hook cascade 2/3)
Hook 메시지의 절차대로 `tasks.md` 를 갱신한다 (`memory-curator` 위임 가능). `rev` +1, `synced_ltm_rev` 설정.

### 7. Plan 갱신 (Hook cascade 3/3, Phase 완료 시에만)
Hook 메시지의 절차대로 `plan.md` 를 갱신한다. **이 단계는 직접 수행**하고, 다음 Phase 범위 조정이 크면 사용자에게 확인을 받는다.

## 반복 & 보고
반복 횟수만큼 1~7 을 반복한다. outcome 이 blocked 이면 반복을 멈추고 blocker 를 보고한다.
끝나면 사이클별 `T-ID / outcome / LTM 추가 항목 수 / 새 Task 수` 표와 `aidlc.py status` 결과를 보여준다.
