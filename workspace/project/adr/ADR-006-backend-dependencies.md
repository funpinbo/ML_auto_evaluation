---
adr: 006
title: 백엔드 외부 의존성 — FastAPI·uvicorn(기본 설치)·Pydantic 만
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [CON-01, CON-02, 원칙 3, 03 §4, 03 §9, 02 §1, 02 §9]
---
# ADR-006. 백엔드 새 외부 의존성 (03 §9 필수)

## Context
- 02 §1: Backend = FastAPI + uvicorn, pip + requirements.txt. 02 §2: API 입출력은 Pydantic. 02 §9: 표준 라이브러리로 안 되는 경우만, MIT/Apache/BSD, 최근 1년 내 릴리스, 버전 고정.
- 원칙 3: 의존성 최소. 03 §4: watchfiles 는 "폴링보다 반응이 빠를 때만" 허용.
- `uvicorn[standard]` 는 httptools, python-dotenv, pyyaml, uvloop(비 Windows), watchfiles, websockets 를 추가로 설치한다(PyPI 메타데이터 확인).
- 2026-10-23 확인 최신: fastapi 0.161.1(MIT), uvicorn 0.54.0(BSD-3-Clause), pydantic 2.14.1(MIT, 2026-10-11), 모두 Python ≥ 3.10.

## Decision
1. **런타임 직접 의존성 3개**: `fastapi==0.161.1`, `uvicorn==0.54.0`(extras 없음), `pydantic==2.14.1`. 전이 의존성(starlette, pydantic-core, anyio, h11, click, typing-extensions, annotated-types 등)은 구현 Task 에서 venv 설치 후 `pip freeze` 결과로 `monitor/backend/requirements.txt` 에 전부 `==` 고정.
2. **개발 의존성**은 `requirements-dev.txt` 로 분리(사용자 설치 대상 아님): pytest, pytest-cov, httpx(TestClient 필요), ruff, pip-audit.
3. 표준 라이브러리로 직접 구현: SSE 직렬화, 파일 감시(ADR-008), frontmatter 파싱(Hook 함수 재사용, ADR-009), JSONL 집계, 런처, 로깅. YAML·dotenv·requests 등 추가 금지.
4. 새 런타임 의존성을 더하려면 새 ADR 필요(architecture 리뷰).

## Alternatives
- **`uvicorn[standard]`**: 성능 향상(uvloop, httptools)은 단일 사용자 로컬에서 의미 없고, 6개 패키지 + 네이티브 바이너리 설치로 설치 시간·실패 가능성 증가(원칙 1·3). 기각.
- **Starlette 만 사용(FastAPI 없이)**: 의존성 1개 감소지만 02 지정 스택·OpenAPI 자동 생성(02 §6) 포기. 기각.
- **Pydantic 생략(dataclass)**: FastAPI 가 Pydantic 을 필수로 요구하고 02 §2 위반. 기각.

## Consequences
- (+) 설치 패키지 10개 안팎, 모두 순수 Python 또는 주요 OS 휠 제공(pydantic-core) → 최초 설치 1분 내외 예상.
- (+) 라이선스 MIT/BSD/Apache 만.
- (−) uvicorn 기본 구현(asyncio + h11)은 처리량이 낮지만 성능은 5순위이고 요구 수준(단일 사용자)에서 충분.
- 릴리스 전 pip-audit(security 확인).
