---
doc: runbook
owner: ops
sources: [ADR-001 §4, SCOPE-01, D-32]
---
# 런북 — 포트 사용 중

**증상:** `address already in use` / 런처가 다음 포트로 넘어감 / 브라우저가 다른 앱을 연다.

## 판단
1. 기본 포트에 무엇이 떠 있는지 health 로 확인:
   ```
   curl -s -m 2 http://127.0.0.1:8765/api/v1/health
   ```
   - `"app":"aidlc-monitor"` 가 있으면 이미 실행 중인 대시보드다 → 그 창/탭을 쓰면 된다(런처도 브라우저만 열고 끝냄, ADR-001 §4).
   - 400 `BAD_HOST` 를 주면 다른 포트 설정으로 뜬 대시보드일 수 있다. 응답 없음·다른 본문이면 다른 프로그램이다.
2. 점유 프로세스 확인(정보용):
   - Linux/macOS: `lsof -nP -iTCP:8765 -sTCP:LISTEN` 또는 `ss -ltnp | grep 8765`
   - Windows: `netstat -ano | findstr :8765` → `tasklist /FI "PID eq <pid>"`

## 조치
- 남은 대시보드 프로세스면 그 콘솔에서 Ctrl+C (또는 PID 종료).
- 다른 프로그램이면 다른 포트로 실행: `AIDLC_MONITOR_PORT=8770 bash run.sh` 또는 `python -m app --port 8770`. 브라우저 주소도 같은 포트(`http://127.0.0.1:8770/`)여야 한다.
- 포트 `0`(임의 할당)은 허용되지 않는다 — Host 가드가 실제 포트를 알 수 없다(D-19).
