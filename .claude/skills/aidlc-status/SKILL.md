---
name: aidlc-status
description: AI-DLC 진행 상태(문서 Gate, Plan/Task/LTM/STM, 미처리 cascade)를 요약한다.
---
# /aidlc-status — 상태 확인

1. `python3 aidlc/scripts/aidlc.py check user` 와 `python3 aidlc/scripts/aidlc.py check project` 의 마지막 GATE 줄만 모은다.
2. `python3 aidlc/scripts/aidlc.py status` 를 실행한다.
3. `workspace/teams/` 의 팀 목록을 확인한다.
4. 아래 형식으로 보고하고, 현재 위치에 맞는 다음 명령을 하나 제안한다:

| 단계 | 상태 |
|------|------|
| 0 init | workspace 존재 여부 |
| 1 interpret | user gate / 00 해석서 GO·HOLD |
| 2 analyze | 10·20·30 존재 여부 |
| 3 teams | 팀 목록 |
| 4 plan | Phase 수 / Task 수 |
| 5 run | current_phase, Phase 별 진행률, STM 상태, 미처리 cascade |
