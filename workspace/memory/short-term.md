---
status: active
task: T-007
team: cicd
outcome: done
opened_at: 2026-10-23T18:23:57+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-007 [cicd] run.py / run.sh / run.bat 원클릭 런처(Python 탐지, venv, 해시 마커 재설치 생략, 포트 선택, 헬스 대기, 브라우저 열기) + requirements 고정 + .gitignore + 로컬 게이트·dist 신선도 검사 — SCOPE-01, KPI-02 | deps: T-006
- 완료 조건(DoD): 깨끗한 상태에서 `bash run.sh --no-browser` 로 서버 기동·health 200 확인, 런처가 실제 선택한 포트를 서버 `settings.port` 로 전달·포트 0 금지(D-19), dist 가 무시되지 않음 확인(I-03), `monitor/backend/requirements.txt`(T-005 가 임시 작성, cicd 소유로 인수) 검토, TestClient httpx vs httpx2 결정(I-22), 런처 중복 실행 판정은 HTTP 200 + `data.app == "aidlc-monitor"`(400 BAD_HOST = 포트 불일치, D-34), `monitor/backend/requirements-dev.txt` 에 mypy(I-29)와 pytest==9.1.1, jsonschema==4.26.0(+referencing, jsonschema-specifications, rpds-py, attrs), ruff==0.17.2, pytest-cov, httpx 를 `pip freeze` 로 `==` 고정 (출처: STM-0004 §5) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: SCOPE-01(stories/SCOPE-01.md AC-1~16), KPI-02, user/02 §3·§4·§9·§10, 03 원칙 1·§6, ADR-001(런처), ADR-005(dist 커밋·신선도), ADR-006(의존성)
- LTM: D-19·D-32(포트: 기본 8765, AIDLC_MONITOR_PORT / `python -m app --port N`, 0·선행 0 금지, 127.0.0.1 고정), D-34(health `data.app` 판정), I-03(dist 무시 금지), I-12·I-22(의존성 최신 확인, httpx/httpx2), I-29(mypy), CLAUDE.md 실행 환경(Windows python/py, aidlc/hooks/run.sh 탐지 방식)
- 기존: monitor/backend/requirements.txt(T-005 임시 작성 → cicd 인수), monitor/.venv 는 개발용(.gitignore)

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->
- 컨텍스트: charter, user/02, SCOPE-01 AC-1~16, ADR-001/005/006, LTM D-19·D-32·D-34·I-03·I-12·I-22·I-29, `app/__main__.py`·`config.py`(`--port` 우선, 127.0.0.1 상수), `aidlc/hooks/run.sh` 탐지 방식 확인.
- PyPI JSON 으로 런타임·dev 전 패키지 최신판 조회(2026-10-23): requirements.txt 14개 모두 최신과 일치 → 핀 변경 없음, 헤더만 cicd 소유로 갱신. mypy 2.4.0, httpx2 2.16.0(2026-10-21) 확인.
- scratch venv(3.13)에 런타임+dev 직접 의존성 설치 → `pip freeze`. httpx2 로 돌리니 `tests/ops/test_logging_config.py::test_app_logs_have_no_paths_or_markers` 1건 FAIL (TestClient 요청이 "httpx2" 로거 INFO 로 찍힘, logging_config 는 "httpx" 만 낮춤) → httpx 0.28.1 유지로 결정, freeze 재작성.
- 작성: `run.py`(stdlib, 3.7 문법까지 — `ast.parse(feature_version=(3,7))` 확인), `run.sh`(LF, .gitattributes `*.sh eol=lf` 적용 대상), `run.bat`(CRLF, ASCII), `monitor/backend/requirements-dev.txt`, `monitor/backend/pyproject.toml`(ruff py311·pytest testpaths·coverage source=app fail_under=70·mypy files=app,scripts), `monitor/tools/check.py`(게이트), `monitor/tools/check_dist_fresh.py`(+`--write`), `monitor/tools/tests/test_run_launcher.py`(37건), `.gitignore`(mypy/ruff 캐시 3줄 추가).
- 깨끗한 venv 에 `pip install -r requirements-dev.txt` → `pip freeze` 가 고정 목록과 완전히 일치, `pip check` OK.
- 실측(공백+한글 경로 사본 `scratchpad/clone dir 한글`, monitor/.venv 없음, HOME=빈 임시 디렉터리): `bash run.sh --no-browser` → venv 생성·설치(pip 출력 44줄)·서버 기동·health 200 `data.app=aidlc-monitor` 까지 **4.9 s** (KPI-02 ≤ 5분). 두 번째 실행(서버 실행 중) 0.11 s, `설치 생략` + `이미 실행 중 http://127.0.0.1:8765/`, 새 서버 없음. 정지 후 재실행 `설치 생략`, health 까지 0.4 s. 임시 HOME 에 파일 0개(AC-14, pip 캐시 미사용).
- 추가 실측: 8765 를 다른 HTTP 서버가 점유 → `포트 8765 는 다른 프로그램이 사용 중` 후 8766 기동·health 200(AC-10). 프로세스 그룹 SIGINT(Ctrl+C 재현) → 서버 graceful shutdown, `종료 중…`/`서버를 종료했습니다.`, 런처 exit 0, 포트 해제(curl 000)(AC-16). 런처만 SIGTERM/SIGINT → 자식 종료 후 exit 0. 리스닝 주소 `/proc/net/tcp` = 127.0.0.1:8765 만(AC-11). Host 127.0.0.1:9999 → 400.
- 실패 경로 실측: PATH 에 Python 없음 → run.sh 안내 2줄 exit 1(AC-7). 존재하지 않는 패키지 핀 추가 → `패키지 설치에 실패했습니다: ERROR: ... No matching distribution ...` + 다음 행동, exit 1, 마커 없음(AC-8). 원복 후 주석 한 줄 변경 → 재설치(AC-6). 서버 기동 시 예외(사본 `__main__` 변조) → `서버가 시작되지 않았습니다 (종료 코드 1)` exit 1(AC-12).
- 수정: uvicorn 0.54 가 정상 종료 뒤 받은 신호를 다시 올려 자식 exit -15 → 런처 exit 241 이 나옴 → `_STOP_CODES`(0, -SIGINT, -SIGTERM, 130, 143, 0xC000013A) 를 정상 종료로 처리. 정지 유예 10 s → 5 s.
- 게이트 `monitor/.venv/bin/python monitor/tools/check.py`(30.8 s): ruff format/check PASS, **mypy(backend) FAIL 5건**, mypy(launcher/tools) PASS, pytest backend 561 passed cov 98% PASS, launcher/tools 37 passed PASS, frontend SKIP(디렉터리 없음), dist 신선도 PASS("no dist yet"), OpenAPI export diff PASS, API 레퍼런스 신선도 PASS. 게이트 종합 exit 1(mypy 때문, T-008·§5).
- `git check-ignore --no-index monitor/frontend/dist/index.html` exit 1, `dist/.build-meta.json`·`dist/assets/*.js` 도 exit 1(I-03). Hook 엔진 테스트 `python3 -m unittest discover -s aidlc/tests` OK.
- 실제 저장소에서도 `bash run.sh --no-browser` 1회(기존 venv, 마커 없어 설치 1회) → 0.9 s 기동, SIGINT 로 정지 exit 0. 실제 monitor/.venv 에 requirements-dev 설치(venv 안, 전역 아님) → freeze 일치. 남은 백그라운드 프로세스 없음 확인.
- run.bat 은 이 Linux 컨테이너에서 실행 불가 — 코드 리뷰만(아래 §4·§6).

## 4. 발견 사항 (LTM 후보)
- 결정: (1) httpx vs httpx2(I-22): **지금은 httpx==0.28.1 유지**. Starlette 1.9 TestClient 는 httpx2 를 우선하고 httpx 면 StarletteDeprecationWarning(경고 1건)을 낸다. httpx2 로 바꾸면 TestClient 요청 로그가 "httpx2" 로거 INFO 로 찍혀 ops 로그 누출 테스트가 실패하므로, ops 가 `logging.getLogger("httpx2")` 를 WARNING 으로 낮춘 뒤 cicd 가 httpx2==2.16.0(+httpcore2, truststore)로 교체(§5). (2) 런처는 `python -m app --port N` 으로 기동(ADR-001 §2.5 의 `-m uvicorn ... --host` 문구 대신 — 호스트 인자를 아예 넘기지 않고 `--port` 가 settings.port 단일 출처, D-19). 자식 env 에서 `AIDLC_MONITOR_PORT` 제거. (3) 해시 마커 = `monitor/.venv/.requirements.sha256`(requirements.txt 바이트 sha256), 설치 전에 지우고 성공 후에만 기록. (4) pip 는 `--no-cache-dir`(AC-14 전역 쓰기 없음). (5) 포트 후보 = 시작 포트부터 10개(ADR-001), 65535 를 넘지 않음, 0·선행 0 거부(app.config.parse_port 와 같은 규칙). 판정: bind 가능 → 기동 / bind 불가 + health 200·`data.app=="aidlc-monitor"` → 이미 실행 중 / 그 밖(400 BAD_HOST 포함) → 다음 포트. health 요청은 프록시 우회. (6) 게이트 = `monitor/tools/check.py`(charter 이름), dist 해시 규칙의 단일 출처 = `check_dist_fresh.py`(정렬된 POSIX 상대경로 + 파일별 sha256, CRLF→LF 정규화, `.build-meta.json` schema 1, 빌드 후 `--write`). 프론트 디렉터리 없으면 "no dist yet" exit 0, 프론트가 생긴 뒤 dist/메타 없으면 FAIL. (7) pip-audit 는 requirements-dev 에 넣지 않음(ADR-006 Decision 2 와 다름 — 전이 의존성 다수·오래됨) → 릴리스 전 임시 venv 실행.
- 가정: **Q-P3(run.bat 실패 시 창 유지) → 권장 기본값 채택**: exit code ≠ 0 이면 `pause` 로 창 유지, 성공(정상 종료)이면 닫힘. PO 답이 다르면 run.bat 끝 3줄만 바꾸면 된다. run.bat 메시지는 ASCII 영어(cmd 가 .bat 를 OEM 코드 페이지로 읽어 UTF-8 한글이 깨짐), 한국어 안내는 run.py 가 출력.
- 패턴: 런처 실측은 공백+한글 경로 사본 + 빈 임시 HOME 으로 돌리면 KPI-02 시간·AC-14(전역 쓰기 0) 를 한 번에 본다. Ctrl+C 재현은 `setsid` 후 프로세스 그룹에 SIGINT(백그라운드 `&` 는 SIGINT 를 무시 상태로 상속하므로 python 래퍼로 SIG_DFL 복원 필요). 게이트는 실패해도 모든 단계를 돌리고 요약.
- 이슈/리스크: (a) backend mypy 오류는 I-29 의 2건이 아니라 **5건/4파일**(aidlc_reader.py:173, pipeline.py:294, security.py:203·204, static_files.py:86) → 게이트 FAIL. T-008 DoD 는 2건만 명시(§5). (b) 02 §9 "1년 내 릴리스" 밖: 런타임 전이 h11 0.16.0(2025-04, 최신판), dev httpx 0.28.1(2024-12)·httpcore 1.0.9(2025-04)·jsonschema-specifications 2025.9.1(I-12, 여전히 최신)·colorama 0.4.6(2022-10, Windows 전용 pytest 의존). (c) 라이선스 MIT/BSD/Apache 밖: typing_extensions PSF-2.0(런타임 전이), certifi·pathspec MPL-2.0(dev 전이) — ADR-006 기록 필요. (d) run.bat 미실행(Windows 없음): Ctrl+C 뒤 cmd 의 "Terminate batch job (Y/N)?" 프롬프트가 뜰 수 있음, `.gitattributes` 에 `*.bat` CRLF 규칙 없음(작업 트리는 CRLF 로 저장). (e) Store 별칭 배제는 "실제 실행 후 버전 검사" 로 한다(스텁은 9009 로 실패) — WindowsApps 경로를 일괄 배제하면 진짜 Store Python 사용자가 막혀서 경로 배제는 하지 않음. (f) 포트 검사와 uvicorn bind 사이 경합 시 서버가 바로 죽고 AC-12 메시지로 끝난다(재시도 없음).
- 교훈: 프레임워크 교체(httpx→httpx2)는 의존성 파일만 바꾸면 끝나는 게 아니다 — 로거 이름 같은 부수 효과가 다른 팀 테스트를 깬다. 고정 전에 전체 테스트를 새 venv 로 돌린다. uvicorn 0.54 는 graceful 종료 뒤 신호를 다시 올려 exit -2/-15 로 끝난다 — 런처 종료 코드 매핑 필요.

## 5. 새로 발견된 Task (Task 후보)
- [ops] `app/logging_config.py` 에서 `logging.getLogger("httpx2")` 도 WARNING 으로 낮추기(+ 테스트) — httpx2 전환 선행 조건 (I-22, 출처: STM T-007 §4)
- [cicd] ops 수정 후 requirements-dev.txt 의 httpx/httpcore/certifi → httpx2==2.16.0·httpcore2==2.16.0·truststore==0.10.5 교체, 전체 테스트·StarletteDeprecationWarning 0건 확인 (I-22)
- [backend] mypy 오류 중 T-008 DoD 밖 3건 수정: `app/security.py:203·204`(미들웨어 체인 변수 타입), `app/static_files.py:86`(FileResponse vs HTMLResponse) — T-008 DoD 에 합치거나 별도 Task (I-29)
- [architecture] ADR-001 §2.5 문구를 실제 기동 방식(`python -m app --port N`, 호스트 인자 없음)으로, ADR-006 Decision 2 를 httpx(→httpx2 예정)·mypy 추가·pip-audit 별도 venv·라이선스 예외(typing_extensions PSF-2.0, certifi/pathspec MPL-2.0)·1년 경계(h11, httpx, httpcore, colorama)로 갱신 — T-009 에 합칠 수 있음
- [cicd] `workspace/project/release/release.md` 작성(버전 규칙, 롤백 = 커밋 되돌리기, pip-audit 임시 venv·npm audit 절차) — charter §5 P1 말
- [frontend] T-012 빌드 스크립트가 `npm run build` 뒤 `python ../tools/check_dist_fresh.py --write` 로 `dist/.build-meta.json` 을 기록하게 (해시 규칙은 check_dist_fresh.py 가 단일 출처)
- [cicd] `.gitattributes` 에 `*.bat text eol=crlf` 추가 검토(프레임워크 파일 — 소유 확인 필요)
- [product] UAT K2-W 에서 run.bat 실기 확인: 더블클릭 첫 실행 시간, 실패 시 pause, Ctrl+C 후 "Terminate batch job" 프롬프트 체감, 공백·한글 경로

## 6. 결과 & 인수인계
- 산출물(파일/PR): `run.py`, `run.sh`, `run.bat`, `monitor/backend/requirements.txt`(헤더만), `monitor/backend/requirements-dev.txt`(신규), `monitor/backend/pyproject.toml`(신규), `monitor/tools/check.py`, `monitor/tools/check_dist_fresh.py`, `monitor/tools/tests/test_run_launcher.py`, `.gitignore`(+3줄). 커밋 전(오케스트레이터 몫).
- 검증 결과: 깨끗한 사본에서 `bash run.sh --no-browser` → venv 생성·설치·health 200(`data.app=aidlc-monitor`) 4.9 s, 재실행 설치 생략·중복 실행 감지 0.11 s, 다른 프로그램 점유 시 다음 포트, Ctrl+C 정상 종료·포트 해제, AC-6/7/8/11/12/14 실측. 런처·도구 테스트 37 passed, backend 561 passed(cov 98%), ruff 통과, OpenAPI·API 레퍼런스 최신, dist 검사 "no dist yet", `git check-ignore --no-index monitor/frontend/dist/index.html` exit 1. requirements-dev 재설치 freeze 일치. **게이트 종합은 FAIL** — backend mypy 5건(기존 코드, T-008·§5 backend). run.bat 은 실행하지 못함(Linux) — 코드 리뷰만: `py -3` → `python` 실제 실행 검사(Store 스텁 9009 배제), CRLF, 실패 시 pause, exit code 전달.
- 남은 일: §5 후보(ops httpx2 로거 → cicd httpx2 교체, backend mypy 3건, ADR-001/006 문구, release.md, T-012 `--write` 연동). Windows 실기(UAT K2-W). 개발자는 `monitor/.venv/bin/python -m pip install -r monitor/backend/requirements-dev.txt` 후 `python monitor/tools/check.py`.

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
