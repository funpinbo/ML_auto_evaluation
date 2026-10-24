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
