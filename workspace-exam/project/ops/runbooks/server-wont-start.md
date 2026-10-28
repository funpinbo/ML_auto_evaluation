---
doc: runbook
owner: ops
sources: [SCOPE-01 AC-12, ADR-001, D-32, R-09]
---
# 런북 — 서버가 시작되지 않음

**증상:** 런처가 "서버가 시작되지 않았습니다" 로 끝남(health 20 s 대기 실패), 또는 `python -m app` 이 바로 종료.

## 확인 순서
1. 콘솔 로그 마지막 줄을 본다 (`... ERROR ...` 또는 Python 오류 종류).
2. Python 버전: `python3 --version` (Windows: `py -3 --version` / `python --version`). 3.11 미만이면 설치 후 재시도.
3. 의존성: `monitor/.venv/bin/python -c "import fastapi, uvicorn"` (Windows: `monitor\.venv\Scripts\python`). 실패 → venv 삭제 후 런처 재실행(재설치).
4. 포트: `port must be ...` 오류 → `AIDLC_MONITOR_PORT`/`--port` 값이 1~65535 십진수(선행 0 없음)인지. `address already in use` → `port-in-use.md`.
5. 수동 기동으로 원인 분리:
   ```
   cd monitor/backend && ../.venv/bin/python -m app --port 8765
   curl -s http://127.0.0.1:8765/api/v1/health
   ```
6. health 가 **400 `BAD_HOST`** → 접속 주소의 포트가 서버 포트와 다르다(런처가 고른 포트와 `settings.port` 불일치, D-19). `127.0.0.1:<서버 포트>` 로 접속.
7. health 200 인데 화면이 비어 있음 → `data.dist == "missing"`: `cd monitor/frontend && npm ci && npm run build`.
8. health 200 + `meta.status = partial` 은 정상 기동이다. `data.sources` 를 보고 해당 런북으로.

## 하지 않는 것
- `~/.claude` 아래 파일을 고치거나 지우지 않는다(02 §11, 사람 승인 필요).
- 바인딩 주소를 `0.0.0.0` 으로 바꾸지 않는다(옵션 없음, N-01).
