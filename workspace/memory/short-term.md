---
status: active
task: T-010
team: backend
outcome: done
opened_at: 2026-10-24T00:20:45+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-010 [backend] 사용량 수집기(프로젝트 폴더 해석, 증분 커서, `"usage":` 사전 필터, 허용 필드, requestId 중복 제거, 시간 버킷, 데우기) + statusline.sh/py(허용 필드 스냅샷, 원자적 쓰기, 전역 statusLine 체이닝) + settings.json statusLine 등록 + GET /usage/summary, /usage/timeseries — FR-004 | deps: T-002, T-003, T-005, T-020
- 완료 조건(DoD): 본문 비노출 테스트·중복 제거 테스트·폴백(스냅샷 없음) 테스트 통과, `transcript_dir_name` 재검증 + `~/.claude/projects` 직속 하위 경계 검사(symlink 포함) 테스트, 응답·로그에 transcript_dir_name 미포함 테스트, `projects/<enc>/` 안 상대 symlink(`creds-link.jsonl -> ../../.credentials.json`, fixture `symlink_escape.credentials_link`) 거부 테스트 (D-13, 출처: STM-0001 §5, STM-0007 §5), V3(일시정지됨) 화면에 세션 활동 정보 제공, `aidlc.py` 모듈 docstring(도움말)에 loop-* 4줄 추가(I-37), `app.state.warmup.progress() -> {state, progress}` 노출(tests/ops warmup 케이스로 회귀 확인)·리더 WARN/INFO 로그(NFR-002, 20 §6)·`source_status()` 서비스 이전 여부 결정(I-26) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련 FR: FR-004 (stories/FR-004.md AC-1~22), KPI-01(5시간 한도 %), 04 DS-03·DS-04, 30 EDA(중복 57.95%, `"usage":` 사전 필터, 4.4 ms/MB, 증분 캐시)
- 계약·ADR: ADR-002(사용량 수집), ADR-003(statusLine 스냅샷·체이닝), contracts/claude-status.schema.json, contracts/README §2·§3·§4(warmup 인터페이스), privacy.md(허용 필드·~/.claude 범위·P-25~P-29), threat-model
- LTM: D-02, D-03, D-13(transcript_dir_name 재검증·노출 금지), D-16·D-24(테스트 홈 격리), D-17(3자 대조), D-34(health usage_warming), D-40 패턴, I-26(warmup·WARN/INFO 로그), I-10(하드 링크)
- fixture: tests/fixtures/{jsonl_gen,claude_home,markers,reference_parser}.py, symlink_escape.credentials_link

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->
- 기준 문서 확인: ADR-002/003, contracts README §2~§4 + claude-status.schema, privacy.md §1~§4.1·§7, FR-004 AC-1~22, 30 EDA, 20 §4~§6, ops/logging.md. 기존 스위트 811 passed 확인.
- `app/services/usage/` 5모듈 작성: `privacy_filter`(사전 필터 → 허용 필드 dataclass, requestId 는 blake2b-16 다이제스트), `resolver`(규칙 인코딩 → 힌트 재검증 → usage 줄 cwd 폴백, 직속 하위 resolve 검사, symlink 미추적 탐색), `aggregator`(시간×모델×sidechain 버킷, 전역 last-wins, 파일 단위 기여분 빼기, 30일 정리), `collector`(커서 dev/ino/size/mtime_ns/offset, 잘림·교체·삭제 리셋, `O_NOFOLLOW`·realpath·`st_nlink>1` 건너뜀, 1 MiB 청크·32 MiB 줄 상한, 최근 파일 우선 데우기 스레드, `progress()`), `service`(summary/timeseries 패널 조립).
- `services/statusline_reader.py`(64 KB 상한·정규 파일만, schema≠1·captured_at 오류 = broken, 힌트 재검증), `models/usage.py`, `api/usage.py`(GET /usage/summary?tz_offset_min, /usage/timeseries?range&bucket&group&tz_offset_min).
- `main.py`: 수집기 생성만(I/O 없음), `app.state.warmup = collector`, FastAPI lifespan 에서 `start_warmup()`/`stop()`. 데우기 전 첫 사용량 요청은 동기 1회 읽기. ControlData 에 `session_activity_at`/`session_activity_age_sec`(V3 세션 활동 = JSONL 최근 mtime, 데우기 전 null) 추가.
- `aidlc/hooks/statusline.sh`(run.sh 방식, LF, Python 없으면 빈 줄) + `statusline.py`(허용 필드 스냅샷 먼저 원자 저장 → 전역 statusLine 체이닝(새 프로세스 그룹, 2 s 후 killpg) → 자기 한 줄, 항상 exit 0). `.claude/settings.json` 에 `statusLine` 키만 추가(hooks 불변). `aidlc.py` docstring loop-* 4줄.
- 테스트 6파일 +182건(unit: usage_collector 37, usage_resolver 46, statusline_reader 28, statusline_script 28 / api: usage_api 44 / 공용 usage_support). OpenAPI export → docs/api 재생성.
- 스크래치 사본 변이 6종: 사전 필터 제거·링크 검사 제거·중복 제거 제거·직속 하위 검사 제거·잘림 리셋 제거 = 5/5 검출, symlink is_symlink 제거 1건은 동치 변이(`follow_symlinks=False` 검사가 같은 역할).
- 로컬 게이트 `monitor/.venv/bin/python monitor/tools/check.py` 전 단계 PASS(frontend SKIP), `python3 -m unittest discover -s aidlc/tests` 31 OK.
- [조치 1차 — security FAIL] 해석기 cwd 폴백(`_scan_cwd`→`_file_has_cwd`)이 하드 링크를 열던 문제: 공용 `app/services/usage/safe_open.open_regular` 신설(lstat 정규 파일·`st_nlink == 1`·symlink 아님 → `O_RDONLY|O_NOFOLLOW|O_NONBLOCK` → fstat 정규 파일·(dev, ino) 일치·nlink 1, 아니면 close 후 거부). 수집기 `_read_file`(expect=탐색 stat)·해석기 폴백(+ realpath 경계 검사, `Resolution.skipped_files` 건수)·`StatuslineReader.read`(lstat → symlink·하드 링크·FIFO = unreadable) 모두 이 함수로만 연다. WARN 문구를 실제 세는 대상과 맞춰 `하드 링크·일반 파일 아님·경계 밖 기록 파일 N개를 건너뛰었습니다` 로 변경(ops 지적), 폴백 거부 건수도 같은 문구로 기록.
- 추가 테스트(security): `test_usage_resolver.py::{test_cwd_fallback_never_opens_hardlinks_or_fifos, test_collector_logs_fallback_skips_as_count, test_open_regular_rules}`, `test_usage_collector.py::test_hardlink_swapped_in_after_scan_is_not_read`(+ 기존 `test_hardlinked_files_are_skipped` 에 os.open spy), `test_statusline_reader.py::test_symlink_and_hardlink_snapshot_are_unreadable`. 변이: 폴백을 plain open 으로 되돌림 → 2건 FAIL, fstat 대조 제거 → FAIL.
- [조치 1차 — qa FAIL] `test_usage_collector.py::test_incremental_reads_only_new_bytes_exact_counts`(requestId 없는 줄 포함 추가 후 정확한 건수·시간 버킷, fdopen spy 로 seek == 이전 크기·읽은 바이트 == 추가 바이트), `test_statusline_script.py::test_chain_timeout_kills_grandchildren`(`sleep A & sleep B; wait` 고유 숫자, elapsed < 2.8 s, /proc 에 남은 손자 0, finalizer 정리). 변이 `_consume` offset 무시·`killpg`→`proc.kill()` 둘 다 검출(실측 정상 2.04 s).
- 조치 후 게이트 PASS: backend 1000 passed, 커버리지 97%, aidlc unittest OK, OpenAPI 변경 없음(--check 최신).

## 4. 발견 사항 (LTM 후보)
- 결정:
  - I-26: `source_status()` 는 **backend 로 옮기지 않는다** — health(ops)의 stat 판정이 단일 출처로 남고 D-34 규칙 그대로. backend 는 `app.state.warmup.progress()`(= UsageCollector, I/O 없음) 와 리더 WARN/INFO 로그(고정 문구 + 건수·코드: `사용량 기록 형식 오류 N줄을 건너뛰었습니다`, `requestId 없는 사용량 응답 N건…`, `링크(심볼릭·하드) 기록 파일 N개를 건너뛰었습니다`, `사용량 기록 폴더를 찾았습니다 (encoded|hint|cwd)`, `…기록 폴더를 찾지 못했습니다`, `…힌트를 무시했습니다: HINT_*`, `사용량 데우기/갱신 오류: <예외타입>`)를 제공. 같은 상태 로그는 한 번만.
  - I-10(가정, T-022 확정 대기): JSONL 하드 링크(`st_nlink > 1`)는 **건너뜀**(보수적 기본값). symlink 는 탐색에서 따라가지 않고, 열 때 `O_NOFOLLOW`, realpath 가 프로젝트 디렉터리 밖이면 건너뜀(3중).
  - requestId 는 메모리에 원문 대신 blake2b 16바이트 다이제스트로만 둔다 → 집계 구조 순회 시 ID 표식 0(P-11, S-07).
  - 데우기는 lifespan 시작, `create_app` 은 파일 I/O 0(export_openapi·health 폴링 안전). `TestClient` 를 `with` 없이 쓰면 `not_started` 유지(ops 기존 warmup 케이스 그대로 PASS).
  - 패널 상태: 스냅샷 없음 = `ok` + `limits_notice`(경고 아님), rate_limits 없음 = `ok` + 안내, stale(>600 s)·broken = `partial` + `meta.error`(SNAPSHOT_STALE / SOURCE_PARSE_ERROR), 기록 폴더 없음 = summary `partial`(스냅샷도 없으면 `empty`) + PROJECT_DIR_NOT_FOUND, timeseries `empty` + 같은 코드, 기간 내 0건 = `empty`, 데우는 중 = `warming`. JSONL 깨진 줄은 `data.skipped_lines` 건수만(partial 아님, FR-004 §4).
  - 토큰 값: 키 누락 = 0, 정수 아님·bool·음수 → 줄 버림(P-04). 시간대 없는 timestamp → 버림. model 이 문자열 아님/128자 초과 → `unknown`.
  - 집계 단위는 UTC 1시간 버킷: day 버킷은 `tz_offset_min` 로 로컬 날짜에 묶고(30분 단위 오프셋은 최대 30분 오차), 5시간 구간은 구간과 겹치는 시간 버킷 합(최대 1시간 앞 포함). 5h 구간 시작 = 미래 `resets_at − 5h`, 지났거나 없으면 이동 5시간 + `estimated=true`.
  - timeseries 응답은 열 지향(`buckets` 시각 목록 + series 별 지표 배열, 0 채움). 30d 기본 bucket = day.
  - statusLine 명령은 `bash "${CLAUDE_PROJECT_DIR:-.}/aidlc/hooks/statusline.sh"` — `CLAUDE_PROJECT_DIR` 미제공이면 세션 cwd(저장소 루트)로 폴백(ADR-003 Decision 1 의 확인 항목을 두 경우 모두 동작하게).
  - API 추가(계약 리뷰 필요): `/usage/summary?tz_offset_min`(20 §5 는 timeseries 에만 표기), ControlData `session_activity_at`·`session_activity_age_sec`.
- 패턴:
  - content trap: `json.loads(raw, object_hook=_Trap)` 로 허용 키 밖 접근·순회 시 예외 → 본문 비접근을 실행으로 증명(T-06). `walk_values` 객체 그래프 순회로 집계 구조 표식 검사(T-03, 속성 이름은 제외).
  - `shell=True` 체이닝 timeout 은 `subprocess.run(timeout=)` 로 부족 — 손자 프로세스가 파이프를 잡아 멈춤. `start_new_session=True` + `os.killpg` 로 2.0 s 에 끝남 실측.
  - status line 스크립트 테스트는 hooks 2파일을 임시 저장소 사본에 복사해 서브프로세스로 실행(자기 위치 기준 쓰기라 실제 workspace 불변), HOME 임시·CLAUDE_CONFIG_DIR 제거.
- 이슈/리스크:
  - `aidlc/hooks/statusline.py` 는 로컬 게이트 ruff/mypy 대상(PY_TARGETS)이 아니다 — 수동으로 ruff(기본 규칙: S110·UP017 포함) 통과시킴. 런처가 Python 3.10 을 허용하므로 `datetime.UTC`(3.11) 대신 `timezone.utc` + noqa.
  - 실제 Claude Code 세션에서 statusLine 실행·`CLAUDE_PROJECT_DIR` 제공·VS Code 패널 동작(A5)은 미검증(이 환경에서 확인 불가).
  - snapshot reader 가 잘못된 힌트를 먼저 버리므로 API 경로에서는 `HINT_INVALID_NAME` 로그가 나오지 않는다(직속 하위 위반 `HINT_OUTSIDE_PROJECTS`/`HINT_NOT_FOUND` 만 로그). 값은 어디에도 남지 않는다.
- 교훈:
  - 방어를 여러 겹 두면 한 겹을 지우는 변이가 살아남는다 — 겹마다 직접 단위 테스트(iter_jsonl 단독)를 두고, 남는 변이는 동치인지 확인한다.

## 5. 새로 발견된 Task (Task 후보)
- [architecture] T-010 계약 반영 리뷰: openapi 의 `/usage/summary?tz_offset_min`·UsageSummaryData/UsageTimeseriesData(열 지향)·ControlData `session_activity_*` 를 20 §5 엔드포인트 표와 맞추고, contracts/README §4 "소스 상태 판정" 행에 I-26 결정(이전 안 함) 기록
- [security] I-10 하드 링크 방침을 threat-model §2.4·privacy P-29 에 확정(T-010 은 `st_nlink > 1` 건너뜀으로 구현) — T-022 입력
- [cicd] `monitor/tools/check.py` PY_TARGETS·mypy 대상에 `aidlc/hooks/statusline.py` 추가(현재 게이트 밖)
- [ops] 런북 warmup-slow.md·statusline-not-running.md 를 실제 구현 기준으로 갱신(로그 문구 목록, `${CLAUDE_PROJECT_DIR:-.}` 폴백, 스냅샷 경로) + ops/logging.md §2 예시에 사용량 WARN 문구
- [backend] T-011: 1초 폴링에서 `collector.refresh()` 호출 → 변경 시 `usage` topic, 데우기 완료 = `ready` 이벤트, 스냅샷 mtime·captured_at 600 s 경계에서 `usage` 발행(FR-004 AC-20)
- [product] T-014 UAT: 실제 CLI·VS Code 세션에서 statusLine 실행 여부, stdin 키·단위(rate_limits, resets_at 정수 여부) 확인 → 30 EDA DS-04 가설 해제
- [ops] (T-028 범위에 합침) warmup-slow.md: T-010 이후 상태 전이(not_started→warming→done/unknown)·실측(310 MB ≈1.2 s)·로그 문구 7종과 대응 조치, 링크 WARN 은 하드 링크만 센다는 점 / statusline-not-running.md: 스냅샷 경로 `workspace/memory/.monitor/claude-status.json`, `${CLAUDE_PROJECT_DIR:-.}` 폴백, 전역 statusLine 체이닝(사용자 줄 먼저·2 s timeout·자기 참조 생략), 스크립트는 오류 메시지를 내지 않으므로 4단계를 '출력 줄·스냅샷 갱신 여부로 판단'으로 교체, Python 없음 = 빈 줄 / logging.md §2 에 사용량 WARN/INFO 예시 (출처: T-010 ops 리뷰)
- [backend] (선택) 링크 WARN 문구 `링크(심볼릭·하드)` 가 실제로는 하드 링크만 셈 — symlink 도 건수에 넣거나 문구를 '하드 링크'로 (T-010 ops 리뷰, 비차단)
- [backend] (차단, T-010 security 리뷰 FAIL) `resolver._scan_cwd`/`_file_has_cwd`(cwd 폴백)가 하드 링크(`st_nlink > 1`)를 건너뛰지 않음 — `projects/<임의>/s.jsonl` = `~/.claude/.credentials.json` 하드 링크를 `openat(O_NOFOLLOW)` 로 연다(strace 실측). 수집기와 같은 규칙 적용: `entry.stat(follow_symlinks=False).st_nlink > 1` 이면 건너뜀 + 연 뒤 `fstat` 으로 S_ISREG·(dev,ino) 일치 확인, 회귀 테스트(폴백 탐색이 하드 링크 파일을 열지 않음: os.open spy) 추가
- [backend] (비차단, security) `StatuslineReader.read` 에 `O_NOFOLLOW` 추가(스냅샷 자리 symlink 를 따라가지 않음 — 지금은 허용 필드만 꺼내 노출은 없음), 수집기·폴백의 JSONL open 에 FIFO 경합 대비 `O_NONBLOCK`(또는 open 후 fstat 전 블록 방지) 검토 — I-38 과 같은 부류
- [backend] (차단, T-010 qa 리뷰 FAIL) 증분 커서 테스트 보강: `test_incremental_append_and_partial_tail` 은 `_consume` 진입 시 `end - cursor.offset` 만 보므로 `_consume` 가 offset 을 무시하고 0 부터 다시 읽어도 통과(변이 `fh.seek(0); pos=0` 생존). 실제로 그 변이에서 requestId 없는 줄 1개 + 1개 추가 → 집계 3건(정답 2). requestId 없는 줄 추가 후 정확한 건수 단언 + 실제 읽은 바이트(fh.read/seek spy) 단언 추가
- [backend] (차단, T-010 qa 리뷰 FAIL) `test_chain_timeout_2s_kills_group` 은 단일 명령(셸이 exec)이라 `os.killpg`→`proc.kill()` 변이가 생존(elapsed < 6 허용). 복합 명령(`<py> -c 'sleep' ; true` 또는 `sleep 30 & wait`)으로 손자 프로세스를 만들고 elapsed < 2.8 s + 손자 프로세스 잔류 0 을 단언(변이 시 3.0 s + 고아 프로세스 실측)
- [backend] T-010 security 조치(현재 작업 트리의 미커밋 `safe_open.py`·collector/resolver 변경) 커밋 후 qa 재리뷰 — 이번 qa 판정은 커밋 4dcccbd 기준
- [qa] tests/perf: FR-004 AC-22 종단 성능(Task 100 + 30일 JSONL fixture, 접속→사용량 패널 값 또는 warming ≤ 2 s, JSONL 1 MB 추가 후 반영 ≤ 5 s — 반영 부분은 T-011 후) 시나리오 작성

## 6. 결과 & 인수인계
- 산출물(파일/PR):
  - 신규: `monitor/backend/app/services/usage/{__init__,privacy_filter,resolver,aggregator,collector,service}.py`, `app/services/statusline_reader.py`, `app/models/usage.py`, `app/api/usage.py`, `aidlc/hooks/statusline.{sh,py}`
  - 수정: `app/main.py`(수집기·lifespan·라우터), `app/api/deps.py`(Services.usage), `app/services/control.py`·`app/models/control.py`(V3 세션 활동), `.claude/settings.json`(statusLine 키만), `aidlc/scripts/aidlc.py`(docstring loop-* 4줄)
  - 테스트: `tests/unit/{usage_support,test_usage_collector,test_usage_resolver,test_statusline_reader,test_statusline_script}.py`, `tests/api/test_usage_api.py`
  - 재생성: `workspace/project/contracts/openapi.json`(export_openapi.py), `docs/api/reference.md`(openapi_docs.py render)
- 검증 결과:
  - `monitor/.venv/bin/python monitor/tools/check.py` → 게이트 PASS (ruff format/check, mypy backend·tools, pytest backend 993 passed 커버리지 97%, launcher/tools pytest, dist 신선도, OpenAPI export diff, API 레퍼런스 신선도; frontend SKIP=T-012 전)
  - `python3 -m unittest discover -s aidlc/tests` 31 OK, `ruff check aidlc/hooks/statusline.py` PASS
  - DoD 대응: 본문 비노출(응답·헤더·로그·집계 구조·스냅샷), 중복 제거(7줄 last-wins·파일 간), 폴백(스냅샷 없음·rate_limits 없음·창 하나 없음), transcript_dir_name 재검증(INVALID_DIR_NAMES 13종 reader·resolver·API) + 직속 하위 경계(symlink 밖/안), `symlink_escape.credentials_link` 미열람(os.open·builtins.open spy), 응답·로그 transcript_dir_name 0, warmup progress(not_started→warming→done, 최근 파일 우선, 실패 unknown) + tests/ops warmup 케이스 PASS, statusline(허용 필드·스키마·원자 교체·체이닝 같은 stdin·2 s timeout·자기 참조 생략·오류 exit 0·Python 없음 빈 줄), 50 MB 합성 cold < 5 s·증분 < 0.5 s(실측 0.1 s 미만)
  - 미실행: 실제 Claude Code 세션 statusLine 실측, `run.sh` 로 화면 확인(프론트 T-012 전이라 사용량 화면 없음 — API 만 확인)
- 남은 일: §5 후보. 리뷰 게이트 대상: qa(필수), security(수집기·status line·statusLine 등록), architecture(OpenAPI·계약 추가 필드), ops(warmup 인터페이스·로그 문구)

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
| architecture | PASS | ADR-002: resolver 3단계·커서(dev/ino/size/mtime/offset)·`"usage":` 사전 필터·requestId last-wins·UTC 시간 버킷+tz_offset_min 합산(§5 그대로)·lifespan 데우기·Lock, 새 의존성 0(import 전부 stdlib/기존 FastAPI·Pydantic, requirements 변경 없음, 원칙 3·ADR-006). ADR-003: settings.json 은 `statusLine` 키만 추가(hooks 불변), refreshInterval 30, `${CLAUDE_PROJECT_DIR:-.}` 폴백은 Decision 1 두 경우를 모두 덮으므로 수용(CLAUDE_PROJECT_DIR 제공 여부는 여전히 미실측 — T-014 UAT 로 이월), statusline.sh run.sh 방식 python3/python/py(R-09). 스냅샷 9필드 = schema required/properties 동일, 같은 디렉터리 임시→os.replace, 쓰기 주체 = statusline.py 단독·backend 는 읽기만(R-10, README §2 OK). README §4: `progress()` 동기·I/O 없음·`{state,progress}` 형식 일치, tests/api+tests/ops 516 passed(직접 실행). `source_status()` health 유지(health.py 변경 없음, D-34 불변) 수용. OpenAPI 하위 호환: 직전 커밋 대비 경로·스키마 삭제 0, 기존 경로 변경 0, ControlData 에 선택(nullable·required 아님) 필드 2개 추가만, 신규 2경로·9스키마 → 가산 변경. `tz_offset_min`(summary)·열 지향 timeseries 는 20 §5 의 미기재 세부일 뿐 ADR 과 모순 없음. control→usage 결합은 주입 callable + 예외 격리(패널 격리, NFR-002)라 수용. 근사(30분 TZ day ±30분, 5h 구간 최대 1h 앞 포함)는 ADR-002 §5 시간 버킷 결정의 귀결이고 KPI-01(한도 %·resets_at)은 스냅샷 값이라 영향 없음 → 수용(문서화 필요). 하드 링크 건너뜀은 I-10 보수적 기본값으로 수용. 재export 결과 git diff 0, openapi_docs render 결과 docs/api/reference.md 와 동일, `aidlc.py check project` PASS | 비차단: [architecture] 20 §5 usage 행에 summary `tz_offset_min`·timeseries 열 지향 형식·ControlData `session_activity_at/age_sec` 반영, contracts/README §4 소스 상태 판정 행에 I-26 결정(이전 안 함)·`Services` 에 usage 추가, ADR-002 Consequences 에 시간 버킷 근사(30분 오프셋 ±30분, 5h 구간 최대 +1h) 기록, ADR-003 체이닝 대상에 `$CLAUDE_CONFIG_DIR` 지원 명시 / [qa] FR-004 AC-16 오라클의 "현재 5시간 구간" 정의를 시간 버킷 겹침 기준과 맞춰 명시 / [product] T-014 UAT 에서 statusLine 실행 환경의 CLAUDE_PROJECT_DIR 제공 여부 기록 → ADR-003 Decision 1 확정 |
| ops | PASS | 설정: HEAD~1 대비 `.claude/settings.json` 변경 키 = `statusLine` 하나(hooks dict 동일 비교 True), type command·refreshInterval 30·`bash "${CLAUDE_PROJECT_DIR:-.}/aidlc/hooks/statusline.sh"`. 롤백 = 키 1개 제거 + 스냅샷 파일 삭제(backend 는 스냅샷 없음 = ok+limits_notice 로 폴백). statusLine 동작(임시 저장소 사본·임시 HOME 으로 실행): 런처는 run.sh 와 같은 python3/python/py 실제 실행 판정(+stdin </dev/null), Python 없는 PATH → `\n` 한 바이트 + rc 0; 전역 statusLine `echo USER-LINE` → 사용자 줄 먼저 + `AI-DLC 5h 24% · 7d 41% · $0.12`; CLAUDE_PROJECT_DIR 미설정 cwd 폴백 동작; 깨진 stdin·실패 체인(exit 3, stderr 버림)·자기 참조 생략 모두 rc 0; 느린 체인(`sleep 61 & sleep 62`) 2.05 s 에 종료·잔류 프로세스 0; 스냅샷에 session_id·경로 원문 0건. health: fake CLAUDE_HOME(30 파일 310 MB) + `python -m app --port 18765` 실제 기동 → 0.1 s 폴링에 usage_warming `warming 0.20→0.33→…→0.97` → `done 1.0`(약 1.2 s), app=aidlc-monitor 유지, not_started 는 tests/ops warmup 5건 PASS(TestClient lifespan 밖)로 확인, tests/ops 40 passed. 로그(stderr 실측): `INFO 사용량 기록 폴더를 찾았습니다 (encoded)`, `WARNING 사용량 기록 형식 오류 30줄을 건너뛰었습니다`, `WARNING requestId 없는 사용량 응답 30건을 중복 제거 없이 집계했습니다`, 별도 실행에서 `WARNING 링크(심볼릭·하드) 기록 파일 1개를 건너뛰었습니다` — 고정 문구+건수/코드, 경로·본문·req_ ID·스크래치 경로 grep 0건, access log 없음, 종료 후 서버 프로세스 0. 비차단 발견: symlink 는 탐색 단계에서 조용히 빠져 링크 WARN 건수에 안 잡힘(하드 링크만 셈 — 실측 hl+sl 2개 중 1개). 런북 차이: warmup-slow.md "T-010 전에는 항상 not_started" 구식·로그 문구 목록 없음, statusline-not-running.md 에 스냅샷 경로·`${CLAUDE_PROJECT_DIR:-.}` 폴백·체이닝(전역 줄 먼저, 2 s)·"스크립트는 오류를 출력하지 않음"(4단계 전제 틀림) 미반영, logging.md §2 에 사용량 WARN/INFO 예시 없음. SLO: 데우기는 백그라운드라 health·다른 패널 응답 지연 없음(폴링 중 매 응답 수신) | 비차단: [ops] T-028 범위에 합침 — 아래 §5 |
| security | FAIL | 직접 실행: backend pytest 993 passed. 코드 대조: privacy_filter 사전 필터(`b'"usage":'`)가 json.loads 앞(P-06), 허용 필드만 frozen dataclass 복사·requestId=blake2b-16·원본 dict 폐기(P-01·P-11), 본문 키 접근 0(P-02), extract_cwd 는 폴백 비교 후 폐기(P-05); 디스크 쓰기·pickle/sqlite/tempfile 0(P-12). DIR_NAME 패턴 resolver·statusline.py == schema 문자열 일치(P-25), 음성 13종 테스트(P-26), direct_child = resolve().parent==projects.resolve()(P-27). statusline.py: 스냅샷 9필드만(실측 stdin 에 session_id·cwd·workspace·extra·`$(...)` 표식 → 스냅샷엔 session_hash·단일 세그먼트만, `$(...)` 미실행), 같은 디렉터리 mkstemp→fsync→os.replace, settings.json 은 statusLine.command 만 추출·저장/로그 0(P-23), stdin 은 사용자 명령의 stdin 으로만 전달(명령줄 삽입 없음), 자기 참조 생략·2 s killpg·항상 exit 0(P-24). `${CLAUDE_PROJECT_DIR:-.}` 폴백: 저장소 하위 cwd 에서만 이 설정이 로드되므로 실행 대상은 저장소 트리 안(신뢰 경계 동일) — 수용. 실서버 probe(가짜 CLAUDE_HOME: qa 표식 fixture+symlink 3종+creds-link+하드 링크, statusline.sh 로 만든 스냅샷, :8799): /usage/summary·timeseries 6변형·control·memory·health·422 2건 응답과 서버 로그에서 표식 12종·dir_name·HOME/프로젝트 경로·세션 ID·escape 토큰값(424242) grep 0, 로그는 고정 문구+건수/코드(HINT_OUTSIDE_PROJECTS 포함). strace: CLAUDE_HOME 아래 쓰기·unlink·rename 0, `.credentials.json`·history·settings.json·outside/ open 0, JSONL open 은 전부 O_NOFOLLOW, escape-dir 힌트는 거부. **FAIL 근거**: cwd 폴백(`resolver._scan_cwd`→`_file_has_cwd`)은 st_nlink 검사가 없어 하드 링크를 연다 — 서버 strace 에서 `projects/<enc>/hard.jsonl`(밖 파일 하드 링크) open, resolver 단독 strace 에서 `projects/other-proj/s.jsonl` = `.credentials.json` 하드 링크 open 확인. 사전 필터·cwd 만 추출이라 내용 노출은 없지만 privacy §4(인증 파일 열지 않음)·I-10 건너뜀 방침과 DoD '하드 링크 건너뜀'이 수집기에만 적용됨. 변경 의존성 0(pip-audit 미실행, 해당 없음) | [backend] 폴백 탐색에도 st_nlink>1 건너뜀 + open 후 fstat(S_ISREG·dev/ino) + 회귀 테스트 → security 재리뷰(§5). 비차단: StatuslineReader O_NOFOLLOW, JSONL open FIFO 경합(§5) |
| qa | FAIL | 기준 커밋 4dcccbd(리뷰 도중 작업 트리에 security 조치용 미커밋 변경 생김 — 판정 범위 밖). 직접 실행: `monitor/.venv/bin/python monitor/tools/check.py` 게이트 PASS(backend pytest 52 s, frontend SKIP=T-012 전), T-010 테스트 6파일 182 passed ×3회 반복(8.2/8.5/8.9 s, 흔들림 없음), 가장 느린 것 chain timeout 2.04 s·50 MB perf 0.10 s → 스위트 부담 없음. 3자 대조: `test_three_way_match_generator_oracle_collector` 가 manifest.expected_buckets == reference_parser.aggregate == 수집기 버킷(숫자 5종 dict 동등) + 줄 분류 건수(ok/broken/no_usage/usage_string_only) + 거짓 양성 토큰 미포함 비교, API 쪽도 `_oracle_cells` 로 summary(today·5h)·timeseries 30d hour/model·day 비교. AC 표본: AC-3·5 안내 문구(정확 문자열), AC-6 SNAPSHOT_STALE, AC-8 broken→partial+토큰 정상, AC-9·10(7줄 last-wins·파일 간), AC-13·14·15(warming < 2 s, progress not_started→warming→done, 최근 파일 우선), AC-16 cache_hit_rate, AC-17·18(content trap·_loads spy), AC-19(13종) 테스트 확인. AC-20 은 T-011, AC-1·2·11·21 화면은 T-012, AC-22 종단 perf 미작성(qa 후보). 격리: autouse home_guard(audit hook) + statusline 테스트는 임시 저장소 사본·임시 HOME·CLAUDE_* 제거로 서브프로세스 실행, 실행 후 실제 workspace/memory/.monitor 없음·~/.claude/settings.json mtime 이 T-010 이전. 변이(스크래치 사본, 24종): 중복 제거 제거·first-wins·사전 필터 제거·cwd/본문/raw requestId 저장·symlink 추적(탐색만/3중 전부)·하드 링크 허용·30일 창(탐색/정리/둘 다)·잘림/inode 리셋 제거·잘린 꼬리 집계·oldest-first·progress done=None·statusline 비원자 쓰기·raw session_id·cwd 필드 추가·전체 transcript 경로·자기 참조 가드 제거 = 21 검출. 생존 3: ① collector `_inside` realpath 제거 — 탐색이 symlink 를 안 따라가고 nlink 검사가 있어 경합 외 동치(수용) ② `_consume` 가 offset 무시하고 0 부터 읽기 — 생존, 실측으로 requestId 없는 줄 이중 집계(2→3) 확인 = 증분 커서 테스트 결함 ③ statusline `os.killpg`→`proc.kill()` — 생존, 손자 프로세스 있는 명령에서 3.0 s + 고아 프로세스 실측 = 2 s 그룹 종료 테스트 결함. 백그라운드 프로세스 잔류 0 확인 | [backend] 증분 커서 테스트(익명 줄 추가 후 정확 건수 + 실제 읽은 바이트) / chain timeout 손자 프로세스 테스트(elapsed < 2.8 s·잔류 0) 보강 → qa 재리뷰. security 조치 커밋 후 같이 재리뷰. [qa] AC-22 tests/perf (§5) |
