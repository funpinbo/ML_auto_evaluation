---
name: aidlc-run
description: 다음 Task 를 골라 Short-term memory 를 열고 팀 Agent 에 위임한 뒤 STM 을 닫아 Hook cascade(STM→LTM→Task→Plan)를 돌린다. 인자로 반복 횟수 지정.
disable-model-invocation: true
argument-hint: "[반복 횟수, 기본 1] [T-ID 지정 가능]"
---
# /aidlc-run — 5단계: 실행 루프

인자: `$ARGUMENTS` — 숫자면 반복 횟수(기본 1, 최대 10), `T-xxx` 면 그 Task 를 지정.

루프 전체는 **루프 경계 규칙**(아래 "## 루프 경계")으로 감싼다: 시작 `loop-start N` → 사이클(0~7) → 사이클 사이 `loop-check` → 일시정지면 `wait-resume` 반복 → 끝 `loop-end`.
대시보드의 일시정지/재개는 이 경계에서만 적용된다(Task·cascade 도중에는 멈추지 않는다).

## 한 사이클
```
[0 정리] → [1 Task 선택] → [2 STM 열기] → [3 팀 Agent 실행] → [3.5 리뷰 게이트] → [4 STM 닫기]
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
`team-<team-id>` 서브에이전트에 위임: "작업 모드 — workspace/memory/short-term.md 의 Task 를 수행하라."
팀 Agent 가 없으면 charter 를 읽고 직접 수행하되 같은 규칙(STM 에 기록, tasks/ltm/plan 수정 금지)을 따른다.
반환 후 STM §3~§6 이 채워졌는지, `outcome` 이 설정되었는지 확인한다.

### 3.5 리뷰 게이트 (다른 팀의 독립 검증)
`workspace/project/40-team-composition.md` §5 리뷰 게이트 표(없으면 각 `workspace/teams/*/charter.md` §9)를 보고,
이번 Task 의 변경이 "적용 대상"에 해당하는 **모든 리뷰 팀**을 고른다. 작업한 팀 자신은 제외한다.
- `qa` 는 코드를 바꾼 모든 Task 에 항상 포함된다.
- 해당 팀들을 리뷰 모드로 **동시에** 호출한다: "리뷰 모드 — workspace/memory/short-term.md 의 Task 결과를 charter §9 기준으로 검증하라."
- STM §7 리뷰 기록에 FAIL 이 있으면:
  1. 작업 팀을 다시 작업 모드로 호출해 FAIL 조치를 반영한다 (최대 2회 반복, 매번 FAIL 낸 팀만 재리뷰).
  2. 그래도 FAIL 이면 `outcome: partial` 로 바꾸고 남은 조치를 STM §5 Task 후보로 남긴다.
- 리뷰 결과 요약(팀별 PASS/FAIL)을 STM §6 검증 결과에 적는다.

### 4. STM 닫기
STM frontmatter 를 `status: closed` 로 바꾼다. → Hook 이 자동으로 `archive/STM-xxxx_<task>.md` 로 보관하고 short-term.md 를 초기화한 뒤 LTM 갱신을 요구한다.

### 5. LTM 갱신 (Hook cascade 1/3)
Hook 메시지의 절차대로 `long-term.md` 를 갱신한다 (`memory-curator` 위임 가능). `rev` +1, `last_merged_stm` 설정.

### 6. Task 갱신 (Hook cascade 2/3)
Hook 메시지의 절차대로 `tasks.md` 를 갱신한다 (`memory-curator` 위임 가능). `rev` +1, `synced_ltm_rev` 설정.

### 7. Plan 갱신 (Hook cascade 3/3, Phase 완료 시에만)
Hook 메시지의 절차대로 `plan.md` 를 갱신한다. **이 단계는 직접 수행**하고, 다음 Phase 범위 조정이 크면 사용자에게 확인을 받는다.

## 루프 경계 (FR-005 · ADR-004 · `workspace/project/contracts/loop-cli.md`)
대시보드 일시정지/재개를 위한 규칙. 계약 문서가 기준이고, 아래는 실행 절차다.

**Python 명령**: 아래 `python3` 는 먼저 `python3 --version` 이 실제로 동작하는지 확인한다. Windows 에서 안 되면 `python`, 그것도 안 되면 `py -3` 로 같은 인자를 넘긴다(CLAUDE.md, R-09). 정한 명령을 루프 끝까지 같게 쓴다.

**호출 방식**: Bash 도구로 저장소 루트에서 `python3 aidlc/scripts/aidlc.py <sub> ...; echo "exit=$?"` 형태로 실행하고 **exit code 로만 분기**한다. stdout 의 `AIDLC-LOOP ...` 한 줄은 사용자 보고용이며 판단에 쓰지 않는다. `run_in_background` 는 쓰지 않는다.

**금지**: `.control.json` 을 만들거나 고치거나 지우지 않는다(작성자 = 대시보드만). `loop-status.json` 도 직접 쓰지 않는다(작성자 = CLI 만, R-10). 대기 중에는 다른 작업·파일 수정을 하지 않는다.

### 흐름
```
loop-start <N>                         # 맨 처음 1회. N = 반복 횟수 (T-xxx 지정이면 1)
for i in 1..N:
    사이클 0~7 수행 (위 "한 사이클", 그대로)
    1단계에서 선택 가능한 Task 없음 → loop-end no_task --done <i-1>, 보고 후 종료
    outcome == blocked             → loop-end blocked --done <i>,  blocker 보고 후 종료
    i < N 이면: loop-check <i>      # 7단계(cascade) 끝난 뒤, 마지막 사이클 뒤에는 호출하지 않음
loop-end done --done <N>               # 모든 반복 완료
```

### exit code 분기
| 호출 | 0 | 10 | 20 | 2 | 1 | 64 |
|------|---|----|----|---|---|----|
| `loop-start <N>` | 진행 | - | - | 경고 한 줄 후 진행 | 경고 한 줄 후 진행 | 스킬 버그 — 루프를 시작하지 말고 보고 |
| `loop-check <i>` | 다음 사이클 (`NO_LOOP` 도 0 — 그대로 진행) | **대기 진입** (아래) | - | 경고 한 줄 후 다음 사이클 | 경고 한 줄 후 다음 사이클 | 버그 — `loop-end blocked --done <i>` 후 중단·보고 |
| `wait-resume` | 재개 → 다음 사이클 | 같은 호출 즉시 반복(설명 없이) | 상한 초과 종료 (아래) | 경고 한 줄 후 다음 사이클 | 경고 한 줄 후 다음 사이클 | 버그 — `loop-end blocked --done <i>` 후 중단·보고 |
| `loop-end ...` | 끝 | - | - | - | 경고만 | 버그로 보고 |

### 대기 진입 (loop-check exit 10)
1. 사용자에게 한 줄 보고: "일시정지됨 — 대시보드에서 재개하세요 (완료 <i>/<N>)".
2. `python3 aidlc/scripts/aidlc.py wait-resume; echo "exit=$?"` 를 Bash **`timeout: 600000`** 으로 호출한다. `--max-wait` 는 주지 않는다(기본 540 s, Bash 600 s 상한 아래 여유 — R-01 실측 D-41).
3. exit 10 이면 추가 설명·요약 없이 같은 호출을 반복한다(토큰 최소화). 대기 1회 ≈ 9분, 2시간 ≈ 14회.
4. exit 20(일시정지 상한 초과, 기본 2시간): 루프를 정상 종료로 보고한다 — "일시정지 상한 초과로 종료, 남은 반복 <N−i>회: `/aidlc-run <N−i>`". STM 은 건드리지 않는다. `loop-end` 는 호출하지 않는다(CLI 가 이미 `ended`·`pause_timeout` 으로 기록, 호출해도 no-op).

### 사용자가 대시보드에서 보는 상태 (루프 제어 패널)
| 화면 라벨 | 뜻 | 스킬 쪽 상황 |
|-----------|----|--------------|
| 실행 중 | 루프가 돌고 있음 (완료/전체 반복) | 사이클 진행 중 |
| 일시정지 요청됨 (현재 Task 진행 중) | 요청을 받았고 현재 Task·cascade 를 마치면 멈춤 | 다음 `loop-check` 에서 exit 10. 마지막 사이클 중이면 멈추지 않고 그대로 끝남 |
| 일시정지됨 (세션 대기 중) | 세션이 `wait-resume` 으로 대기, 남은 허용 시간 표시 | 대기 루프 중 |
| 재개 요청됨 | 재개를 눌렀고 세션이 곧 감지(1초 이내) | `wait-resume` 이 exit 0 을 낼 차례 |
| 세션 없음 | 대기하던 세션이 사라짐(heartbeat 120 s 초과) | 창이 닫힘 등 — 사용자가 `/aidlc-run <남은 수>` 로 다시 실행 |
| 루프 없음 | 루프가 끝났거나 시작 전. 종료 사유 문구(완료 / 막힘 / Task 없음 / 일시정지 상한 초과 + 남은 반복) 표시 | `loop-end` 또는 exit 20 이후 |

## 반복 & 보고
반복 횟수만큼 1~7 을 반복한다(사이클 사이에 위 루프 경계 규칙). outcome 이 blocked 이면 반복을 멈추고 blocker 를 보고한다.
끝나면 사이클별 `T-ID / 팀 / 리뷰(PASS·FAIL 팀) / outcome / LTM 추가 항목 수 / 새 Task 수` 표와 `aidlc.py status` 결과를 보여준다. 루프가 일시정지 상한·경고(exit 2/1)로 영향을 받았으면 그 사실을 한 줄 덧붙인다.
