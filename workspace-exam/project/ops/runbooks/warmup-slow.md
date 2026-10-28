---
doc: runbook
owner: ops
sources: [ADR-002 §6, NFR-001, I-11]
---
# 런북 — 사용량 데우기가 느림

**구성:** 서버 시작 시 백그라운드 스레드 1개가 `~/.claude/projects/<프로젝트>/**/*.jsonl` 을 최근 파일부터 읽는다(ADR-002 §6). 진행률은 health `data.usage_warming` 과 사용량 패널 `meta.status = warming`. (구현: T-010 — 그 전에는 항상 `not_started`)

## 판단
1. `curl -s http://127.0.0.1:8765/api/v1/health` 의 `usage_warming.progress` 를 몇 초 간격으로 본다.
   - 증가 중 → 정상. 최근 파일 우선이라 "오늘/현재 5시간" 값이 먼저 완성된다.
   - 멈춤 / `unknown` → 수집기 오류. 콘솔의 WARNING/ERROR 줄(파일 종류·건수만)을 본다.
2. `data.sources.claude_projects` 가 `missing` 이면 읽을 기록이 없다 → `CLAUDE_HOME` 값 확인.
3. 데이터 양: 30일 JSONL 이 수백 MB 면 첫 데우기는 수 초~수십 초가 걸릴 수 있다(30 EDA 4.4 ms/MB 기준, I-11 실측 예정).

## 조치
- 기다린다. 데우기 중에도 다른 패널은 그대로 동작한다(NFR-002).
- 백신·동기화 프로그램이 `~/.claude/projects` 를 스캔 중이면 끝난 뒤 재시작.
- 기록 파일을 지우거나 옮기지 않는다(`~/.claude` 수정은 02 §11 — 사람 승인 필요).
