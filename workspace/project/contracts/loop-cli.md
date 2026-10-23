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
| 정수 필드(`schema`·`seq`·`max_pause_sec`)가 아래 "엄격 정수" 판정에 실패(bool, `7.0`, `7e0`, `NaN`/`Infinity`, 범위 밖, 4300자리 초과 리터럴) | **broken** |
| 정상 | 파일 값 |

`max_pause_sec` 는 판독 시점의 제어 파일 값을 쓴다(없거나 broken 이면 7200).

**엄격 정수 판정 (CLI·대시보드 공통, 같은 술어)**
```
SEQ_MAX = 9007199254740991            # 2^53 - 1 (JS Number 안전 정수, 프론트 표시 정밀도 보장)
is_strict_int(x, lo, hi) = type(x) is int and lo <= x <= hi
  seq:           lo = 1, hi = SEQ_MAX     (control.schema.json)
  baseline_seq:  lo = 0, hi = SEQ_MAX     (loop-status.schema.json)
  max_pause_sec: lo = 600, hi = 86400
```
- 정수는 **JSON 정수 리터럴만** 받는다. `true`/`false`(Python `bool` 은 `int` 하위형이라 `isinstance` 로는 통과 — 금지, `type(x) is int` 를 쓴다), `7.0`·`7e0`·`7E+0`(Python `json` 은 float 로 파싱) 은 거부한다.
- JSON Schema 2020-12 의 `"type": "integer"` 는 `7.0` 을 정수로 통과시키므로 **스키마 검증만으로는 부족하다**. 스키마 `maximum` 과 위 술어를 함께 적용한다(CLI 는 표준 라이브러리만 쓰므로 술어가 곧 검증, 대시보드는 jsonschema/Pydantic 검증 뒤 같은 술어를 추가로 적용).
- `NaN`/`Infinity`/`-Infinity` 는 `json.loads(..., parse_constant=<예외 발생>)` 로 거부한다.
- Python 의 정수 문자열 변환 상한(`sys.int_info.str_digits_check_threshold`, 기본 4300자리)을 넘는 리터럴은 `json.loads` 가 `ValueError` 를 낸다. 판독기는 `parse_int` 훅으로 숫자 문자열 길이를 먼저 검사(16자리 초과면 범위 밖으로 거부)하거나 `ValueError` 를 잡아 **broken** 으로 처리한다 — 예외가 밖으로 나가 500·exit 1 이 되면 안 된다.
- 범위 밖: `.control.json` 이면 **broken**, `loop-status.json` 의 `baseline_seq` 이면 대시보드는 baseline **0** 으로 본다(§7.1). CLI 가 자기 파일을 다시 읽을 때(loop-check 등) loop-status 가 이 판정에 실패하면 "활성 루프 없음"(§3.2) 과 같다.

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

## 7. `baseline_seq` 의미와 `seq` 발급 규칙
- `loop-start` 시점의 control `seq`. 이 값 **이하**의 요청은 이번 루프에 적용되지 않는다 → 이전 루프에서 남은 `pause` 가 새 루프를 멈추지 않는다(ADR-004 Consequences).
- 루프 도중에는 바뀌지 않는다. 같은 루프에서 일시정지 → 재개 → 다시 일시정지도 동작한다: 쓰기마다 seq 가 증가하므로 판정은 항상 "최신 요청(seq > baseline)의 state".
- 대시보드 화면 판정(ADR-004 §4)의 "control (seq > baseline)" 열도 같은 규칙을 쓴다.

### 7.1 대시보드의 다음 seq (I-16 해결, ADR-004 Decision 1.1)
대시보드는 `.control.json` 을 쓸 때마다 다음 값을 **두 파일을 새로 읽어** 계산한다(메모리에 seq 를 캐시하지 않는다).
```
prev     = .control.json 의 seq   (파일이 정상일 때만, 없음/broken 이면 0)        — §2.1 판독 규칙
baseline = loop-status.json 의 baseline_seq (loop-status.schema.json 에 맞을 때만, 없음/깨짐이면 0)
next_seq = max(prev, baseline) + 1
```
- 정상 경로에서는 `prev ≥ baseline` 이므로 `next_seq = prev + 1`(기존 규칙과 같음, FR-005 AC-1·AC-4·AC-10).
- 루프 도중 제어 파일이 삭제·손상되면 `prev = 0` 이 되지만 `baseline` 이 하한이 되어 `next_seq = baseline + 1 > baseline` → **CLI 가 다음 POST 를 새 요청으로 적용한다**(AC-18 "다음 POST 로 복구").
- `ended` 인 loop-status 의 baseline 도 그대로 쓴다(값이 커질 뿐 해가 없음). loop-status 가 없거나 깨졌으면 활성 루프가 없다는 뜻이고(§3.2 `NO_LOOP`), pause 는 409 로 쓰지 않으며 resume 이 쓴 seq 는 다음 `loop-start` 의 baseline 이 될 뿐이다.
- 대시보드는 `loop-status.json` 을 **읽기만** 한다(이미 `GET /control` 의 읽기 대상). 파일별 작성자는 그대로다(R-10, D-04).
- `max_pause_sec`: pause 는 요청 본문 값(기본 7200), resume 은 `prev` 가 정상일 때 그 값을 유지하고 아니면 7200.
- `prev`·`baseline` 판독은 §2.1 엄격 정수 판정을 따른다: `.control.json` 이 판정에 실패하면 broken → `prev = 0`, `loop-status.json` 이 스키마 또는 판정에 실패하면 `baseline = 0`. 손상 입력 때문에 예외가 나거나 500 이 고착되지 않는다.
- **상한 초과**: 계산한 `next_seq > SEQ_MAX`(2^53−1) 이면 **쓰지 않는다** — 기존 파일 그대로, 500 `CONTROL_WRITE_FAILED`. 정상 사용(초당 1회 쓰기로도 2억 년 이상)에서는 도달하지 않고, 수동 편집으로 상한 근처 값이 들어간 경우에만 생긴다. 복구는 사용자가 제어 파일을 지우는 것(그래도 baseline 이 상한이면 다음 `loop-start` 후 해소).

### 7.2 CLI 쪽 규칙 (변경 없음, 명시)
- CLI 판정은 매 판독마다 `(control.seq > baseline_seq, control.state)` 만 본다. 이전에 본 seq 를 기억하거나 "seq 가 바뀌었는지" 로 판정하지 않는다 → 제어 파일 재생성으로 같은 seq 값이 다시 쓰여도(예: 삭제 전 8, 재생성 후 8) 판정이 맞다.
- 제어 파일 **없음** 은 `seq 0, running`(정상, 경고 없음)이라 일시정지·재개 어느 쪽도 일으키지 않는다. 대기 중 파일이 사라지면 계속 대기한다(§3.3).
- 제어 파일 **broken** 은 exit 2(계속 진행, 대기 중이면 재개 — §3.3, AC-18).

### 7.3 경쟁 조건
| 경우 | 처리 |
|------|------|
| 대시보드가 쓰는 중 CLI 가 읽음 | 같은 디렉터리 임시 파일 → `os.replace` 이므로 CLI 는 이전 파일 또는 새 파일 전체만 본다. 반쪽 파일 없음 |
| 대시보드 POST 두 개가 동시에 도착 | 대시보드 프로세스(단일 프로세스, ADR-001) 안의 **락 하나**로 "두 파일 읽기 → next_seq 계산 → 쓰기" 전체를 직렬화한다. 두 요청은 서로 다른 연속 seq 를 받고, 파일에는 나중 요청이 남는다(최신 요청 우선) |
| CLI 가 loop-status 를 쓰는 중 대시보드가 baseline 을 읽음 | CLI 도 원자적 교체 → 이전/새 파일 중 하나. 루프 도중 `baseline_seq` 는 바뀌지 않으므로 어느 쪽이든 같은 값 |
| POST 와 `loop-start` 가 거의 동시 | `loop-start` 가 제어 파일을 읽기 **전**에 쓰인 요청은 이번 루프의 baseline 이하 → 무시(루프 시작 전 요청, AC-12 와 같은 의미). 읽은 **후**에 쓰인 요청은 `next_seq ≥ 그 시점 seq + 1 > baseline` → 적용. 어느 순서든 파일 단일 작성자·seq 단조성은 유지 |
| Windows 에서 읽는 쪽이 파일을 연 순간 `os.replace` 가 `PermissionError` | 쓰는 쪽이 짧게 재시도(최대 5회, 50 ms 간격 — 락 보유 시간 상한 약 0.3 s). 대시보드는 끝내 실패하면 500 `CONTROL_WRITE_FAILED`(AC-20, 기존 파일 보존). CLI 는 §2 대로 경고만 |
| POST 연타(수십 개 동시) | 락 획득은 **타임아웃 2 s**(`threading.Lock.acquire(timeout=2.0)`, 무한 대기 금지). 시간 안에 못 얻으면 쓰지 않고 500 `CONTROL_WRITE_FAILED`. 락 안에서 하는 일은 "두 파일 읽기 → 계산 → 임시 파일 쓰기 → `os.replace`(재시도 포함)" 뿐이고 sleep·네트워크·SSE 대기를 하지 않는다 → 락 보유 상한 ≈ 재시도 상한(0.3 s) + 파일 I/O. 락은 `with`/`try-finally` 로 반드시 해제(예외 경로 포함). 동기 핸들러는 스레드풀에서 돌므로 요청 하나의 지연 상한 ≈ 2 s + 보유 상한 |
| 쓰기 실패 정리 | 어떤 실패(락 타임아웃 제외 — 그때는 아무것도 만들지 않음)든 이번 요청이 만든 임시 파일을 `finally` 에서 삭제한다(`os.unlink`, 이미 없으면 무시). 기존 `.control.json` 은 바뀌지 않는다. 임시 파일 이름은 고정 접두어(예: `.control.json.<random>.tmp`)로 같은 디렉터리에 만든다 |
| 실패 응답 내용 | 500 `CONTROL_WRITE_FAILED` 의 `message` 는 **고정 문자열**("제어 파일을 쓰지 못했습니다. 잠시 후 다시 시도하세요." 등 구현이 한 번 정한 값). 파일 경로·예외 메시지·errno·스택을 응답에 넣지 않는다(02 §7). 원인은 콘솔 로그에 예외 종류만 남긴다. 에러 코드는 D-26 닫힌 9개 집합 안의 `CONTROL_WRITE_FAILED` 하나만 쓴다(새 코드 추가 없음) |
| 대시보드 프로세스가 2개 이상 | 계약 범위 밖(ADR-001 이 중복 실행을 막음). 이 경우 락이 공유되지 않아 seq 중복이 가능하다 |

### 7.4 테스트 시나리오 (T-008 이 그대로 테스트로 옮긴다)
공통: baseline = 7 인 활성 루프(`loop-start` 당시 control seq 7). "POST" = 대시보드 `POST /api/v1/control/pause|resume`. 시계·sleep 주입.

| # | 준비 | 동작 | 기대 결과 |
|---|------|------|-----------|
| SQ-1 | running, control seq 9 `running` | 제어 파일 삭제 → `loop-check 1` | exit 0 `CONTINUE`(없음 = 정상, 경고 없음, stderr 비어 있음) |
| SQ-2 | SQ-1 이후 | POST pause → `loop-check 1` | 파일 `seq 8, pause`(schema 통과) → exit 10 `PAUSE` |
| SQ-3 | paused(wait-resume 중), control seq 8 `pause` | 제어 파일 삭제 → 3 tick 경과 | 계속 대기(exit 없음), loop-status `paused` 유지 |
| SQ-4 | SQ-3 이후 | POST resume | 파일 `seq 8, running` → 다음 1초 tick 안에 wait-resume exit 0 `RESUMED` |
| SQ-5 | paused, control seq 8 `pause` | 제어 파일을 잘린 JSON 으로 교체 | 다음 tick 에 wait-resume exit 2 `CONTROL_BROKEN`, loop-status `running`·`paused_since null` (AC-18) |
| SQ-6 | SQ-5 이후(파일 여전히 broken) | `loop-check 2` → POST resume → `loop-check 2` | 첫 호출 exit 2. POST 후 파일 `seq 8, running` → exit 0 `CONTINUE` |
| SQ-7 | running, 제어 파일 broken | POST pause → `loop-check 1` | 파일 `seq 8, pause` → exit 10 (손상된 파일에서 다음 POST 로 복구) |
| SQ-8 | running, control seq 9 | 대시보드 재시작 후 POST pause | 파일 `seq 10, pause`(재시작 전과 같은 결과 — 메모리 상태 없음) |
| SQ-9 | running, 제어 파일 없음 | 대시보드 재시작 후 POST pause | 파일 `seq 8, pause` → `loop-check` exit 10 |
| SQ-10 | running, control seq 9 `running` | POST pause, POST resume 를 연달아(동시 스레드 포함) | 서로 다른 seq 10·11, 파일 최종 = 나중에 처리된 요청. pause→resume 순이면 `loop-check` exit 0(AC-8 과 같음) |
| SQ-11 | running, control seq 9 | POST pause 두 개 동시 | seq 10·11 둘 다 pause, 최종 파일 seq 11, 유실·중복 seq 없음, 파일 schema 통과 |
| SQ-12 | loop-status 없음, 제어 파일 없음 | POST resume → `loop-start 2` | 파일 `seq 1, running`, loop-start `baseline=1`. POST pause 는 409 `NO_ACTIVE_LOOP`, 파일 무변경 |
| SQ-13 | running, control seq 3(수동 편집으로 baseline 7 보다 작음) | POST pause → `loop-check 1` | 파일 `seq 8, pause` → exit 10 |
| SQ-14 | loop-start 시 제어 파일 broken (baseline 0, exit 2) | POST pause → `loop-check 1` | 파일 `seq 1, pause` → exit 10 |
| SQ-15 | 모든 SQ | - | CLI 는 `.control.json` 을 만들거나 고치지 않음(mtime·내용 불변), 대시보드는 `loop-status.json` 을 쓰지 않음(R-10) |
| SQ-16 | control seq 9 `running`, loop-status `baseline_seq` 를 각각 `-1` / `"7"` / `true` / `7.0` / `9007199254740992`(상한+1) / 4301자리 정수 / 스키마 위반(필드 누락)으로 교체 | POST resume, 이어서 POST pause | 각 경우 baseline = 0, 예외·고착 500 없음. resume → 파일 `seq 10, running`(schema·엄격 정수 통과, `10.0` 아님). loop-status 가 깨짐 = 활성 루프 없음이므로 pause → 409 `NO_ACTIVE_LOOP`, 파일 무변경(§7.1) |
| SQ-17 | 활성 루프, `.control.json` 의 `seq` 를 각각 `7.0` / `true` / `9007199254740992` / `8e0` / 4301자리 정수로 교체 | `loop-check 1` → POST pause → `loop-check 1` | 첫 호출 exit 2 `CONTROL_BROKEN`(CLI 술어). POST 는 prev = 0 → 파일 `seq 8, pause` → exit 10. 대시보드 `GET /control` 도 같은 파일을 broken 으로 판정(CLI 와 판정 일치) |
| SQ-18 | 활성 루프, `baseline_seq = 9007199254740991`(상한), 제어 파일 없음 | POST pause | 쓰지 않음(파일 없음 유지), 500 `CONTROL_WRITE_FAILED`, 고정 message, 임시 파일 없음 |
| SQ-19 | running, control seq 9 | POST pause/resume 50개 동시(스레드) | 모든 응답이 200 또는 500 `CONTROL_WRITE_FAILED`(락 타임아웃) 중 하나, 각 응답 ≤ 2.5 s. 성공한 요청의 seq 는 서로 다르고 연속(10 부터), 최종 파일 seq = 성공 수 + 9, schema 통과. 끝난 뒤 락이 풀려 있음(다음 POST 즉시 200), 임시 파일 없음 |
| SQ-20 | control seq 9 `running` | `os.replace` 가 매번 `PermissionError` 를 내도록 주입 → POST pause | 5회 재시도 후 500 `CONTROL_WRITE_FAILED`. 기존 파일 내용·mtime 불변, 디렉터리에 임시 파일 남지 않음, 응답 본문에 경로·예외문 없음(고정 message). 다음 POST(주입 해제)는 즉시 200 `seq 10` |
| SQ-21 | 락 획득 타임아웃 주입(다른 스레드가 락 보유) | POST pause | 2 s 뒤 500 `CONTROL_WRITE_FAILED`, 파일·디렉터리 불변(임시 파일 생성 안 함) |

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
- 상태 전이 표 전체, exit code 5종(0/10/20/2/64), `baseline_seq` 로 오래된 pause 무시, §7.4 SQ-1~SQ-21(제어 파일 삭제·손상 후 복구, 대시보드 재시작, 연속 POST, 엄격 정수·상한, POST 연타, 쓰기 재시도 소진), 같은 루프 재일시정지, `paused_since` 누적(반복 호출), 상한 초과, max-wait 반환, 제어 파일 없음/깨짐/스키마 위반, 쓰기 결과가 `loop-status.schema.json` 에 맞음, CLI 가 `.control.json` 을 절대 쓰지 않음, 시간 주입(시계·sleep 대체)으로 빠르게 실행.
