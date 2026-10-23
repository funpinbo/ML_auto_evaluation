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

## Consequences
- (+) 쓰기 경쟁 없음, 오래된 일시정지 요청이 새 루프를 멈추지 않음(`baseline_seq`).
- (+) Task·cascade 중간에는 절대 멈추지 않음(사이클 경계에서만 확인).
- (−) 대기 중 약 9분마다 대기 호출 1회분 토큰·컨텍스트 소비(2시간 = 약 14회). Bash 실질 상한이 낮으면 `--max-wait` 를 낮춰 호출 수 증가.
- (−) 세션(VS Code 창)이 닫히면 자동 재개 불가 → "세션 없음" 표시 + 재실행 안내.
- (−) 프레임워크 파일(SKILL.md, aidlc.py) 변경 → architecture 리뷰, `docs/aidlc` 는 수정하지 않음(CLAUDE.md).
- 검증: 02 §5 필수 "일시정지/재개 시나리오 테스트"(상태 전이 표 전체, 타임아웃, 깨진 파일, 오래된 요청 무시) + 1주차 실제 `/aidlc-run 3` 리허설(30분·2시간).
