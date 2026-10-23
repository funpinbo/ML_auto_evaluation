---
adr: 004
title: 루프 제어 — 제어 파일 + 사이클 경계 확인 + 같은 세션 대기 CLI
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [FR-005, FR-003, A7, A8, Q5, Q6, CON-03, 원칙 2, 03 §5, 03 §9, 03 §10]
---
# ADR-004. 루프 제어 방식 (03 §9 ADR 필수 대상)

## Context
- FR-005 / 01 §10: 일시정지하면 `/aidlc-run N` 이 현재 Task(cascade 포함)를 마친 뒤 **같은 세션에서 대기**, 대시보드에서 재개하면 남은 반복을 이어간다.
- 원칙 2·03 §5: 대시보드가 쓰는 파일은 제어 파일 하나. 00 Q6: 제어 파일 = `workspace/memory/.control.json`, `.claude/skills/aidlc-run/SKILL.md`·`aidlc/scripts` 수정은 이 프로젝트 범위로 승인.
- 00 Q5: 대기 반복 토큰 소비 허용, 최대 일시정지 기본 2시간(설정 가능), 초과 시 루프 정상 종료, STM 은 건드리지 않음.
- Claude Code 에는 대기 기능이 없어 Bash 도구 호출로 대기해야 한다. Bash 도구 timeout 은 기본 120 s, 최대 600 s 로 문서화(실제 상한이 더 낮다는 보고도 있음).
- 현재 Hook(`memory_cascade.py`): Stop Hook 은 응답이 끝날 때만 실행되므로 도구 호출 중에는 실행되지 않는다. PostToolUse 매처는 `Write|Edit|MultiEdit` 라 Bash 로 쓰는 파일은 Hook 을 깨우지 않는다. 사이클 경계(7단계 후)에는 미처리 cascade 가 없다.
- 두 주체(대시보드, 세션의 CLI)가 같은 파일을 쓰면 재개 요청이 heartbeat 쓰기에 덮일 수 있다.

## Decision
1. **파일 2개, 파일마다 작성자 1명 (경쟁 조건 제거)**
   - `workspace/memory/.control.json` — **대시보드만 쓴다**(사용자의 의도):
     `{"schema": 1, "seq": 7, "state": "running" | "pause", "requested_at": ISO, "max_pause_sec": 7200}`. 쓸 때마다 `seq` +1, 임시 파일 → `os.replace`.
   - `workspace/memory/.monitor/loop-status.json` — **루프 제어 CLI 만 쓴다**(세션의 실제 상태):
     `{"schema": 1, "run_id", "state": "running" | "paused" | "ended", "baseline_seq", "iterations_total", "iterations_done", "started_at", "heartbeat_at", "paused_since", "ended_reason"}`.
   - 대시보드의 쓰기는 여전히 `.control.json` 하나(원칙 2 유지). 두 파일 모두 gitignore. Hook 판정 대상 아님.
   - **1.1 seq 발급 규칙 (I-16)**: 대시보드는 쓸 때마다 `next_seq = max(prev, baseline) + 1` 로 계산한다. `prev` = 기존 `.control.json` seq(없음/broken 이면 0), `baseline` = `loop-status.json` 의 `baseline_seq`(없음/스키마 위반이면 0). 두 파일을 매번 새로 읽고(메모리 캐시 없음, 재시작 무관) 프로세스 안 락 하나로 "읽기 → 계산 → 원자적 쓰기" 를 직렬화한다. 루프 도중 제어 파일이 삭제·손상돼도 다음 POST 는 `baseline + 1` 이상이 되어 CLI 가 적용한다(FR-005 AC-18 복구 경로). CLI 판정은 그대로 `seq > baseline_seq` 와 `state` 만 본다(이전 seq 를 기억하지 않음). 대시보드의 loop-status 접근은 읽기뿐이라 파일당 작성자 1명(D-04, R-10)은 유지된다. **엄격 정수·상한**: `seq`·`baseline_seq` 는 JSON 정수 리터럴만(bool·`7.0`·지수 표기·NaN 거부), 범위 `seq` 1..2^53−1, `baseline_seq` 0..2^53−1(스키마 `maximum: 9007199254740991` + CLI·대시보드 공통 술어 `type(x) is int and lo <= x <= hi` — JSON Schema integer 는 `7.0` 을 통과시키므로 스키마만으로는 부족). 위반은 제어 파일 broken / baseline 0, 4300자리 초과 리터럴의 `ValueError` 도 broken. `next_seq` 가 상한을 넘으면 쓰지 않고 500 `CONTROL_WRITE_FAILED`. **쓰기 견고성**: 락 획득 타임아웃 2 s(초과 → 500 `CONTROL_WRITE_FAILED`, D-26 닫힌 집합 유지), 락 안에서는 파일 I/O 와 `os.replace` 재시도(5회·50 ms)만, 실패 시 임시 파일 삭제, `CONTROL_WRITE_FAILED` message 는 고정 문자열(경로·예외문 미포함). 상세·시나리오 SQ-1~SQ-21: `contracts/loop-cli.md` §2.1·§7.
2. **CLI (`aidlc/scripts/loop_control.py`, `aidlc.py` 서브커맨드, 표준 라이브러리)**
   - `loop-start <N>`: 새 `run_id`, `baseline_seq = 현재 .control.json seq`(시작 전에 남아 있던 요청은 무시), state running. exit 0.
   - `loop-check <done>`: `iterations_done`·`heartbeat_at` 갱신. `.control.json` 의 `seq > baseline_seq` 이고 `state == "pause"` 면 exit 10(일시정지), 아니면 exit 0.
   - `wait-resume [--max-wait 540]`: state paused, `paused_since` 는 처음 한 번만 기록(호출을 넘어 누적). 1초마다 제어 파일 확인, 30초마다 heartbeat. `state == "running"` 이고 `seq > baseline_seq`(재개 요청) → state running, exit 0. `--max-wait` 도달 → exit 10(아직 일시정지, 다시 호출). `now − paused_since > max_pause_sec` → state ended(`pause_timeout`), exit 20. 제어 파일 깨짐 → exit 2(경고 출력, 스킬은 계속 진행).
   - `loop-end <done|blocked|no_task>`: state ended.
3. **`/aidlc-run` 스킬 변경 (architecture 소유)**
   - 시작: `python aidlc/scripts/aidlc.py loop-start <N>` (Windows: `python3` 대신 `python`/`py` 허용 문구).
   - 각 사이클 7단계(cascade 처리)가 끝나고 다음 사이클 전에 `loop-check <완료 수>`. 마지막 사이클 뒤에는 확인하지 않는다.
   - exit 10 이면 사용자에게 "일시정지됨 — 대시보드에서 재개" 한 줄 보고 후 `wait-resume` 을 Bash `timeout: 600000` 으로 호출, exit 10 이면 같은 호출 반복(추가 설명 없이, 토큰 최소화). exit 0 → 남은 반복 진행. exit 20 → 루프 정상 종료 보고(STM 무변경, 남은 반복 수 안내).
   - 종료(정상·blocked·선택 가능 Task 없음): `loop-end <reason>`.
4. **대시보드 상태 판정 (`GET /api/v1/control`)**
   | loop-status | control (seq > baseline) | heartbeat | 화면 |
   |---|---|---|---|
   | 없음 / ended | - | - | 루프 없음 (ended_reason 표시) |
   | running | pause | - | 일시정지 요청됨 (현재 Task 진행 중) |
   | running | running/없음 | - | 실행 중 (iterations_done/total, 세션 활동 = 최근 JSONL 기록 시각) |
   | paused | pause | ≤ 120 s | 일시정지됨 (세션 대기 중, 남은 허용 시간) |
   | paused | running | ≤ 120 s | 재개 요청됨 |
   | paused | - | > 120 s | 세션 없음 (대기 세션이 사라짐 — 다음 `/aidlc-run <남은 수>` 안내) |
   `POST /control/pause` 는 loop-status 가 running/paused 일 때만 허용(아니면 409 `NO_ACTIVE_LOOP`). `POST /control/resume` 은 언제나 허용(멱등).
5. **최대 일시정지**: `max_pause_sec` 기본 7200, `POST /control/pause` 본문으로 600~86400 범위 지정 가능(Pydantic 검증).
6. **Hook 영향 없음 확인 테스트**: `.control.json`/`.monitor/` 존재 여부와 무관하게 `Memory.pending()`·`summary()` 결과가 같음, Stop Hook 상태 파일(`.cascade-state.json`) 불변.

## Alternatives
- **A. 단일 파일 `.control.json` 에 대시보드 요청과 heartbeat 를 함께 기록**(초기 제안): 파일 수는 적지만 두 작성자가 읽고-고쳐-쓰기를 해서 재개 요청 유실 가능, 그리고 "대시보드가 쓰는 파일 하나"를 CLI 도 쓰게 되어 소유가 섞임. 기각.
- **B. 일시정지 = 루프 종료, 재개 = 사용자가 `/aidlc-run <남은 수>` 재입력**: 가장 단순하고 토큰 0이지만 01 §10 "같은 세션 자동 재개" 결정과 다름. **스파이크 실패 시 후퇴안**으로 유지(대시보드 상태표의 ended/no_session 경로가 이미 이를 지원).
- **C. Stop Hook 이 pause 일 때 종료를 막아 대기**: Stop Hook 은 최대 3회 차단 후 허용하는 구조이고 cascade 판정과 섞여 위험(CLAUDE.md cascade 규칙). 기각.
- **D. Bash `run_in_background` + 알림으로 대기**: 대기 중 세션이 응답을 끝내 Stop Hook 이 돌고 루프 문맥이 끊길 수 있음, 동작 보장 불명. 기각.
- **E. Hook(memory_cascade.py) 에 제어 로직 추가**: Hook 은 cascade 전용으로 두는 편이 유지보수에 낫다. 기각.

- **F. (I-16 대안) CLI 가 "제어 파일이 직전에 없음/broken 이었으면 seq 증가가 아니라 변경만으로 새 요청" 으로 판정**: loop-check·wait-resume 는 호출마다 새 프로세스라 "직전 상태" 를 `loop-status.json` 에 저장해야 함(스키마 변경, CLI 상태 증가). 제어 파일 없음은 정상 상태(루프 시작 전 흔함)라 "없음 → seq 1" 을 새 요청으로 볼지 판정이 모호하고, 1초 tick 사이에 삭제 → 재생성이 끝나면 변화를 놓친다. 기각.
- **G. (I-16 대안) 시각 기반 요청 id(예: epoch ms)**: 이전 값 없이도 대개 커지지만 벽시계는 단조가 아니다(NTP 보정·수동 변경으로 뒤로 가면 baseline 이하가 됨). 테스트에 시계 주입이 필요해지고 seq 의미가 바뀌어 계약 변경이 크다. 결정적이지 않아 기각. 원칙 3(표준 라이브러리) 관점에서는 모두 동등.

## Consequences
- (+) 쓰기 경쟁 없음, 오래된 일시정지 요청이 새 루프를 멈추지 않음(`baseline_seq`).
- (+) Task·cascade 중간에는 절대 멈추지 않음(사이클 경계에서만 확인).
- (−) 대기 중 약 9분마다 대기 호출 1회분 토큰·컨텍스트 소비(2시간 = 약 14회). Bash 실질 상한이 낮으면 `--max-wait` 를 낮춰 호출 수 증가.
- (−) 세션(VS Code 창)이 닫히면 자동 재개 불가 → "세션 없음" 표시 + 재실행 안내.
- (−) 프레임워크 파일(SKILL.md, aidlc.py) 변경 → architecture 리뷰, `docs/aidlc` 는 수정하지 않음(CLAUDE.md).
- (+) I-16 해결: 제어 파일 삭제·손상 후에도 다음 POST 로 복구(AC-18). 수정은 대시보드 쪽 seq 계산 하나이고 CLI·스키마 구조·`schema_version` 은 그대로(하위 호환).
- (−) 대시보드 쓰기 경로가 loop-status 읽기에 의존한다(읽기 실패 시 baseline 0 → 그때는 활성 루프도 없음).
- 검증: 02 §5 필수 "일시정지/재개 시나리오 테스트"(상태 전이 표 전체, 타임아웃, 깨진 파일, 오래된 요청 무시) + 1주차 실제 `/aidlc-run 3` 리허설(30분·2시간).

## 변경 이력
- 2026-10-23 T-026 (I-16): Decision 1.1 seq 발급 규칙 추가 — `next_seq = max(이전 seq(없음/broken 이면 0), loop-status.baseline_seq(없음/깨짐이면 0)) + 1`, 매 쓰기마다 두 파일 재판독 + 프로세스 내 락. Alternatives F(CLI 변경 감지)·G(시각 기반 id) 기각. 근거: 원칙 2(대시보드 쓰기는 `.control.json` 하나 유지), D-04/R-10(파일당 작성자 1명), 03 §9(루프 제어 방식은 ADR 필수). 계약: `contracts/loop-cli.md` §7, `control.schema.json` `seq` 설명. 파일 형식·CLI 동작 변경 없음.
- 2026-10-23 T-026 (security 리뷰 FAIL 조치): Decision 1.1 에 엄격 정수·상한·쓰기 견고성 추가 — `control.schema.json` `seq`·`loop-status.schema.json` `baseline_seq` 에 `maximum: 9007199254740991`(2^53−1), CLI·대시보드 공통 판정 `type(x) is int` + 범위(bool·`7.0`·지수 표기 거부, 범위 밖 → broken / baseline 0, 4300자리 초과 → broken), `next_seq` 상한 초과 시 미기록 + 500 `CONTROL_WRITE_FAILED`, 락 획득 타임아웃 2 s, 락 안 작업 한정, 실패 시 임시 파일 삭제, 고정 에러 message. SQ-16~SQ-21 추가. 근거: 원칙 2(쓰기 경로 `.control.json` 하나 유지), user/03 §2 가용성("파일이 깨져도 죽지 않을 것")·보안 2순위, 02 §7(응답에 경로 미노출), D-26(에러 코드 닫힌 집합 — 새 코드 없음), R-10(작성자 무변경). 하위 호환: 정상 파일(정수 seq, 2^53−1 이하)은 그대로 유효, `schema` 값·CLI exit code·stdout 무변경. 이전에 통과하던 `7.0`·bool·초대형 seq 는 이제 broken(손상 입력으로만 생기는 값이라 정상 작성자 영향 없음).
