---
doc: ops-index
owner: ops
sources: [20 §6, CON-05, NFR-002, R-09, ADR-001, ADR-003, ADR-004]
---
# Ops 문서 색인

| 문서 | 내용 |
|------|------|
| `logging.md` | 콘솔 로그 포맷·레벨·금지 항목, uvicorn access log 결정 |
| `runbooks/server-wont-start.md` | 서버가 안 뜸 / 런처 health 대기 실패 |
| `runbooks/port-in-use.md` | 포트 사용 중 |
| `runbooks/statusline-not-running.md` | 한도 % 가 안 나옴 (status line 스냅샷 없음·오래됨) |
| `runbooks/pause-not-releasing.md` | 일시정지가 풀리지 않음 / "세션 없음" |
| `runbooks/warmup-slow.md` | 사용량 데우기가 느림 |

## 1. 로컬 실행 환경 전제 (infra 인수)
- 바인딩은 `127.0.0.1` 고정(옵션 없음, N-01). 포트 기본 8765, 변경은 `AIDLC_MONITOR_PORT` 또는 `python -m app --port N`(우선). 0·선행 0·범위 밖 거부 (D-32).
- Host 가드는 `127.0.0.1:<port>`·`localhost:<port>` 만 통과 → 다른 포트·이름으로 열면 400 `BAD_HOST` (D-19).
- Python 3.11+. Windows 는 Hook·statusLine 이 bash(Git Bash) 를 전제한다 (R-09). bash 가 없으면 statusLine 이 돌지 않고 한도 패널은 폴백으로 표시된다.
- 경로 입력은 환경 변수 `AIDLC_ROOT`(기본: 저장소 루트), `CLAUDE_HOME`(기본: `~/.claude`) 뿐이다 (D-16).

## 2. 상태 확인 — `GET /api/v1/health`
응답은 공통 봉투 `{data, meta}`. 경로·파일 이름은 담지 않는다.

```
curl -s http://127.0.0.1:8765/api/v1/health
```

| 필드 | 값 | 의미 |
|------|----|------|
| `data.status` | `ok` | 프로세스 생존 (응답이 오면 항상 ok) |
| `data.app` | `aidlc-monitor` | 런처 중복 실행 판정용 식별자 (값 고정, ADR-001 §4) |
| `data.version` | `0.1.0` 등 | 앱 버전 |
| `data.sources.workspace` | ok / missing / unreadable | `<AIDLC_ROOT>/workspace/memory` |
| `data.sources.claude_projects` | ok / missing / unreadable | `<CLAUDE_HOME>/projects` |
| `data.sources.statusline` | ok / missing / stale / unreadable | `workspace/memory/.monitor/claude-status.json` (수정 시각 10분 초과 = stale) |
| `data.sources.control` | ok / missing / unreadable | `workspace/memory/.control.json` (missing 은 정상, 경고 없음) |
| `data.dist` | ok / missing | 프론트 `dist/index.html` (ADR-005 §3) |
| `data.usage_warming` | `{state: not_started/warming/done/unknown, progress: 0~1/null}` | 사용량 캐시 데우기 (T-010 전에는 not_started) |
| `meta.status` | ok / partial / warming | 경고가 있으면 partial, 경고 없이 데우는 중이면 warming |

소스 판정은 `stat` 만 쓴다(파일을 열지 않음, 쓰기 없음). 소스가 없어도 HTTP 200 이다 (NFR-002).

## 3. 변경·롤백
설정은 환경 변수·인자뿐이고 앱이 쓰는 파일은 `.control.json` 하나다. 롤백 = 프로세스 종료 후 이전 커밋으로 되돌리고 다시 실행.
