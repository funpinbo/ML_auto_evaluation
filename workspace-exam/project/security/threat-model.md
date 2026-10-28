---
doc: threat-model
layer: project
owner: security
sources: [00 Q2/C2, 20 §4, ADR-002, ADR-003, ADR-011, contracts/README §2·§3, NFR-003, QS-05·06·07, LTM D-02·D-08·D-13]
status: draft
---
# 위협 모델 (STRIDE) — AI-DLC Monitor

범위: 로컬 대시보드(FastAPI, 127.0.0.1) + statusline 스크립트 + `.control.json` 쓰기. 실제 공격 코드는 이 문서에 두지 않는다(개념 수준 기술).
검증 열의 ID 는 privacy.md 의 항목(P-/N-/W-/D-/T-)이다. 정책 상세(허용 필드, Host/Origin, 접근 범위)는 `privacy.md` 가 단일 기준이다. 이 문서는 "왜"와 "어떤 통제가 어떤 위협을 막는가"를 매핑한다.

## 1. 자산과 신뢰 경계
| ID | 자산 | 민감도 | 위치 |
|----|------|--------|------|
| A-1 | 대화 본문 (JSONL 의 `message.content` 등) | 높음 | `~/.claude/projects/<enc>/**/*.jsonl` (usage 줄과 같은 줄) |
| A-2 | Claude 인증 파일·settings 내 기타 키 | 높음 | `~/.claude/` (읽기 대상 아님) |
| A-3 | 파일 경로(홈·사용자명 포함), `transcript_dir_name`, sessionId/requestId 원문 | 중간 | JSONL, `claude-status.json` |
| A-4 | 루프 제어 상태 (`.control.json`) | 중간(무결성) | `workspace/memory/.control.json` |
| A-5 | 사용량 집계(토큰 수·모델명) | 낮음 | 프로세스 메모리 |

신뢰 경계: (1) 브라우저 ↔ backend (127.0.0.1 루프백), (2) backend ↔ `~/.claude` 읽기, (3) backend ↔ `workspace/memory/` 쓰기, (4) Claude Code ↔ statusline 스크립트(stdin), (5) 사용자 PC 의 다른 웹 페이지(비신뢰) ↔ 로컬 포트.

## 2. 위협 목록 (STRIDE)
위험도: 가능성·영향 H/M/L. 잔여 = 통제 적용 후.

### 2.1 LAN 접속 (외부 호스트가 대시보드에 접근)
| STRIDE | 위협 | 통제 | 잔여 | 검증 (privacy.md) |
|--------|------|------|------|-------------------|
| I (정보 노출) | 0.0.0.0 바인딩으로 같은 LAN 의 타 기기가 사용량·프로젝트 정보 조회 | 바인딩은 `127.0.0.1` 고정, 주소를 바꾸는 옵션·환경변수 0개(NFR-003) | L | N-01 |
| S/T | LAN 기기가 `POST /control/pause` 로 루프 조작 | 위와 동일(도달 불가) + Host/Origin 가드(깊은 방어) | L | N-01, N-03·N-04 |
| E | `run.py` 에 `--host` 류 옵션이 추가되어 노출 확대 | 옵션 부재를 리뷰 항목화, 구현 변경 시 security 리뷰 | L | N-01 |

### 2.2 DNS rebinding / CSRF (브라우저가 공격 경로)
| STRIDE | 위협 | 통제 | 잔여 | 검증 |
|--------|------|------|------|------|
| S/I | 공격자 도메인이 127.0.0.1 로 재바인딩되어 동일 출처 정책을 우회, 응답 읽기(같은 PC 의 다른 로컬 포트로 향한 Host 혼동 포함) | 자체 `HostGuardMiddleware`(가장 바깥, ADR-011 §4·D-18): Host 헤더 정확히 1개 + 소문자화 후 `127.0.0.1:<port>`/`localhost:<port>` 정확 일치(`<port>`=`settings.port`)가 아니면 400 `BAD_HOST`, GET·POST·SSE·정적 dist 전부. 케이스는 privacy.md §5.1 | L | N-02 |
| T/E | 다른 사이트의 form/fetch 가 `POST /control/pause|resume` 호출 | POST 는 미디어 타입이 정확히 `application/json`(누락·form 계열·접두 함정 거부, 쓰기 전), Origin 이 있으면 허용 출처와 일치해야 함, 아니면 403 `FORBIDDEN_ORIGIN`(415 아님, ADR-011 §5·D-14). 케이스는 privacy.md §5.2 | L | N-03·N-04 |
| I | CORS 설정 실수로 타 출처 응답 읽기 허용 | CORS 미들웨어 미사용, `Access-Control-*` 헤더 0 | L | N-05 |
| T | Origin 헤더 없는 비브라우저 클라이언트 POST | 루프백 도달 가능한 로컬 프로세스는 이미 같은 사용자 권한 → 수용(ADR-011: 토큰 인증 기각). 쓰기 대상이 `.control.json` 1개이고 Pydantic 검증된 값만 쓰므로 영향 제한 | L (수용) | N-03, N-07 |
| I/T | 응답 내용 스니핑·프레임 삽입 | `nosniff`, `Referrer-Policy: no-referrer`, CSP(`default-src 'self'` …) | L | N-06 |

### 2.3 대화 본문 노출 (NFR-003, Q2)
| STRIDE | 위협 | 통제 | 잔여 | 검증 |
|--------|------|------|------|------|
| I | usage 줄에 본문이 같이 있어 파싱 시 메모리·응답·로그·캐시로 유입 | `"usage":` 없는 줄은 파싱 전 폐기, 허용 필드만 새 dataclass 로 복사 후 원본 dict 즉시 폐기, `message.content` 접근 금지 | M | P-01~P-08 |
| I | 예외 메시지·로그에 줄 내용(json 파싱 오류의 원문 일부) 포함 | 파싱 실패는 건수만 WARN, 예외는 종류만 기록, `INTERNAL_ERROR` 메시지에 경로·내용 미포함 | M | P-09, P-10 |
| I | 응답/SSE 에 sessionId·requestId·경로 원문 포함, 중복 제거용 requestId dict 가 응답으로 새어나감 | requestId 는 메모리 내부 키로만 사용, 응답 모델에 필드 없음(스키마 allow-list) | M | P-09, P-11 |
| I | 테스트가 실제 `~/.claude` 기록을 사용해 본문이 CI 로그·fixture 로 유입 | 합성 fixture 만 사용, 실제 기록 금지(02 §5) | L | P-30·§7 |
| I | 폴백 해석에서 `cwd` 가 캐시·응답으로 유출 | `cwd` 는 폴백 때만 복사, 비교 후 폐기, 해석 결과는 디렉터리 선택에만 사용 | L | P-05, P-09 |
| I | 비교적 흔한 우회: 사전 필터가 있어도 본문 안에 `"usage":` 문자열이 들어 있는 줄은 통과 | 통과 후에도 허용 필드만 복사하므로 본문은 유입되지 않음(사전 필터는 성능 목적, 보안 경계는 allow-list 복사) | L | P-03 |

### 2.4 `~/.claude` 인증 파일 및 경로 이탈
| STRIDE | 위협 | 통제 | 잔여 | 검증 |
|--------|------|------|------|------|
| I | `~/.claude` 아래 인증·설정 파일을 읽거나 노출 | 읽기 허용은 `projects/<enc>/**/*.jsonl` 과 `settings.json` 의 `statusLine` 키뿐. 그 외 파일 open 금지, settings 의 다른 키는 로그·응답·캐시 금지 | M | P-21~P-24 |
| T/E | statusline 스냅샷의 `transcript_dir_name` 변조(`..`, 절대경로, 구분자)로 `~/.claude` 밖/타 디렉터리 읽기 | D-13 정규식 재검증 + `resolve()` 결과가 `~/.claude/projects/` 직속 하위인지 확인. 실패 시 힌트 무시·폴백, 값 없이 코드만 기록 | M | P-25~P-28 |
| T | `projects/` 아래 symlink 가 밖(예: `~/.claude` 의 인증 파일, 홈)을 가리킴 | `resolve()` 후 경계 검사(직속 하위), JSONL 탐색 시 symlink 로 경계를 벗어나는 파일은 열지 않음(`resolve()` 결과가 대상 디렉터리 하위가 아니면 건너뜀) | M | P-28, P-29 |
| I | 체이닝이 `settings.json` 전체를 읽어 로그/스냅샷에 기록 | `statusLine.command` 만 추출, 다른 키는 보지 않음, 명령 문자열 자체도 로그 금지 | L | P-23, P-24 |
| E | 체이닝 명령 실행(셸)이 임의 명령 실행 경로 | 명령은 사용자 본인의 기존 설정(사용자 권한), 재귀 방지·timeout 2 s. 신규 입력 아님 → 수용. 요청에서 받은 값은 절대 셸로 넘기지 않음 | L (수용) | P-30 |
| I | 스냅샷에 `transcript_path` 원문·`cwd`·session_id 원문 저장 | 스키마 `additionalProperties: false`, `session_hash`(sha256 앞 12자)만 | L | P-31 |

### 2.5 쓰기 경로와 무결성 / 가용성
| STRIDE | 위협 | 통제 | 잔여 | 검증 |
|--------|------|------|------|------|
| T/E | 대시보드가 다른 파일(`loop-status.json`, `claude-status.json`, memory/tasks 등)에 씀 | 쓰기 경로는 `workspace/memory/.control.json` 1개(QS-07), 파일당 쓰기 주체 1개 | L | W-01 |
| T | 요청에서 받은 경로·임의 문자열로 쓰기 대상 변경 | 요청에 파일 경로 파라미터 없음(ADR-011 §3), 입력은 enum/범위 Pydantic | L | N-07 |
| T | 쓰기 중 중단으로 제어 파일 깨짐 | 임시 파일 → `os.replace` 원자적 교체 | L | W-02 |
| D | 조작된 JSONL/스냅샷(거대 줄, 깨진 JSON)으로 서버 다운·메모리 폭주 | 파싱 실패는 건수만 기록하고 계속, 패널 단위 오류 격리(NFR-002), 30일 초과 파일 건너뜀, SSE 연결 상한 503 `TOO_MANY_STREAMS` | M | 백엔드 테스트(qa) |
| D | SSE 연결 고갈 | 연결 상한(D-12) | L | qa |
| R (부인) | 누가 일시정지/재개했는지 부인 | 단일 사용자 로컬 도구 → 범위 밖(수용). `.control.json` 에 요청 시각만 기록 | 수용 | - |

### 2.6 공급망·의존성
| STRIDE | 위협 | 통제 | 검증 |
|--------|------|------|------|
| T | 취약한 Python/npm 의존성 | `pip-audit -r monitor/backend/requirements.txt`, `cd monitor/frontend && npm audit` High 이상 0 (02 §8, P1 말·P2 말). 의존성 추가는 ADR-006·007 범위로 제한 | D-01·D-02 |
| T | 커밋된 `dist` 에 악성/비밀 포함 | `.build-meta.json` 신선도, 비밀값 하드코딩 0(grep) | D-03 |
| I | 런타임 파일이 git 에 올라감 | `.gitignore`: `workspace/memory/.control.json`, `workspace/memory/.monitor/` | W-04 |

## 3. 수용한 잔여 위험
1. 같은 사용자 권한의 로컬 프로세스가 Origin 없이 `POST /control/*` 를 호출하는 것 (인증 없음, 02 §6, ADR-011 대안 기각).
2. 사용자 본인 `settings.json` 의 statusLine 명령 실행(체이닝).
3. 단일 사용자 도구이므로 부인 방지·감사 로그 없음.

## 4. 보류·열린 항목
- 구현 전이므로 모든 통제는 "요구" 상태. 구현 후 리뷰에서 P-항목을 실제 테스트/grep 으로 확인해야 한다.
- 폴백 `cwd` 해석은 홈 디렉터리 경로를 일시적으로 메모리에 올린다. 비교 후 폐기를 코드 리뷰로 확인(P-05).
- Windows/macOS 에서의 symlink·대소문자 경로 비교는 리허설 시 재확인.
