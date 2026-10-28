---
doc: runbook
owner: ops
sources: [ADR-004, contracts/loop-cli.md, QS-11, FR-005]
---
# 런북 — 일시정지가 풀리지 않음 / "세션 없음"

**구성:** 대시보드는 `.control.json` 만 쓰고, 루프 CLI(`aidlc.py loop-*`)는 `.monitor/loop-status.json` 만 쓴다(D-04). 재개 조건은 `control.state == "running"` 이고 `control.seq > baseline_seq` (loop-cli.md §3.3). (구현: T-008)

## 판단
1. health `data.sources.control`: `unreadable` 이면 파일 자리에 디렉터리가 있거나 권한 문제 → 정상 파일로 복구될 때까지 재개 불가.
2. 대시보드 루프 제어 패널(`GET /api/v1/control`)의 `heartbeat_age_sec`:
   - 120 s 초과 → "세션 없음": `wait-resume` 을 부르던 Claude Code 세션이 닫혔다(QS-11, 감지 ≤ 2분). 재개 버튼을 눌러도 받을 쪽이 없다.
   - 120 s 이하 → 세션은 대기 중. 재개 요청이 반영되지 않는 경우다.
3. `remaining_pause_sec` 이 0 → 누적 상한(기본 7200 s = 2시간) 초과로 루프가 `pause_timeout` 으로 정상 종료됐다(exit 20, STM 무변경).

## 조치
- 세션 없음 / pause_timeout: 대시보드에서 재개(제어 파일을 running 으로) 후 Claude Code 에서 `/aidlc-run N` 을 새로 시작한다. 진행 중이던 Task 는 STM 이 그대로라 이어진다.
- 재개가 반영 안 됨: 재개 버튼을 한 번 더 눌러 `seq` 를 올린다. `.control.json` 이 깨졌다가 다시 만들어지면 `seq` 가 낮아져 CLI 가 무시할 수 있다(I-16, T-026) — 이 경우 루프를 끝내고 새로 시작한다.
- CLI 가 exit 2 를 내면(제어 파일 broken) 스킬은 경고 후 계속 진행한다 — 멈춰 있지 않다.

## 하지 않는 것
- `loop-status.json` 을 손으로 고치지 않는다(작성자는 CLI 하나, R-10).
- `.control.json` 을 에디터로 고치지 않는다 — 대시보드(또는 `POST /api/v1/control/resume`)로만.
