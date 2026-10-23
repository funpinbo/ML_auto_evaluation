---
doc: privacy-policy-checklist
layer: project
owner: security
sources: [00 Q2/C2, 20 §4·§5, ADR-002, ADR-003, ADR-011 §4·§5·§9, contracts/README §2·§3, NFR-003, CON-07, QS-05·06·07, LTM D-02·D-08·D-13·D-14·D-18·D-19]
status: draft
---
# 개인정보·접근 범위·Host/Origin 정책 (리뷰 체크리스트)

리뷰어(security, qa)는 아래 P-항목을 하나씩 실제 테스트·grep·diff 로 확인하고 결과를 STM §7 에 쓴다. 구현은 backend 소유(`privacy_filter.py` 등), 이 문서는 기준이다.
실행하지 않은 항목은 통과로 쓰지 않는다. 불확실하면 FAIL.
체크리스트 ID(P-/N-/W-/D-/T-)와 그 하위 테스트 케이스 ID(N-02 의 H-xx, N-04 의 C-xx, §5.1·§5.2)는 이 문서에서만 정의한다. 다른 문서는 ID 를 참조만 한다.

## 1. 허용 필드 화이트리스트 (JSONL → 메모리)
| 허용 필드 | 용도 | 비고 |
|-----------|------|------|
| `timestamp` | 시간 버킷 | |
| `requestId` | 중복 제거 키 | 메모리 내부 전용, 응답·로그 노출 금지 |
| `message.model` | 모델별 집계 | |
| `message.usage.input_tokens` | 토큰 | 숫자 |
| `message.usage.output_tokens` | 토큰 | 숫자 |
| `message.usage.cache_creation_input_tokens` | 토큰 | 숫자 |
| `message.usage.cache_read_input_tokens` | 토큰 | 숫자 |
| `isSidechain` | 서브에이전트 구분 | bool |
| `cwd` | **디렉터리 해석 폴백 때만**(ADR-002 §1.3) | 경로 비교 후 즉시 폐기, 저장·응답·로그 금지 |

이 외 모든 키(특히 `message.content`, `content`, `text`, `tool_use`, `tool_result`, `sessionId`, `uuid`, `parentUuid`, `gitBranch`, `userType`, `version`)는 접근하지 않는다. 필드를 추가하려면 이 표 갱신 + security 리뷰가 선행한다.

- [ ] **P-01** 파서가 새 dataclass(고정 필드)에 위 표의 필드만 복사한다. 원본 dict 를 보관·반환·로그하지 않는다(복사 직후 폐기).
- [ ] **P-02** 코드에서 `content`, `text`, `tool_result` 등 본문 키에 접근하는 식(`["content"]`, `.get("content")`)이 0건이다 (`grep -rn "content" monitor/backend/app` 결과를 검토).
- [ ] **P-03** 허용 필드 복사가 보안 경계다. 본문 안에 `"usage":` 문자열이 들어 있는 줄이 통과해도 본문이 결과에 나타나지 않는다(테스트로 확인).
- [ ] **P-04** `message.usage` 가 dict 가 아니거나 숫자 필드가 숫자가 아니면 그 줄을 버리고 건수만 센다.
- [ ] **P-05** `cwd` 는 폴백 해석 경로에서만 읽고, 비교 후 폐기한다. 집계 구조·캐시·응답·로그에 남지 않는다.

## 2. `"usage":` 사전 필터
- [ ] **P-06** 줄 단위 읽기에서 원문 바이트에 `b'"usage":'` 가 없으면 `json.loads` 호출 전에 폐기한다(파싱 전 버림이 코드 순서로 확인됨).
- [ ] **P-07** 잘린 마지막 줄(개행 없음)은 처리하지 않고 다음 주기로 미룬다(ADR-002 §2). 잘린 줄 조각이 로그에 남지 않는다.
- [ ] **P-08** 사전 필터는 성능 목적, 허용 필드 복사가 보안 목적임을 코드 주석/테스트 이름에서 구분한다(P-03 과 짝).

## 3. 응답·로그·캐시 금지 항목
금지 대상: 대화 본문, 파일 경로(홈 디렉터리 포함 전체·일부), `transcript_dir_name` 원문·일부, sessionId·requestId 원문, `cwd`, `~/.claude/settings.json` 내용(statusLine 외 키는 물론 statusLine 명령 문자열도), 예외에 딸린 줄 내용.
범위: REST 응답 본문, SSE 페이로드, 에러 메시지(`INTERNAL_ERROR` 포함), stdout/stderr 로그, 프로세스 메모리 캐시(집계 버킷), 디스크 파일.

- [ ] **P-09** 모든 REST 응답·SSE 이벤트가 응답 모델(Pydantic allow-list)로만 만들어지며, 합성 fixture 의 표식 문자열(본문 표식, 경로 표식, requestId 표식, session 표식)이 응답 어디에도 나타나지 않는다.
- [ ] **P-10** 로그(캡처한 stdout/stderr/logging)에도 같은 표식이 없다. 파싱 실패 로그는 건수·예외 종류만 포함한다. `INTERNAL_ERROR` 메시지에 경로·내용이 없다.
- [ ] **P-11** 메모리 집계 구조(`(hour, model, is_sidechain) → {responses, 토큰 4종}`)에 문자열 본문·경로가 없다. requestId 는 중복 제거 dict 키로만 존재하고 30일 후 정리된다. 테스트에서 집계 객체를 순회해 표식 부재를 확인한다.
- [ ] **P-12** 디스크 쓰기는 `workspace/memory/.control.json` 1개뿐이다(§6). 캐시·집계를 디스크에 영속하지 않는다(SQLite·pickle·임시 파일 0).

## 4. `~/.claude` 접근 범위
허용 읽기:
1. `~/.claude/projects/<enc>/**/*.jsonl` (이 저장소에 해당하는 `<enc>` 하나, 서브에이전트 `subagents/agent-*.jsonl` 포함)
2. `~/.claude/settings.json` 의 `statusLine` 키 (체이닝용, `statusline.py` 에서만)
3. 폴백 해석 시 `~/.claude/projects/*` 의 디렉터리 목록과 최근 30일 jsonl 의 usage 줄(사전 필터 통과분의 `cwd` 만)

그 외 `~/.claude` 하위(인증·자격 증명·`.credentials*`, `history`, `todos`, `shell-snapshots`, `statsig`, 기타 설정)는 **열지 않는다**. 쓰기는 `~/.claude` 에 대해 0.

- [ ] **P-21** `open`/`Path.read_*`/`glob` 등 `~/.claude` 접근 지점을 전수 grep 하고 각각 위 1~3 중 하나임을 확인한다 (경로 상수 정의 위치 1곳).
- [ ] **P-22** `~/.claude` 에 대한 쓰기·삭제·rename 이 0건이다.
- [ ] **P-23** `settings.json` 에서 `statusLine.command` 외 키를 꺼내지 않고, 파일 전체 내용·명령 문자열을 로그·응답·스냅샷에 넣지 않는다.
- [ ] **P-24** 체이닝은 `aidlc/hooks/statusline` 포함 명령을 건너뛰고(재귀 방지) timeout 2 s 이며 요청에서 받은 값을 셸에 넘기지 않는다.
- [ ] **P-29** JSONL 탐색이 `projects/<enc>` 아래로만 제한되고, 각 파일의 `resolve()` 결과가 해당 `<enc>` 디렉터리 하위가 아니면(symlink 이탈) 열지 않는다. symlink fixture 로 확인한다.
- [ ] **P-30** 인증 파일은 리뷰·테스트 중에도 열지 않는다(02 §8). 테스트는 `tmp_path` 에 만든 합성 `~/.claude`(HOME 치환)만 쓴다.

### 4.1 `transcript_dir_name` 재검증 (D-13, contracts/README §2·§3)
정규식: `^(?!\.{1,2}(?![\s\S]))[A-Za-z0-9._-]{1,255}(?![\s\S])` — `.`/`..`, 구분자, `:`, 제어문자, 개행 거부. 끝 앵커는 `$` 가 아니라 `(?![\s\S])` (Python `$` 는 끝 개행 앞에서 매치).

- [ ] **P-25** reader 가 스키마 검증 여부와 무관하게 위 정규식으로 **재검증**한다(`re.search` 가 아니라 `re.fullmatch`/`match` 로 동일 의미가 되는지, 패턴 문자열이 계약과 일치하는지 diff).
- [ ] **P-26** 음성 케이스가 테스트에 있다: `..`, `.`, `a/b`, `a\b`, `/abs`, `C:x`, 빈 문자열, 256자, 끝에 `\n`, NUL/제어문자, 앞뒤 공백 — 모두 거부되어 폴백으로 진행.
- [ ] **P-27** 검증 통과 후 `(~/.claude/projects/<name>).resolve()` 의 `parent` 가 `~/.claude/projects` 의 `resolve()` 와 정확히 같다(직속 하위). 아니면 힌트 무시·폴백.
- [ ] **P-28** symlink 케이스: `projects/<name>` 이 밖을 가리키는 symlink 이면 P-27 에서 거부된다. 실패 로그는 값 없이 코드만 포함하고(경로·이름 미포함), API 응답·SSE·로그 어디에도 `transcript_dir_name` 이 없다.
- [ ] **P-31** `claude-status.json` 은 스키마 `additionalProperties: false` 이며 `transcript_path` 원문·`cwd`·session_id 원문이 없고 `session_hash` 만 있다. 보안 관련 필드를 추가하면 이 목록(contracts/README §3)과 이 문서를 갱신하고 security 리뷰를 받는다.

## 5. Host / Origin / 바인딩 정책 (ADR-011 §4~§6, QS-05)
| 항목 | 규칙 | 오류 |
|------|------|------|
| 바인딩 | `127.0.0.1` 고정. 주소를 바꾸는 CLI 옵션·환경변수·설정 0개 | - |
| Host | `Host` 헤더가 **정확히 1개**이고, 값 `strip()`·소문자화 후 `127.0.0.1:<port>` 또는 `localhost:<port>` 와 **정확 일치**할 때만 통과(`<port>` = `settings.port`, D-19). 접두·접미 일치, 포트 생략, 다른 포트, 선행 0 포트, userinfo, 추가 세그먼트, `[::1]`, 끝 점, 빈 값·누락·중복은 전부 거부. 가드는 자체 ASGI `HostGuardMiddleware`(가장 바깥, D-18)이며 GET·POST·SSE·정적 dist 전부에 적용. 거부 메시지에 받은 Host 값을 넣지 않는다 | 400 `BAD_HOST` |
| POST Content-Type | `Content-Type` 의 미디어 타입(첫 `;` 앞, `strip()`·소문자화)이 정확히 `application/json` 일 때만 통과. 매개변수 허용(`; charset=utf-8`). 누락·form 계열·`text/plain`·접두 함정(`application/jsonx`, `application/json-patch+json`)은 `.control.json` 을 건드리기 전, 본문 검증(422)보다 먼저 거부. 415 는 쓰지 않는다 | 403 `FORBIDDEN_ORIGIN` |
| POST Origin | 있으면 `http://127.0.0.1:<port>` 또는 `http://localhost:<port>` 와 정확히 일치, 불일치 거부 | 403 `FORBIDDEN_ORIGIN` |
| CORS | 미들웨어 없음, `Access-Control-*` 응답 헤더 0, OPTIONS preflight 에 허용 응답 없음 | - |
| 보안 헤더 | `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, CSP `default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'` | - |
| 오류 본문 | `{"error":{"code","message"}}`, message 에 경로·입력 원문(받은 Host·Origin·Content-Type 값 포함) 미포함 | - |

참고: 비-JSON Content-Type 을 `FORBIDDEN_ORIGIN` 403 으로 응답하는 것은 ADR-011 §5 확정안이다(D-14). 20 §QS-05 가 "Origin 불일치 또는 Content-Type 이 JSON 아님 → 403" 으로 명시하고 20 §5 에러 코드 목록(닫힌 집합, ADR-011 §9 와 동일)에 415 가 없다. 따라서 구현이 다른 코드(예: 415)를 쓰면 계약 위반으로 FAIL 이다.
Host 헤더 개수 판정은 서버 파서(h11/uvicorn)의 동작에 맡기지 않고 가드가 ASGI `scope["headers"]` 에서 `host` 항목 수를 세어 직접 한다(LTM 패턴). 테스트는 TestClient 의 Host 를 직접 덮어쓰거나 ASGI scope 를 직접 만들어 넣는다(ADR-011 §4 테스트 영향: `base_url="http://127.0.0.1:<fixture port>"`).

### 5.1 N-02 Host 케이스 표 (T-005 테스트로 그대로 옮김)
표기: `<port>` = fixture 의 `settings.port`(예: 8765), `<other>` = `<port>` 와 다른 포트. "대상" 이 `*` 인 행은 아래 4개 대상 각각에 대해 실행한다 — `GET /api/v1/health`, `POST /api/v1/control/pause`(정상 JSON 본문·허용 Origin), `GET /api/v1/events`(SSE), `GET /`(정적 dist index). 거부 행은 모두 응답 본문 `error.code == "BAD_HOST"`, `error.message` 에 요청 Host 값(부분 문자열 포함)이 없고, POST 의 경우 `.control.json` 이 변하지 않는다(해시 비교).

| case | 요청 Host 헤더 | 대상 | 기대 |
|------|----------------|------|------|
| H-01 | `127.0.0.1:<port>` | * | 통과 (400 아님) |
| H-02 | `localhost:<port>` | * | 통과 |
| H-03 | `LOCALHOST:<port>` | * | 통과 (소문자화) |
| H-04 | `127.0.0.1:1` (포트 불일치) | * | 400 `BAD_HOST` |
| H-05 | `localhost:<other>` | * | 400 `BAD_HOST` |
| H-06 | `127.0.0.1` (포트 생략) | * | 400 `BAD_HOST` |
| H-07 | `localhost` (포트 생략) | * | 400 `BAD_HOST` |
| H-08 | `[::1]:<port>` | * | 400 `BAD_HOST` |
| H-09 | `localhost.:<port>` (끝 점) | * | 400 `BAD_HOST` |
| H-10 | `127.0.0.1:0<port>` (선행 0, 예: `127.0.0.1:08765`) | * | 400 `BAD_HOST` |
| H-11 | `user@127.0.0.1:<port>` (userinfo) | * | 400 `BAD_HOST` |
| H-12 | `127.0.0.1:<port>:x` (추가 세그먼트) | * | 400 `BAD_HOST` |
| H-13 | `localhost.evil.com:<port>` (접두 일치) | * | 400 `BAD_HOST` |
| H-14 | `evil.example` | * | 400 `BAD_HOST` |
| H-15 | `192.168.0.10:<port>` | * | 400 `BAD_HOST` |
| H-16 | `""` (빈 값) | * | 400 `BAD_HOST` |
| H-17 | Host 헤더 없음 (scope `headers` 에 `host` 0개) | * | 400 `BAD_HOST` |
| H-18 | Host 헤더 2개: `127.0.0.1:<port>` + `127.0.0.1:<port>` (같은 값 중복) | * | 400 `BAD_HOST` |
| H-19 | Host 헤더 2개: `127.0.0.1:<port>` + `evil.example` | * | 400 `BAD_HOST` |
| H-20 | `testserver` (TestClient 기본값) | `GET /api/v1/health` | 400 `BAD_HOST` |
| H-21 | `evil.example` + POST 의 Origin·Content-Type 도 잘못됨 | `POST /api/v1/control/pause` | 400 `BAD_HOST` (Host 가드가 가장 바깥이라 403 보다 먼저) |
| H-22 | `evil.example`, 존재하지 않는 경로 | `GET /api/v1/nope`, `GET /assets/nope.js` | 400 `BAD_HOST` (404 아님) |

### 5.2 N-04 Content-Type 케이스 표 (T-005 테스트로 그대로 옮김)
공통: Host `127.0.0.1:<port>`, Origin `http://127.0.0.1:<port>`, 대상 `POST /api/v1/control/pause` 와 `POST /api/v1/control/resume` 각각, 본문은 해당 엔드포인트의 유효한 JSON 바이트(C-10 제외). 거부 행은 모두 `error.code == "FORBIDDEN_ORIGIN"`, 상태 코드가 415·422 가 아니며, `.control.json` 이 존재 여부·바이트 모두 요청 전과 같다.

| case | 요청 `Content-Type` | 기대 |
|------|---------------------|------|
| C-01 | `application/json` | 통과 (403 아님) |
| C-02 | `application/json; charset=utf-8` | 통과 |
| C-03 | `Application/JSON` | 통과 (미디어 타입 소문자화) |
| C-04 | 헤더 없음 | 403 `FORBIDDEN_ORIGIN` |
| C-05 | `application/x-www-form-urlencoded` | 403 `FORBIDDEN_ORIGIN` |
| C-06 | `multipart/form-data; boundary=x` | 403 `FORBIDDEN_ORIGIN` |
| C-07 | `text/plain` | 403 `FORBIDDEN_ORIGIN` |
| C-08 | `application/jsonx` (접두 함정) | 403 `FORBIDDEN_ORIGIN` |
| C-09 | `application/json-patch+json` (접두 함정) | 403 `FORBIDDEN_ORIGIN` |
| C-10 | `text/plain` + 본문이 JSON 이 아닌 바이트 | 403 `FORBIDDEN_ORIGIN` (422 `VALIDATION_ERROR` 아님 — Content-Type 검사가 본문 검증보다 먼저) |
| C-11 | `""` (빈 값) | 403 `FORBIDDEN_ORIGIN` |

- [ ] **N-01** 서버 기동 코드가 `host="127.0.0.1"` 리터럴이고, `--host`/`HOST` 환경변수/설정 파일로 변경하는 경로가 없다(grep `0.0.0.0`, `host=`, `argparse` 옵션 목록).
- [ ] **N-02** §5.1 표 H-01~H-22 가 전부 자동 테스트로 있고 통과한다(`*` 행은 4개 대상 전부). 포트 검사·Host 개수 검사는 **필수**다. 추가로 코드 확인: `TrustedHostMiddleware` import/사용 0건, 허용 집합이 `settings.port` 에서 만들어짐(포트 리터럴 중복 0), `HostGuardMiddleware` 가 앱의 가장 바깥 미들웨어이고 http·SSE·정적 마운트 경로를 가리지 않고 적용됨, 거부 응답 생성에 요청 Host 값이 쓰이지 않음.
- [ ] **N-03** 테스트: POST 의 Origin `http://evil.example`, `null`, `http://127.0.0.1:<다른포트>`, `https://127.0.0.1:<port>` 가 403 `FORBIDDEN_ORIGIN`. Origin 없음 + JSON 은 통과(비브라우저 허용, 잔여 위험으로 수용).
- [ ] **N-04** §5.2 표 C-01~C-11 이 전부 자동 테스트로 있고 통과한다(pause·resume 각각). 거부는 항상 403 `FORBIDDEN_ORIGIN` 이며 415 를 반환하는 경로가 코드에 0건(grep `415`, `HTTP_415`, `UNSUPPORTED_MEDIA_TYPE`). 미디어 타입 비교가 `startswith`/`in` 이 아니라 정확 일치다(diff 확인).
- [ ] **N-05** 응답 헤더에 `Access-Control-Allow-Origin` 등 CORS 헤더가 없다(허용 Origin 요청, 타 Origin 요청, OPTIONS 모두).
- [ ] **N-06** 보안 헤더 3종이 모든 응답(정적 dist 포함)에 있다.
- [ ] **N-07** 입력은 enum/범위 Pydantic 모델이며 요청에서 파일 경로를 받는 파라미터가 없다. 422 는 `VALIDATION_ERROR` 로 변환되고 입력 원문을 되돌려주지 않는다.

## 6. 쓰기 경로 (QS-07)
- [ ] **W-01** 대시보드 프로세스의 파일 쓰기는 `workspace/memory/.control.json` 하나뿐이다 (`open(…, "w"|"a"|"x")`, `write_text`, `os.replace`, `shutil`, `mkdir`, `touch` 의 대상 전수 확인).
- [ ] **W-02** 쓰기는 같은 디렉터리 임시 파일 → `os.replace`, 경로는 상수이며 요청 값이 경로 구성에 쓰이지 않는다.
- [ ] **W-03** `loop-status.json`, `claude-status.json`, `memory/*.md`, `tasks.md`, `.claude/` 를 backend 가 쓰지 않는다.
- [ ] **W-04** `.gitignore` 에 `workspace/memory/.control.json`, `workspace/memory/.monitor/` 가 있다 (`git check-ignore --no-index -v`).

## 7. 본문 비노출 테스트 기준 (qa 에 제공)
합성 fixture 규칙:
- 실제 `~/.claude` 기록을 쓰지 않는다. `tmp_path` 에 가짜 HOME/`projects/<enc>/` 구성 (02 §5).
- 줄마다 고유 **표식 문자열**을 넣는다: 본문(`message.content` 안), 경로(`cwd`, 별도 경로 필드), sessionId, uuid, 도구 입력/출력, 그리고 허용 필드가 아닌 임의 키. 본문 안에 `"usage":` 리터럴이 든 줄도 포함.
- 케이스: usage 없는 줄, 중복 requestId(last-wins), requestId 없는 줄, 깨진 JSON, 잘린 마지막 줄, `subagents/agent-*.jsonl`, symlink 이탈, 거대 줄.

통과 기준 (전부 만족):
- [ ] **T-01** 표식 문자열이 모든 REST 응답 본문·헤더, SSE 프레임에 0회 (엔드포인트 전수: usage, health, status 계열 포함).
- [ ] **T-02** 표식 문자열이 캡처한 로그(stdout/stderr/logging, WARN 포함)에 0회.
- [ ] **T-03** 집계 구조를 재귀 순회(dict 키·값, dataclass 필드)해도 표식이 0회. 문자열 값은 모델명과 `warnings` 류로 한정.
- [ ] **T-04** 디스크에서 테스트 전후 diff 결과 새로 생긴 파일이 `.control.json`(해당 시)뿐이다.
- [ ] **T-05** 사전 필터가 usage 없는 줄에서 `json.loads` 를 호출하지 않는다(호출 횟수 모킹/카운트 또는 파서 spy).
- [ ] **T-06** `message.content` 접근 0: content 를 접근하면 예외를 던지는 객체/속성 trap 을 쓰거나 코드 grep 으로 보강한다.
- [ ] **T-07** `transcript_dir_name` 음성 케이스(§4.1 P-26)와 symlink 케이스가 자동 테스트에 있다.
- [ ] **T-08** 예외 경로: 깨진 JSON/형식 오류 줄이 로그에 줄 내용 일부(예외 메시지의 `char N` 외 원문)를 남기지 않는다.

## 8. 의존성·비밀값 점검 (02 §8)
- [ ] **D-01** `pip-audit -r monitor/backend/requirements.txt` High 이상 0 (실행 결과 첨부, 미실행이면 미통과로 기록).
- [ ] **D-02** `cd monitor/frontend && npm audit` High 이상 0 (동일).
- [ ] **D-03** 비밀값 하드코딩 0 (토큰·키·자격 증명 패턴 grep, `.env` 커밋 없음).
- [ ] **D-04** 새 의존성은 ADR-006/007 범위 안이거나 ADR 갱신이 있다.

## 9. 보존·마스킹 요약
| 데이터 | 처리 | 보존 |
|--------|------|------|
| JSONL 허용 필드 | 프로세스 메모리 집계 | 프로세스 수명, 30일 초과 정리, 디스크 영속 없음 |
| requestId | 중복 제거 키 | 메모리, 30일 정리, 외부 노출 없음 |
| `claude-status.json` | 허용 필드만, session_id 는 해시 12자 | 덮어쓰기, git 무시 |
| `.control.json` | 일시정지 요청 상태만 | 덮어쓰기, git 무시 |
| 로그 | 건수·코드·예외 종류만 | 콘솔 |
