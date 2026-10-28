---
adr: 003
title: 한도·비용 수집 — 프로젝트 statusLine 스냅샷 + 사용자 전역 statusLine 체이닝
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [FR-004, FR-010, A4, A5, Q4, Q13, CON-07, 원칙 2, 원칙 3, 03 §9]
---
# ADR-003. 한도·비용 수집 방식 (사용량 데이터 수집, 03 §9 필수)

## Context
- 5시간/7일 한도 사용률·초기화 시각·세션 비용은 JSONL 에 없다. Claude Code statusLine 스크립트의 stdin JSON 에만 있다(DS-04).
- 공식 문서 확인(https://code.claude.com/docs/en/statusline): `rate_limits.five_hour/seven_day.used_percentage`(0~100), `resets_at`(epoch 초), Pro/Max 구독 + 세션 첫 응답 이후에만, 창별로 없을 수 있음. `cost.total_cost_usd`(세션 추정), `context_window.used_percentage`(초기 null 가능), `model.id`, `session_id`, `version`, `transcript_path`, `workspace.project_dir`. 설정 키 `type`, `command`, `padding`, `refreshInterval`(최소 1초). 이벤트마다 300 ms 디바운스 후 실행, 새 업데이트가 오면 실행 중 스크립트를 취소. workspace trust 수락 전에는 실행 안 함. Windows 는 Git Bash(있으면) 또는 PowerShell 로 명령 실행.
- VS Code 확장 채팅 패널에서 statusLine 이 실행되는지는 문서에 없다(미해결, 00 A5).
- 00 Q4: 프로젝트 `.claude/settings.json` 에 등록, 사용자 전역 statusLine 이 있으면 그 명령을 실행해 출력을 이어 붙인다. 02 §11: 전역 settings 변경 금지.

## Decision
1. **등록**: 프로젝트 `.claude/settings.json` 에
   `"statusLine": {"type": "command", "command": "bash \"$CLAUDE_PROJECT_DIR/aidlc/hooks/statusline.sh\"", "refreshInterval": 30}`.
   `CLAUDE_PROJECT_DIR` 이 statusLine 실행 환경에 주어지는지는 구현 첫 Task 에서 확인. 없으면 `bash aidlc/hooks/statusline.sh`(세션 cwd = 저장소 루트) 로 바꾼다. 기존 Hook 과 같은 bash 전제.
2. **`statusline.sh`**: `aidlc/hooks/run.sh` 와 같은 python3/python/py 탐지 후 `statusline.py` 실행. Python 이 없으면 빈 줄 출력, exit 0.
3. **`statusline.py` (표준 라이브러리)**:
   1. stdin 전체 읽기 → `json.loads` (실패 시 체이닝만 하고 종료).
   2. **스냅샷을 먼저 저장**(취소에 대비): 허용 필드만 골라 `{"schema": 1, "captured_at", "claude_version", "model_id", "session_hash": sha256(session_id)[:12], "transcript_dir_name", "rate_limits": {five_hour, seven_day} | null, "cost": {total_cost_usd, total_duration_ms}, "context_window": {used_percentage, context_window_size}}` 를 `workspace/memory/.monitor/claude-status.json` 에 임시 파일 → `os.replace` 로 원자적 저장. 저장 위치는 스크립트 자기 위치 기준 저장소 루트(환경 변수에 의존하지 않음). `transcript_path` 원문·`cwd`·세션 ID 원문은 저장하지 않는다.
   3. **체이닝**: `~/.claude/settings.json` 을 읽어 `statusLine.command` 만 꺼낸다(다른 키는 보지 않고 로그 금지). 명령에 `aidlc/hooks/statusline` 이 들어 있으면 재귀 방지로 생략. 있으면 같은 stdin 으로 셸 실행(timeout 2 s), 출력이 있으면 그대로 먼저 출력.
   4. 자기 한 줄 출력: 예 `AI-DLC 5h 23% · 7d 41% · $0.12` (한도 없으면 `AI-DLC ctx 8%`).
   5. 모든 예외 무시, exit 0 (세션 표시를 깨지 않음).
4. **대시보드**: 스냅샷 파일을 읽기만 한다(ADR-002 와 함께 FR-004). `captured_at` 이 10분 넘으면 `SNAPSHOT_STALE` 경고, `rate_limits` 가 null 이면 "한도 정보 없음 — Pro/Max 구독의 CLI 세션에서 첫 응답 이후 표시" 안내.
5. 여러 세션이 동시에 돌면 마지막 쓰기가 이김. 한도는 계정 기준이라 문제 없고, 비용은 `session_hash` 와 함께 "최근 세션" 으로 표기.
6. `.gitignore` 에 `workspace/memory/.monitor/` 추가. 이 디렉터리는 Hook 판정(`Memory.archived/pending`)이 보지 않는 경로이고, Bash 쓰기라 PostToolUse(Write|Edit 매처)도 발생하지 않는다.

## Alternatives
- **사용자 전역 `~/.claude/settings.json` 에 등록**: 02 §11 금지(승인 필요), 저장소 clone 만으로 동작하지 않음. 기각.
- **체이닝 없이 프로젝트 설정으로 덮기**: 사용자의 기존 표시가 사라짐(00 Q4 에서 체이닝 선택). 기각.
- **`/usage` 출력 또는 Anthropic API 조회**: 출력 파싱 불안정, API 호출은 인증 정보 접근 + 외부 전송 성격(03 §4·§8). 기각.
- **스냅샷을 `monitor/.runtime/`(00 A4 초안)에 저장**: 가능하지만 루프 상태 파일과 함께 `workspace/memory/.monitor/` 한 곳에 모아 감시·gitignore 를 단순화. 변경.
- **session_id 원문 저장**: 세션 구분에는 해시면 충분(최소 수집). 기각.

## Consequences
- (+) 한도 %·초기화 시각·비용을 추가 의존성 없이 얻는다. `refreshInterval: 30` 으로 유휴 중에도 30초 안에 갱신.
- (−) statusLine 이 실행되지 않는 환경(VS Code 패널 가능성, trust 미수락, bash 없음)에서는 한도 미표시 → FR-004 폴백. 1주차 실측 Task 필수.
- (−) 프로젝트 설정 커밋으로 이 저장소를 여는 모든 사용자에게 statusLine 이 적용됨(의도된 동작, 체이닝으로 기존 표시 유지).
- (−) 체이닝 명령이 느리면 Claude Code 가 취소할 수 있음 → 스냅샷을 먼저 저장해 데이터는 보존.
- 테스트: 가짜 stdin(한도 있음/없음/깨진 JSON), 원자적 쓰기, 허용 필드 외 키 미저장, 체이닝 재귀 방지·timeout.
