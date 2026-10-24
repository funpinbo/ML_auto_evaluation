---
adr: 006
title: 백엔드 외부 의존성 — FastAPI·uvicorn(기본 설치)·Pydantic 만
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [CON-01, CON-02, 원칙 3, 03 §4, 03 §9, 02 §1, 02 §9, 02 §10, I-22, I-29]
---
# ADR-006. 백엔드 새 외부 의존성 (03 §9 필수)

## Context
- 02 §1: Backend = FastAPI + uvicorn, pip + requirements.txt. 02 §2: API 입출력은 Pydantic. 02 §9: 표준 라이브러리로 안 되는 경우만, MIT/Apache/BSD, 최근 1년 내 릴리스, 버전 고정.
- 원칙 3: 의존성 최소. 03 §4: watchfiles 는 "폴링보다 반응이 빠를 때만" 허용.
- `uvicorn[standard]` 는 httptools, python-dotenv, pyyaml, uvloop(비 Windows), watchfiles, websockets 를 추가로 설치한다(PyPI 메타데이터 확인).
- 2026-10-23 확인 최신: fastapi 0.161.1(MIT), uvicorn 0.54.0(BSD-3-Clause), pydantic 2.14.1(MIT, 2026-10-11), 모두 Python ≥ 3.10.

## Decision
1. **런타임 직접 의존성 3개**: `fastapi==0.161.1`, `uvicorn==0.54.0`(extras 없음), `pydantic==2.14.1`. 전이 의존성(starlette, pydantic-core, anyio, h11, click, typing-extensions, annotated-types 등)은 구현 Task 에서 venv 설치 후 `pip freeze` 결과로 `monitor/backend/requirements.txt` 에 전부 `==` 고정.
   - fastapi 0.161.1 전이 의존성 `opentelemetry-api==1.45.1`(Apache-2.0)·`annotated-doc==0.0.5`(MIT) 도 포함(I-22). opentelemetry-api 는 API 패키지뿐이고 SDK·exporter 가 없으며 자동 구성이 기본 꺼짐 → 외부 전송 없음(NFR-005 영향 없음). 직접 import 하지 않는다. 추가로 앱 팩토리가 FastAPI 네이티브 텔레메트리를 `telemetry={tracing, metrics, logs, operation_spans, auto_configure: False}` 로 명시해 끈다 — 사용자 환경의 `OTEL_*`·`FASTAPI_OTEL_AUTO_CONFIGURE` 와 무관하게 외부 전송 0(I-24, 실서버 OTLP 0건 확인 STM-0014, 테스트로 고정).
   - 전체 런타임 고정 목록(14개)의 정본은 `monitor/backend/requirements.txt`(cicd 소유, T-007 이 PyPI 최신과 일치 확인).
2. **개발 의존성**은 `requirements-dev.txt` 로 분리(사용자 설치 대상 아님, run.py 는 설치하지 않음): pytest, pytest-cov, httpx(TestClient 필요), ruff, **jsonschema**, **mypy**. pip-audit 는 dev 의존성이 아니다(아래).
   - 전이까지 `==` 고정한 정본은 `monitor/backend/requirements-dev.txt`(cicd 소유, T-007 이 Python 3.13 깨끗한 venv `pip freeze` 로 기록, `pip check` OK).
   - **httpx(I-22)**: `httpx==0.28.1`(+`httpcore==1.0.9`, `certifi==2026.10.23`) 를 유지한다. Starlette 1.9 TestClient 는 httpx2 를 우선하고 httpx 면 StarletteDeprecationWarning 을 내지만, httpx2 2.16.0 으로 바꾸면 TestClient 요청이 "httpx2" 로거 INFO 로 찍혀 `tests/ops/test_logging_config.py` 가 실패한다(logging_config 는 "httpx" 로거만 낮춤). ops 가 "httpx2"/"httpcore2" 로거를 WARNING 으로 낮춘 뒤 cicd 가 httpx2 로 교체한다(교체 시 이 항목 갱신, 새 ADR 불필요 — 같은 역할의 후속판).
   - **mypy(I-29)**: `mypy==2.4.0`(MIT) + 전이 `mypy_extensions==1.1.0`(MIT), `librt==0.16.0`(MIT, PyPy 제외), `ast_serialize==0.13.1`(MIT), `pathspec==1.1.1`(MPL-2.0). 근거: 02 §10 DoD "타입 검사 통과" 를 Python 쪽에서 검증할 표준 라이브러리 수단이 없다(원칙 3 예외 조건, 02 §9). dev 전용이라 사용자 설치 경로(원칙 1)에 영향 없음. 설정은 `monitor/backend/pyproject.toml`(files = app, scripts), 실행은 `monitor/tools/check.py` 게이트.
   - **pip-audit 는 dev 의존성에서 제외**: 전이 의존성이 많고(일부는 1년 경계 밖) 일상 개발 venv 에 상시 둘 이유가 없다(원칙 3). 대신 **릴리스 전 별도 임시 venv** 에 설치해 `requirements.txt`·`requirements-dev.txt` 를 감사하고 venv 를 버린다(절차: `workspace/project/release/release.md`, cicd·security). 버전은 실행 시점 최신을 쓰고 결과를 릴리스 기록에 남긴다.
   - `jsonschema==4.26.0`(MIT, Python ≥ 3.10) + 전이 4종 `referencing==0.37.0`, `jsonschema-specifications==2025.9.1`, `rpds-py==2026.9.1`, `attrs==26.1.0`(모두 MIT, 2026-10-23 `monitor/.venv` 메타데이터 확인). 용도: `workspace/project/contracts/*.schema.json`(JSON Schema 2020-12) 의 `check_schema`·examples·음성 케이스 검증과, 백엔드가 쓴 `.control.json` 을 계약 스키마로 검증하는 테스트(T-008).
   - 근거: 표준 라이브러리에 JSON Schema(2020-12) 검증기가 없고 직접 구현은 유지보수성(03 §2 3순위)을 해친다(원칙 3 의 예외 조건 충족, 02 §9). dev 전용이라 사용자 설치 경로(`requirements.txt`, 런처)에는 들어가지 않아 원칙 1 에 영향이 없다. 런타임 코드는 jsonschema 를 import 하지 않는다(필요하면 새 ADR).
   - 주의: `jsonschema-specifications 2025.9.1` 은 02 §9 "최근 1년 내 릴리스" 경계에 걸린다(전이·dev 전용·최신판이라 수용, 아래 예외 표). 새 릴리스가 있으면 올리고, 없으면 릴리스 전 pip-audit 결과로 판단한다.
3. 표준 라이브러리로 직접 구현: SSE 직렬화, 파일 감시(ADR-008), frontmatter 파싱(Hook 함수 재사용, ADR-009), JSONL 집계, 런처, 로깅. YAML·dotenv·requests 등 추가 금지.
4. 새 런타임 의존성을 더하려면 새 ADR 필요(architecture 리뷰). 새 **직접** dev 의존성도 이 ADR 개정 또는 새 ADR 필요(03 §9).
5. **02 §9 적용 범위와 예외**: 02 §9 의 라이선스(MIT/Apache/BSD)·"최근 1년 내 릴리스" 기준은 **직접 도입 결정**(우리가 requirements 에 직접 고르는 패키지)에 적용한다. 런타임 직접 의존성 3개(fastapi·uvicorn·pydantic)와 dev 직접 의존성은 **httpx 를 빼고** 모두 기준을 충족한다 — httpx 0.28.1(직접 dev, 2024-12)은 PyPI 최신판이지만 1년 경계 밖이라 아래 표에 직접 의존성 예외로 기록하고 httpx2 전환(I-22)까지 임시 수용한다. 직접 의존성이 끌고 오는 전이 의존성은 회피할 수 없으므로 아래처럼 근거와 함께 기록하고 수용한다. 전이 의존성까지 02 §9 가 적용되는지는 **사용자 확인 대기**(00 해석서 질문 후보) — 답이 "적용" 이면 이 표를 다시 판정한다.

   | 패키지 | 구분 | 기준 | 상태 | 수용 근거 |
   |--------|------|------|------|-----------|
   | typing_extensions 4.16.0 | 런타임 전이 | 라이선스 | PSF-2.0 | FastAPI·Pydantic 필수 의존성이라 회피 불가. PSF-2.0 은 허용형(permissive) 라이선스 |
   | certifi 2026.10.23 | dev 전이(httpx) | 라이선스 | MPL-2.0 | dev 전용, 사용자 설치·재배포 안 함. 파일 단위 약한 copyleft 라 수정·재배포하지 않으면 의무 없음. httpx2 전환 시 truststore 로 대체 예정 |
   | pathspec 1.1.1 | dev 전이(mypy) | 라이선스 | MPL-2.0 | dev 전용, 재배포 안 함(위와 같음) |
   | h11 0.16.0 | 런타임 전이(uvicorn) | 1년 내 릴리스 | 2025-04 | PyPI 최신판(새 릴리스 없음). uvicorn 기본 구현 필수 |
   | httpx 0.28.1 | **dev 직접** | 1년 내 릴리스 | 2024-12 | 유일한 직접 의존성 예외. 최신판, dev 전용 임시 수용 — httpx2 전환으로 해소 예정(I-22) |
   | httpcore 1.0.9 | dev 전이(httpx) | 1년 내 릴리스 | 2025-04 | 최신판, dev 전용 — httpx2 전환 시 함께 해소(I-22) |
   | colorama 0.4.6 | dev 전이(pytest, Windows 만) | 1년 내 릴리스 | 2022-10 | 최신판, dev 전용 |
   | jsonschema-specifications 2025.9.1 | dev 전이(jsonschema) | 1년 내 릴리스 | 2025-09 | 최신판, dev 전용 |
   | referencing 0.37.0 | dev 전이(jsonschema) | 1년 내 릴리스 | 2025-10-13 | 최신판, dev 전용 |
   | mypy_extensions 1.1.0 | dev 전이(mypy) | 1년 내 릴리스 | 2025-04-22 | 최신판, dev 전용 |

   - 판정 근거(2026-10-23, 1년 경계 = 2025-10-23): `requirements.txt` 14개 + `requirements-dev.txt` 22개 = 36개 핀 전수. 릴리스일은 PyPI JSON API(`https://pypi.org/pypi/<name>/json`, 해당 버전 파일의 최초 `upload_time`), 라이선스는 `monitor/.venv` 설치 메타데이터(`License-Expression`/Classifier, 미설치 colorama 는 PyPI 메타데이터 BSD). 경계 밖은 위 표 7건(h11·httpx·httpcore·colorama·jsonschema-specifications·referencing·mypy_extensions)뿐이고 모두 PyPI 최신판. 라이선스 예외는 위 표 3건뿐.
   - 표의 상태는 릴리스 전 pip-audit(임시 venv)로 취약점 여부를 함께 확인한다. 표에 없는 패키지가 기준을 벗어나면 이 ADR 을 개정한다.

## Alternatives
- **`uvicorn[standard]`**: 성능 향상(uvloop, httptools)은 단일 사용자 로컬에서 의미 없고, 6개 패키지 + 네이티브 바이너리 설치로 설치 시간·실패 가능성 증가(원칙 1·3). 기각.
- **Starlette 만 사용(FastAPI 없이)**: 의존성 1개 감소지만 02 지정 스택·OpenAPI 자동 생성(02 §6) 포기. 기각.
- **Pydantic 생략(dataclass)**: FastAPI 가 Pydantic 을 필수로 요구하고 02 §2 위반. 기각.

## Consequences
- (+) 설치 패키지 10개 안팎, 모두 순수 Python 또는 주요 OS 휠 제공(pydantic-core) → 최초 설치 1분 내외 예상.
- (+) 직접 의존성 라이선스는 MIT/BSD/Apache 만. 전이 의존성 예외(typing_extensions PSF-2.0 런타임, certifi·pathspec MPL-2.0 dev 전용)는 Decision 5 표에 기록.
- (−) uvicorn 기본 구현(asyncio + h11)은 처리량이 낮지만 성능은 5순위이고 요구 수준(단일 사용자)에서 충분.
- 릴리스 전 pip-audit 를 별도 임시 venv 에서 실행(security 확인, dev 의존성 아님 — Decision 2).
- (−) TestClient 가 httpx 로 돌아 StarletteDeprecationWarning 1건이 남는다 → httpx2 전환 Task 로 해소(I-22).

## 변경 이력
- 2026-10-23 T-021: Decision 2 dev 의존성에 jsonschema 4.26.0(+referencing, jsonschema-specifications, rpds-py, attrs, 모두 MIT) 추가(LTM I-08).
- 2026-10-23 T-007 architecture 리뷰 조치: Decision 2 에 mypy 2.4.0(+mypy_extensions, librt, ast_serialize, pathspec) 추가(02 §10·I-29), pip-audit 를 dev 의존성에서 빼고 릴리스 전 임시 venv 실행으로 변경, httpx 0.28.1 유지(httpx2 전환은 ops 로거 수정 후, I-22). Decision 1 에 fastapi 전이 opentelemetry-api·annotated-doc 기록(I-22). Decision 5(02 §9 적용 범위·전이 의존성 예외 표) 신설, Consequences 의 "라이선스 MIT/BSD/Apache 만" 정정. 02 §9 의 전이 의존성 적용 여부는 사용자 확인 대기.
- 2026-10-23 T-007 architecture 재리뷰 조치(문구만): Decision 5 의 '직접 의존성은 모두 기준을 충족' 을 httpx 0.28.1(직접 dev, 2024-12) 예외 반영으로 정정, 예외 표 httpx/httpcore 를 직접/전이 행으로 분리, 1년 경계 밖 누락분 referencing 0.37.0(2025-10-13)·mypy_extensions 1.1.0(2025-04-22) 추가, 36개 핀 전수 판정 방법(PyPI JSON·venv 메타데이터) 기록.
- 2026-10-24 T-009 (I-22 마무리, 문구만): Decision 1 opentelemetry-api 항목에 앱 팩토리의 텔레메트리 명시 비활성(`telemetry=` 전 항목 False, I-24)을 근거로 추가. 근거: 03 §4 금지(외부 SaaS 로 데이터 전송), NFR-005(외부 호출 0). 의존성 목록·핀 변경 없음.
