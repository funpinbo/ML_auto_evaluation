---
doc: contract
contract: loop-cli
schema_version: 1
owner: architecture
implementer: backend (aidlc/scripts/loop_control.py + aidlc.py subcommands)
consumers: .claude/skills/aidlc-run/SKILL.md, dashboard backend (reads loop-status.json)
sources: [ADR-004, 20 §5 F4·F5·F6, 20 §4 루프 제어 CLI, R-01, R-09, R-10]
---
# 루프 제어 CLI 계약 (`aidlc.py loop-*`)

> `/aidlc-run` 스킬이 Bash 도구로 호출하는 4개 서브커맨드의 인자·exit code·stdout·파일 쓰기 규칙.
> 이 문서와 `control.schema.json`, `loop-status.schema.json` 이 구현(`aidlc/scripts/loop_control.py`)과 테스트의 기준이다.
> 표준 라이브러리만 사용(원칙 3). 대시보드 쓰기 범위는 `.control.json` 하나로 유지된다(원칙 2, 03 §5).

## 1. 호출 형식
```
python3 aidlc/scripts/aidlc.py loop-start <N>
python3 aidlc/scripts/aidlc.py loop-check <done>
python3 aidlc/scripts/aidlc.py wait-resume [--max-wait <sec>]
python3 aidlc/scripts/aidlc.py loop-end <done|blocked|no_task> [--done <done>]
```
- 작업 디렉터리 = 저장소 루트. 파일 경로는 스크립트 위치 기준 저장소 루트에서 계산한다(환경 변수 비의존, cwd 비의존).
- Windows: `python3` 가 없으면 `python` 또는 `py -3` 로 같은 인자를 넘긴다(R-09). 출력은 UTF-8, 줄바꿈 LF.
- 인자: `N` 정수 1~10(aidlc-run 최대 반복), `done` 정수 0~N, `--max-wait` 정수 1~580(기본 540).

## 2. 파일과 작성자 (R-10 단일 작성자)
| 파일 | CLI | 대시보드 |
|------|-----|----------|
| `workspace/memory/.control.json` | **읽기만** | 쓰기(유일) |
| `workspace/memory/.monitor/loop-status.json` | 쓰기(유일) | 읽기만 |

- CLI 는 `.control.json` 을 어떤 경우에도 만들거나 고치지 않는다.
- `loop-status.json` 쓰기 = `.monitor/` 디렉터리 생성(없으면) → 같은 디렉터리 임시 파일 → `os.replace`.
- `loop-status.json` 쓰기 실패(디스크·권한)는 stderr 경고만 내고 **exit code 를 바꾸지 않는다**(루프를 멈추지 않는다 — 상태 파일은 화면 표시용).

### 2.1 제어 파일 판독 규칙
| `.control.json` 상태 | 판독 결과 |
|----------------------|-----------|
| 없음 | `seq = 0`, `state = running` (정상, 경고 없음) |
| JSON 오류 / UTF-8 아님 / `control.schema.json` 위반(`schema ≠ 1`, 범위 밖 `max_pause_sec` 포함) | **broken** |
| 정상 | 파일 값 |

`max_pause_sec` 는 판독 시점의 제어 파일 값을 쓴다(없거나 broken 이면 7200).

## 3. 서브커맨드
### 3.1 `loop-start <N>`
- 새 `run_id`(uuid4 hex), `state = running`, `baseline_seq = 현재 control seq`(없거나 broken 이면 0), `iterations_total = N`, `iterations_done = 0`, `started_at = heartbeat_at = now`, `paused_since = null`, `ended_reason = null`.
- 이전 `loop-status.json` 이 무엇이든(running 으로 남은 죽은 세션 포함) 덮어쓴다.
- exit **0**. 제어 파일 broken 이면 stderr 경고 후 exit **2**(스킬은 계속 진행).

### 3.2 `loop-check <done>`
- `iterations_done = done`, `heartbeat_at = now`, `state = running` 기록.
- **일시정지 조건**: `control.seq > baseline_seq` **그리고** `control.state == "pause"` → exit **10**.
- 그 외 → exit **0**. 제어 파일 broken → exit **2**(계속 진행).
- 활성 루프 없음(`loop-status.json` 없음/깨짐/`ended`): 아무것도 쓰지 않고 일시정지 판정도 하지 않는다. stderr 경고, stdout `NO_LOOP`, exit **0**(루프를 멈추지 않는다).

### 3.3 `wait-resume [--max-wait <sec>]`
1. 진입 시: `state = paused`. `paused_since` 가 null 이면 now 로 설정, 이미 있으면 **유지**(반복 호출을 넘어 누적). `heartbeat_at = now`.
2. 1초마다 제어 파일 판독:
   - **재개 조건** `control.state == "running"` 그리고 `control.seq > baseline_seq` → `state = running`, `paused_since = null`, exit **0**.
     (pause 이후 resume 이 쓰이면 seq 가 반드시 증가하므로 충분하다. 제어 파일이 사라진 경우는 재개로 보지 않는다 — seq 0.)
   - broken → `state = running`, `paused_since = null`, stderr 경고, exit **2**(스킬은 남은 반복 계속).
   - `now − paused_since > max_pause_sec` → `state = ended`, `ended_reason = pause_timeout`(`paused_since` 유지), exit **20**.
3. 30초마다 `heartbeat_at = now` 기록.
4. 호출 시작 후 `--max-wait` 초 경과 → 상태 유지(`paused`), exit **10**(스킬이 즉시 다시 호출).
- 판정 순서(같은 tick): 재개 → broken → 상한 초과 → max-wait.
- 활성 루프 없음(`loop-status.json` 없음/깨짐/`ended`): 쓰지 않고 exit **0**(대기할 루프 없음, stderr 경고).

### 3.4 `loop-end <reason> [--done <done>]`
- `reason ∈ {done, blocked, no_task}` (`pause_timeout` 은 wait-resume 만 기록). `state = ended`, `ended_reason = reason`, `paused_since = null`, `heartbeat_at = now`, `--done` 이 있으면 `iterations_done` 갱신.
- 이미 `ended` 이면 아무것도 쓰지 않는다(첫 `ended_reason` 보존, 예: `pause_timeout`). 활성 루프 없음도 no-op. 항상 exit **0**.

## 4. Exit code (스킬이 분기하는 유일한 기준)
| code | 이름 | 발생 | 스킬 동작 |
|------|------|------|-----------|
| 0 | OK / resumed | 모든 서브커맨드 정상, wait-resume 재개 | 다음 단계 진행 |
| 10 | paused / still paused | loop-check: 일시정지 요청 / wait-resume: max-wait 도달 | `wait-resume` 호출(반복) |
| 20 | pause cap exceeded | wait-resume: 일시정지 상한 초과 | 루프 정상 종료 보고(STM 무변경, 남은 반복 수 안내). `loop-end` 불필요(호출해도 no-op) |
| 2 | control file broken | loop-start/loop-check/wait-resume 에서 제어 파일 broken | stderr 경고를 사용자에게 한 줄 보고 후 **계속 진행**(일시정지하지 않음) |
| 64 | usage error | 인자 누락·범위 밖·알 수 없는 reason | 스킬 버그 — 루프 중단하고 보고 |

- argparse 기본 usage 오류 코드(2)는 "control broken" 과 겹치므로 loop-* 서브커맨드는 usage 오류를 **64** 로 낸다(구현 시 `ArgumentParser.error` 재정의 또는 서브커맨드 자체 파싱).
- 그 밖의 예기치 못한 예외: stderr 에 예외 종류만 출력, exit **1**. 스킬은 경고 보고 후 계속 진행(루프를 멈추는 기본값은 일시정지 요청뿐).

## 5. stdout 형식
한 줄, 기계·사람 겸용. 토큰 절약을 위해 이 한 줄 외에는 stdout 에 쓰지 않는다(경고·진단은 stderr).
```
AIDLC-LOOP <subcommand> <RESULT> key=value ...
```
| 서브커맨드 | RESULT (exit) | 키 |
|------------|---------------|----|
| loop-start | `STARTED`(0), `CONTROL_BROKEN`(2) | `run=<run_id 앞 8자> total=<N> baseline=<seq>` |
| loop-check | `CONTINUE`(0), `PAUSE`(10), `CONTROL_BROKEN`(2), `NO_LOOP`(0) | `done=<d>/<N> seq=<s> baseline=<b>` |
| wait-resume | `RESUMED`(0), `STILL_PAUSED`(10), `PAUSE_TIMEOUT`(20), `CONTROL_BROKEN`(2), `NO_LOOP`(0) | `paused_sec=<경과> remaining_sec=<상한까지> done=<d>/<N>` |
| loop-end | `ENDED`(0), `ALREADY_ENDED`(0), `NO_LOOP`(0) | `reason=<reason> done=<d>/<N>` |

예: `AIDLC-LOOP wait-resume STILL_PAUSED paused_sec=1080 remaining_sec=6120 done=1/3`
- 스킬은 exit code 로만 분기하고 stdout 은 보고용으로만 쓴다. 키 추가는 하위 호환(소비자는 모르는 키 무시), 키 삭제·RESULT 의미 변경은 깨지는 변경(architecture 리뷰 + ADR-004 갱신).
- stdout/stderr 에 파일 경로·대화 내용을 쓰지 않는다(02 §7).

## 6. Heartbeat 규칙
- `heartbeat_at` 은 loop-* 서브커맨드가 `loop-status.json` 을 쓸 때마다 now 로 갱신되고, `wait-resume` 실행 중에는 **30초마다** 갱신된다.
- `running` 중에는 사이클 경계(`loop-check`)에서만 갱신된다(Task 하나가 오래 걸릴 수 있음) → 대시보드는 `running` 상태에서 heartbeat 나이로 세션 생존을 판정하지 **않는다**(ADR-004 §4 표대로 세션 활동은 최근 JSONL 시각으로 표시).
- `paused` 상태에서 `heartbeat_age > 120 s` → 대시보드 표시 "세션 없음"(no_session). 반복 호출 사이 간격은 수 초라 정상 대기는 120 s 를 넘지 않는다. 감지 ≤ 2분(QS-11).

## 7. `baseline_seq` 의미
- `loop-start` 시점의 control `seq`. 이 값 **이하**의 요청은 이번 루프에 적용되지 않는다 → 이전 루프에서 남은 `pause` 가 새 루프를 멈추지 않는다(ADR-004 Consequences).
- 루프 도중에는 바뀌지 않는다. 같은 루프에서 일시정지 → 재개 → 다시 일시정지도 동작한다: 쓰기마다 seq 가 증가하므로 판정은 항상 "최신 요청(seq > baseline)의 state".
- 대시보드는 control 파일이 없거나 broken 일 때 이전 seq 를 0 으로 보고 1부터 쓴다. 이 경우 CLI 의 baseline 도 0 이므로 새 요청은 적용된다.
- 대시보드 화면 판정(ADR-004 §4)의 "control (seq > baseline)" 열도 같은 규칙을 쓴다.

## 8. 상태 전이
```
(없음|ended) --loop-start--> running
running --loop-check: exit 0/2--> running
running --loop-check: exit 10--> running   (스킬이 이어서 wait-resume)
running|paused --wait-resume 진입--> paused
paused --재개(0) / broken(2)--> running
paused --max-wait(10)--> paused
paused --상한 초과(20)--> ended(pause_timeout)
running|paused --loop-end--> ended(reason)
```

## 9. 스킬 호출 규칙 요약 (SKILL.md 가 따를 것)
1. 시작: `loop-start <N>`.
2. 각 사이클 7단계 후, 마지막 사이클이 아니면 `loop-check <완료 수>`.
3. exit 10 → "일시정지됨 — 대시보드에서 재개" 한 줄 보고 → `wait-resume` 을 Bash `timeout: 600000` 으로 호출, exit 10 이면 설명 없이 같은 호출 반복.
4. exit 0 → 남은 반복 진행 / exit 20 → 정상 종료 보고 / exit 2 → 경고 한 줄 후 진행.
5. 종료: `loop-end <done|blocked|no_task> --done <완료 수>` (exit 20 으로 끝난 경우 생략 가능).
- `--max-wait` 기본 540 은 Bash 600 s 상한 아래 여유를 둔 값. R-01 스파이크에서 실질 상한이 낮으면 스킬 쪽 인자만 낮춘다(예: `--max-wait 50`) — 계약 변경 아님.

## 10. 테스트 기준 (qa / backend)
- 상태 전이 표 전체, exit code 5종(0/10/20/2/64), `baseline_seq` 로 오래된 pause 무시, 같은 루프 재일시정지, `paused_since` 누적(반복 호출), 상한 초과, max-wait 반환, 제어 파일 없음/깨짐/스키마 위반, 쓰기 결과가 `loop-status.schema.json` 에 맞음, CLI 가 `.control.json` 을 절대 쓰지 않음, 시간 주입(시계·sleep 대체)으로 빠르게 실행.
