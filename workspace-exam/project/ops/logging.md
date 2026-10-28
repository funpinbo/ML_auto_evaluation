---
doc: ops-logging
owner: ops
sources: [user/02 §7, 20 §6, ADR-011 §8, contracts/README §2]
---
# 로그 규칙

구현: `monitor/backend/app/logging_config.py` 의 `setup_logging()` (`python -m app` / `uvicorn app.main:app` 모두 `app.main.setup_logging()` 을 거쳐 호출).

## 1. 포맷
- stderr 콘솔 텍스트, 한 줄: `%(asctime)s %(levelname)s %(message)s` → `2026-10-23 18:16:38,234 WARNING tasks 파일 형식 오류 2건`
- 메시지 안 줄바꿈은 공백으로 바꾼다(한 레코드 = 한 줄, 위조 줄 방지).
- 예외는 traceback 을 찍지 않고 끝에 `(ExceptionType)` 만 붙인다 — traceback 에는 설치 경로(사용자 홈)가 들어간다.

## 2. 레벨
| 레벨 | 언제 | 예 |
|------|------|----|
| ERROR | 패널을 못 그림 (패널 예외 격리, 처리되지 않은 예외) | `pipeline 패널 오류: KeyError` |
| WARNING | 파일 누락·형식 오류로 일부 생략. **파일 종류와 건수만** | `tasks 파일 형식 오류 2건` |
| INFO | 시작·종료, 데이터 소스 해석 결과(찾음/못 찾음만) | `Uvicorn running on http://127.0.0.1:8765` |

## 3. 금지 (호출하는 쪽이 지킨다 — 1차 방어)
- Claude 대화 본문, tool 입력·출력, 파일 내용
- 파일 경로(절대·상대·`~`), 디렉터리 이름(`transcript_dir_name` 포함), 요청 경로·쿼리 문자열, 요청 헤더 값(Host 등)
- sessionId, uuid, requestId, message id
- 토큰·키·인증 정보
- 예외 메시지 원문(`str(exc)`) — 경로가 들어 있다. `type(exc).__name__` 만 쓴다.

## 4. 포매터의 2차 방어
`SafeFormatter` 가 메시지에서 아래 모양을 `<redacted>` 로 바꾼다. 규칙 위반을 가리는 안전망일 뿐이므로 1차 규칙을 대신하지 않는다.
POSIX 절대 경로(구분자 2개 이상), Windows 드라이브·UNC 경로, `~/` 경로, UUID, `req_`/`msg_`/`toolu_` ID, `sk-` 키, `Bearer` 토큰. `http://127.0.0.1:8765` 같은 URL 은 가리지 않는다.

## 5. uvicorn access log — 끔 (결정)
- 요청 줄(`"GET /api/v1/...?... HTTP/1.1" 200`)에 경로·쿼리 문자열이 그대로 들어가므로 끈다. `__main__` 의 `access_log=False` + `setup_logging()` 이 `uvicorn.access` 로거를 disabled 로 만든다(`uvicorn app.main:app` 직접 실행 경로 포함).
- 대안(경로를 지운 access 로그)은 지금 필요 없다. 요청 단위 관측이 필요해지면 상태 코드·소요 시간만 남기는 방식으로 따로 만든다.
- `uvicorn.error`(시작·종료 안내)는 root 핸들러로 보낸다.

## 6. 검증
`cd monitor/backend && python -m pytest tests/ops` — 포맷, 멱등, access log 차단, 경로·ID·키 가림, traceback 미출력, 앱 전 엔드포인트 호출 시 qa 표식·경로 0건.
