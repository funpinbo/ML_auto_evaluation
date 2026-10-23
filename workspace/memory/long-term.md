---
rev: 3
last_merged_stm: 3
---
# Long-term Memory

> **계층 3.** 프로젝트 전체에서 재사용할 지식. STM 이 끝날 때마다(cascade 1/3) 정제되어 쌓인다.
> 규칙: 사실만 기록, 출처 STM 번호 표기(예: `(STM-0003)`), 중복 금지, 틀린 항목은 삭제하지 말고 ~~취소선~~ + 대체 항목 링크.
> 이 파일이 갱신되면(rev 증가) Hook 이 Task 갱신(cascade 2/3)을 요구한다.

## 1. 결정 사항 (Decisions)
| ID | 결정 | 근거 | 대안 | 출처 |
|----|------|------|------|------|
| D-01 | 단일 FastAPI 프로세스(127.0.0.1)가 /api/v1 REST·SSE 와 커밋된 Vue dist 를 함께 서빙, `run.py` 원클릭 실행 | 03 원칙 1, 가중 점수 125/140 | stdlib+vanilla(83), 수집기+SQLite(84) | (ADR-001) |
| D-02 | 사용량은 `~/.claude/projects/<enc>/**/*.jsonl` 에서 `"usage":` 사전 필터 후 허용 필드만 복사, requestId 중복 제거(last-wins), 메모리 증분 캐시 | 30 EDA: 중복 57.95%, 4.4 ms/MB | Admin API(키 필요) | (ADR-002) |
| D-03 | 한도 %는 statusLine 스냅샷(`workspace/memory/.monitor/claude-status.json`)에서, 전역 statusLine 은 체이닝 | 00 Q4 | 전역 설정 수정(02 §11 금지) | (ADR-003) |
| D-04 | 루프 제어: 대시보드는 `.control.json` 만, CLI 는 `loop-status.json` 만 쓴다(파일당 쓰기 주체 1개). wait-resume exit 0/10/20/2 | 경쟁 조건 제거 | 단일 파일 공유 | (ADR-004) |
| D-05 | 프론트 dist 를 저장소에 커밋, `.build-meta.json` 으로 신선도 검사 | 사용자 PC 에 Node 불필요 | 실행 시 빌드 | (ADR-005) |
| D-06 | 변경 감지는 1초 stat 폴링, watchfiles 미사용 | 03 원칙 3 | watchfiles | (ADR-008) |
| D-07 | AI-DLC 상태는 memory_cascade 의 읽기 함수만 사용, `aidlc.py status` 서브프로세스 금지(closed STM 을 아카이브하는 부작용) | 30 EDA 발견 | status 호출 | (ADR-009) |
| D-08 | 응답 envelope `{data, meta}`, 에러 `{"error":{code,message}}`, Host/Origin 가드 | user/02 §6 | - | (ADR-011) |
| D-09 | 루프 CLI exit code: 0 재개/정상, 10 계속 대기, 20 일시정지 상한 초과, 2 제어 파일 broken(계속 진행), 64 사용법 오류, 1 예기치 못한 예외(경고 후 계속). 루프를 멈추는 것은 일시정지 요청뿐. stdout 은 `AIDLC-LOOP <sub> <RESULT> k=v` 한 줄, 스킬은 exit code 로만 분기 | argparse 기본 2 와 broken 충돌 회피, 원칙 2 | - | (STM-0001, contracts/loop-cli.md) |
| D-10 | 일시정지 상한은 일시정지 1회(episode) 기준 — paused_since 는 반복 wait-resume 을 넘어 유지, 재개 시 null. 활성 루프가 없으면 loop-check·wait-resume·loop-end 는 쓰지 않고 exit 0(NO_LOOP) | 00 Q5 해석 | 루프 전체 누적 | (STM-0001) |
| D-11 | heartbeat 로 세션 생존을 판정하는 것은 paused 상태(120 s 기준)에서만. running 에서는 사이클 경계에서만 갱신되므로 판정하지 않음 | 오탐 방지 | - | (STM-0001) |
| D-12 | SSE: 첫 프레임 `retry: 5000`, keep-alive 15 s, id 미사용, ready = 사용량 캐시 데우기 완료, alerts 는 memory/tasks/usage 발행 시 파생, 연결 상한 초과 503 `TOO_MANY_STREAMS`(신규 에러 코드), 프론트는 45 s 무프레임 시 재연결 | ADR-011 보완 | - | (STM-0001, contracts/sse-events.md) |
| D-13 | `transcript_dir_name` 은 `^(?!\.{1,2}(?![\s\S]))[A-Za-z0-9._-]{1,255}(?![\s\S])` 로 제한, reader 는 재검증 + resolve 결과가 `~/.claude/projects/` 직속 하위인지 확인(실패 시 폴백, 값 없이 코드만 기록), API 응답·SSE·로그 노출 금지 | security 리뷰 FAIL 조치 | 관대한 reader | (STM-0001, contracts/README §2·§3) |
| D-14 | 비-JSON Content-Type 의 변경 요청도 403 `FORBIDDEN_ORIGIN` 으로 거부 (415 는 계약 위반=FAIL) | 20 §QS-05 가 명시, 20 §8 에러 코드는 닫힌 집합(415 없음), ADR-011 §5 가 같은 항목에서 묶어 서술 | 415 | (STM-0003, architecture 리뷰) |
| D-15 | Origin 헤더 없는 로컬 POST 는 잔여 위험으로 수용 | ADR-011 이 토큰 인증을 기각 | 토큰 인증 | (STM-0003, threat-model.md) |

## 2. 확립된 패턴 & 컨벤션 (Patterns)
- 공통 DoD: 테스트 통과, ruff/eslint/타입 검사, frontend 변경 시 dist 재빌드, 문서 갱신, run 스크립트로 화면 확인 (user/02§10)
- Claude 기록에서는 usage·model·timestamp·requestId·isSidechain 만 읽는다. 실제 `~/.claude` 기록은 테스트에 쓰지 않는다 (user/02§5, 00 Q2)
- Windows 에서는 `python3` 대신 `python`/`py`, 셸 스크립트는 LF (CLAUDE.md 실행 환경)
- (예: 모든 API 응답은 `{data, error}` 래퍼 사용 (STM-0002))
- 파일 계약: 스키마는 작성자를 검증(additionalProperties false), 읽는 쪽은 관대하되 schema 버전 불일치는 broken(SOURCE_PARSE_ERROR). 단, 보안 필드는 reader 도 재검증 (STM-0001)
- 파일당 쓰기 주체 1개: `.control.json` = 대시보드, `.monitor/loop-status.json` = 루프 CLI, `.monitor/claude-status.json` = statusline 스크립트 (STM-0001, contracts/README)
- JSON Schema 2020-12 의 `format` 은 기본 annotation 이라 강제되지 않는다 → 시각 등은 `pattern` 으로 함께 강제 (STM-0001)
- JSON Schema pattern 의 끝 앵커는 `$` 대신 `(?![\s\S])` — Python `re` 의 `$` 는 끝 개행 앞에서도 매치된다. Python·ECMA 동일 동작 (STM-0001)
- 존재하지 않는 경로의 무시 여부는 `git check-ignore --no-index -v <path>` 로 확인. 디렉터리 패턴은 하위 파일 경로로 검사 (STM-0002)
- 보안 리뷰 체크리스트 ID 체계: P-(개인정보) / N-(네트워크 Host·Origin) / W-(쓰기 경로) / D-(의존성) / T-(본문 비노출 테스트). threat-model 의 검증 열이 이 ID 를 가리킨다. ID 는 한 문서(privacy.md)에서 정의하고 다른 문서는 참조만 한다 (STM-0003)
- 주의: privacy.md 의 체크리스트 D-01~D-04(의존성)는 이 파일 §1 결정 D-01~ 과 번호가 겹친다. 맥락(문서)으로 구분하고, 인용 시 출처 문서를 함께 적는다 (STM-0003)

## 3. 알려진 이슈 & 리스크 (Known Issues)
| ID | 내용 | 영향 범위 | 상태 | 출처 |
|----|------|-----------|------|------|
| ~~I-01~~ | ~~`.gitignore` 에 런타임 파일 미등록~~ | 저장소(public) | 해결 (STM-0002): 런타임·build 블록 추가 | (STM-0001, STM-0002) |
| I-03 | 전역 `dist/` 같은 넓은 무시 패턴이 추가되면 커밋 대상 dist 가 무시됨(ADR-005 위반) | 배포 | 감시: 리뷰 시 `git check-ignore --no-index monitor/frontend/dist/index.html` 가 exit 1 | (STM-0002) |
| I-02 | `TOO_MANY_STREAMS`(503), loop-cli 결정(exit 64/1, episode 상한, NO_LOOP) 이 ADR-004·ADR-011·20 §5 에 아직 없음 | 문서 정합성 | 열림 → T-009 | (STM-0001) |
| I-04 | ADR-011 §4: Host 가드(TrustedHostMiddleware)가 포트를 검사할지 미정. 현재는 포트 무시인데 privacy.md N-02 는 포트 불일치 거부를 요구 | 보안 체크리스트 정합성 (비차단) | 열림: 검사하면 구현 방식을 ADR 에 명시, 안 하면 N-02 포트 케이스를 선택 항목으로 유지 | (STM-0003) |
| I-05 | ADR-011 §5 에 비-JSON Content-Type 도 403 `FORBIDDEN_ORIGIN` 이라는 한 줄 보강 필요 (D-14) | 문서 정합성 (비차단) | 열림 → [architecture] 후보 | (STM-0003) |
| I-06 | 보안 통제가 모두 "요구" 상태(구현 전). 구현 후 P/N/W/T 항목을 실제 실행 근거와 함께 재확인 필요 | 보안 | 열림: backend 구현 후 security 리뷰 | (STM-0003) |
| I-07 | tasks.md T-002 DoD 경로 `workspace/teams/security/` 가 실제 경로 `workspace/project/security/` 와 불일치 | 문서 정합성 | 열림 → cascade 2/3 에서 정정 | (STM-0003) |

## 4. 팀별 지식 (Team Knowledge)
<!-- /aidlc-teams 가 생성된 팀마다 "### <team-id>" 소제목을 추가한다 -->

### product
- (아직 없음)

### architecture
- (아직 없음)

### qa
- (아직 없음)

### cicd
- (아직 없음)
- .gitignore 의 Monitor 항목은 런타임 / build·dev 두 주석 블록. dist 는 의도적으로 제외(ADR-005) (STM-0002)

### ops
- (아직 없음)

### security
- (아직 없음)
- 보안 문서 경로는 `workspace/project/security/` (threat-model.md = STRIDE 6영역, privacy.md = 허용 필드·접근 범위·Host/Origin·체크리스트). charter·40·타 팀 charter 모두 이 경로를 참조 (STM-0003)
- 보안 경계는 "허용 필드 allow-list 복사"다. `"usage":` 사전 필터는 성능용이며 보안 경계가 아니다 (본문에 usage 문자열이 있어도 유입되지 않음) (STM-0003)
- 체크리스트 ID 체계는 §2 참조 (P-/N-/W-/D-/T-). 비-JSON Content-Type 도 403 FORBIDDEN_ORIGIN 이 기준 (D-14) (STM-0003)
- 쓰기 경로는 `.control.json` 1개뿐 (R-10·QS-07). Origin 없는 로컬 POST 는 수용된 잔여 위험 (D-15) (STM-0003)

### backend
- (아직 없음)

### frontend
- (아직 없음)
- 계약 문서는 jsonschema Draft202012 로 check_schema + examples + 음성 케이스까지 돌려 검증한다 (STM-0001)
- 경로성 필드는 패턴 검증 + resolve 후 경계 검사 + 노출 금지 3종을 같이 요구한다. symlink 우회 여부는 backend reader 리뷰 때 재확인 (STM-0001)

## 5. 교훈 (Lessons Learned)
- (반복하지 말아야 할 실수, 효과가 있었던 방법)
- examples 만이 아니라 음성 케이스까지 스키마로 돌려야 `format` 비강제, `$` 끝 개행 같은 구멍이 드러난다 (STM-0001)
- 보안 리뷰는 계약 단계에서도 효과가 있다 — 구현 전에 경로 이탈(`..`) 위험을 막았다 (STM-0001)
- 번호 참조를 문서 두 개에 나눠 쓰면 어긋나기 쉽다 — 한 문서에서 ID 를 정의하고 다른 문서는 참조만 한다 (STM-0003)
- 리뷰 모드가 문서 대조만으로도 구현 전 모순(415 vs 403, Host 포트 무시 vs N-02)을 잡아냈다 (STM-0003)

## 6. 용어집 (Glossary)
| 용어 | 정의 |
|------|------|
