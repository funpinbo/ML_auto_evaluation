---
doc: architecture-analysis
layer: project
author: architecture-analyst
status: draft
source: 00-interpretation.md (GO), 10-business-analysis.md, 30-data-analysis.md, user/02@0.2, user/03@0.2
---
# 20. 아키텍처 분석

> 입력: 00-interpretation.md, 10-business-analysis.md, 30-data-analysis.md, user/02, user/03.
> 모든 판단은 user/03 의 **품질 속성 우선순위**로 채점합니다 (가중치 = 8 - 순위).

## 0. 핵심 설계 결론 (요약)
1. **모델 호출 인터페이스(00§3.1 #2, 10§7)**: 사용자 업로드 스크립트는 반드시 모듈 전역 함수 `predict(X) -> y` 를 노출해야 한다(ADR-002). 프레임워크(PyTorch/scikit-learn)는 메타데이터일 뿐, 평가 엔진은 프레임워크 분기 로직을 갖지 않는다 — 10-business-analysis §5 FR-004 가 예상한 "두 프레임워크 분기 처리" 노력을 제거해 "하루" 일정 리스크(Q9)를 완화한다.
2. **지표-문제유형 호환성(00§3.2 #10, 30§5.2)**: data-analyst 제안(`Model.problem_type` 사용자 직접 지정 + `METRIC_COMPATIBILITY` + `Evaluation.status`)을 **그대로 승인**한다(ADR-003). 다만 KPI-02 산식과 `error` 상태 추가는 본 문서에서 확정한다.
3. 두 결정 모두 **Compatibility Filter** 를 Evaluation Engine 과 분리된 모듈로 둬, FR-003/FR-005 고도화를 P2로 미뤄도 FR-001/002/004 핵심 파이프라인(P1)이 먼저 동작하는 구조를 보장한다(10§5~§6 완화안과 합치).

## 1. 품질 속성 시나리오
| ID | 품질 속성 | 자극 (Stimulus) | 환경 | 기대 반응 | 측정 기준 | 출처 (NFR) |
|----|-----------|----------------|------|-----------|-----------|-----------|
| QS-1 | 성능 | 사용자가 Run 버튼을 클릭해 소규모 모델×데이터 조합 다수를 동기 평가 요청 | 로컬 PC, 단일 사용자, 블로킹 REST 호출 | 조합들이 순차적으로 평가되고 Run 응답이 반환됨 | 명시적 지연 목표 없음(수치 없음) — 수동 확인으로 "참을 수 있는 시간" 내 완료되면 충족 | NFR-001 |
| QS-2 | 가용성/신뢰성 | 잘못된 모델 스크립트 업로드 등으로 서버 프로세스가 비정상 종료됨 | 단일 프로세스, SQLite 영속 저장 | `python -m app`(ADR-005) 재시작 시 기존 Model/Dataset/Run/Evaluation 데이터가 그대로 조회되고 신규 Run 수행 가능 | 재시작 후 GET 조회 API 로 이전 데이터 존재 확인(수동) | NFR-002 |
| QS-3 | 보안 | 외부 네트워크(같은 LAN 의 다른 기기 등)에서 서버 접근 시도 | 서버가 `127.0.0.1` 에만 바인딩 | 외부 요청이 도달하지 않음(연결 거절/타임아웃) | 코드 리뷰로 바인딩 주소가 `127.0.0.1` 고정인지 확인(수동) | NFR-003 |
| QS-4 | 확장성 | 동시에 여러 요청이 들어옴(설계상 발생 가정 안 함) | 단일 프로세스, 동시성 제어(락/큐) 없음 | 특별한 동시성 제어 없이 순차 처리되어도 요구사항 위반 아님 | 코드 리뷰로 락/워커풀 부재가 "의도된 생략"임을 확인 | NFR-004 |
| QS-5 | 컴플라이언스 | 사용자가 모델/CSV 업로드 | 업로드 파일에 PII 없음(확인됨) | 별도 마스킹/암호화 없이 로컬 파일시스템에 그대로 저장 | 코드 리뷰로 마스킹 로직 부재가 의도된 설계임을 확인 | NFR-005 |
| QS-6 | 유지보수성/개발속도 | 사용자가 `predict(X)->y` 계약을 지키지 않는 스크립트를 업로드 | Model Loader 가 업로드 시점에 `import` + `hasattr(module, "predict")` 검증 수행 | 업로드 즉시 `HTTPException`(4xx) 반환, 평가 실행 전에 실패를 알림(fail fast) | 업로드 API 가 계약 위반 시 4xx 반환 + 콘솔 ERROR 로그 확인 | FR-002, ADR-002 |
| QS-7 | 가용성/신뢰성 + 유지보수성 (KPI-02) | Run 버튼 클릭 시 일부 (model, metric) 조합이 `problem_type` 과 비호환 | Compatibility Filter 가 Evaluation Engine 과 분리된 모듈로 사전 검사 | 호환 조합은 `status=success` 로 값 계산, 비호환 조합은 `status=skipped_incompatible` 로 기록 + WARNING 로그, Run 전체는 에러 없이 완료 | Run 완료 후 `Evaluation.status` 분포 조회로 success/skipped_incompatible/error 수 확인, KPI-02 = success 모델 수 / 입력 모델 수 (ADR-003) | KPI-02, 00§3.2 #10, 30§5.2 |

## 2. 후보 아키텍처 비교
<!-- 최소 2개. 점수 = Σ(속성 점수 × 가중치), 가중치는 user/03 §2 순위로 산정: 가중치 = 8 - 순위 -->
- **가중치**: 개발속도(1위)=7, 유지보수성(2위)=6, 가용성/신뢰성(3위)=5, 확장성(4위)=4, 성능(5위)=3, 운영비용(6위)=2, 보안(7위)=1
- **후보 A — 단일 프로세스 모놀리스**: FastAPI 한 프로세스 안에서 API·평가 엔진·DB 접근이 모두 동작, 동기 REST, SQLite, in-process 모델 로더/실행기
- **후보 B — 모놀리스 + 평가 전용 자식 프로세스**: 웹 서버는 FastAPI 로 유지하되, 모델 `predict()` 실행만 `subprocess` 로 분리해 평가 중 크래시가 웹서버에 전파되지 않도록 격리
- **후보 C — 모놀리스 + 메시지 브로커 기반 비동기 작업 큐**: Celery/Redis 등으로 Run 실행을 비동기 워커에 위임 (03§4 "금지 기술"에 해당 — 비교를 위해 포함, 실격 처리)

| 품질 속성 (가중치) | 후보 A: 단일 프로세스 모놀리스 | 후보 B: 모놀리스+자식 프로세스 격리 | 후보 C: 모놀리스+메시지 브로커(Celery/Redis) |
|--------------------|---------|---------|---------|
| 개발 속도 (7) | 5 | 3 | 1 |
| 유지보수성 (6) | 5 | 3 | 2 |
| 가용성/신뢰성 (5) | 4 | 5 | 4 |
| 확장성 (4) | 2 | 3 | 5 |
| 성능 (3) | 3 | 3 | 4 |
| 운영비용 (2) | 5 | 4 | 1 |
| 보안 (1) | 3 | 3 | 3 |
| **합계** | **7×5+6×5+5×4+4×2+3×3+2×5+1×3 = 115** | **7×3+6×3+5×5+4×3+3×3+2×4+1×3 = 96** | **7×1+6×2+5×4+4×5+3×4+2×1+1×3 = 76 (03§4 금지 기술 위반으로 실격)** |

- 후보 C 는 "별도 메시지 브로커" 를 요구해 03§4 금지 목록과 직접 충돌하므로, 점수와 무관하게 **원칙 위반으로 제외**한다(원칙 1·2 위반).
- 후보 B(자식 프로세스 격리)는 가용성 점수는 A 보다 높지만, IPC(직렬화, 자식 프로세스 생명주기 관리) 구현 비용이 "하루" 일정(원칙 1, 개발속도 1위)과 충돌해 총점에서 A 에 못 미친다. QS-2(가용성)는 SQLite 영속화만으로도 "재시작 시 데이터 보존" 요구를 충족하므로, 프로세스 격리까지는 과설계로 판단한다(원칙 1 "과설계 금지").

## 3. 선택 아키텍처
- **선택: 후보 A — 단일 프로세스 모놀리스** (FastAPI 한 프로세스, 동기 REST, SQLite 저장, in-process 모델 로더/평가 실행기)
- **근거 (원칙 번호 인용)**:
  - 원칙 1 (단순함 우선): 프로세스 경계·IPC·브로커 없이 "하루" 안에 동작하는 가장 단순한 구성.
  - 원칙 2 (로컬 단일 프로세스): 01 NFR-002/004 와 직접 합치.
  - 원칙 3 (결과 비교 용이성 > 성능): 평가 결과를 SQLite 한 곳에 모아 pandas 로 바로 비교·시각화 가능.
  - 품질속성 1·2위(개발속도·유지보수성)에서 후보 A 가 최고점, §2 가중합계 115점으로 최고.
- **포기한 것 (트레이드오프)**:
  - 확장성(4위)·성능(5위)에서는 후보 B/C 가 이론상 더 유리하지만, 03§2 에서 두 속성 모두 하위 순위이고 01 NFR-004(동시 사용자 1명)·NFR-001(성능 목표 없음) 전제상 손실이 사실상 없음.
  - 모델 `predict()` 실행 중 크래시가 웹 서버 프로세스 전체에 영향을 줄 수 있음(후보 B 대비) — QS-6(업로드 시 contract 검증으로 fail fast)·QS-2(SQLite 영속화 후 재시작 복구)로 완화.

## 4. 컨텍스트 & 컴포넌트
```mermaid
flowchart LR
  user[사용자 브라우저] -->|HTTP sync REST| webui

  subgraph proc[단일 FastAPI 프로세스]
    webui[Web UI<br/>Jinja2 템플릿 + 바닐라 JS]
    api[API 라우터<br/>app/api]
    loader[모델 로더/어댑터<br/>predict(X)-&gt;y 계약 검증]
    compat[호환성 필터<br/>METRIC_COMPATIBILITY]
    engine[평가 실행기<br/>Evaluation Engine]
    metrics[지표 계산기<br/>accuracy/f1/rmse]
    repo[데이터 접근 계층<br/>Repository]
    viz[시각화 생성기<br/>pandas+matplotlib]

    webui --> api
    api --> loader
    api --> repo
    api --> engine
    api --> viz
    engine --> compat
    engine --> loader
    engine --> metrics
    engine --> repo
    viz --> repo
  end

  repo --> db[(SQLite 파일)]
  loader --> files[(로컬 파일 저장소<br/>workspace/data/)]
  api --> files
```

| 컴포넌트 | 책임 | 기술 | 소유 팀 (예정) | 의존 |
|----------|------|------|----------------|------|
| Web UI (템플릿+JS) | 업로드 폼, N:M 연결 화면, 지표 선택, Run 버튼, 결과 화면 렌더링 | Jinja2, 바닐라 JS | frontend | API 라우터 |
| API 라우터 (`app/api`) | REST 엔드포인트, 요청 검증(pydantic), 라우팅 | FastAPI | backend | 모델 로더, 데이터 접근 계층, 평가 실행기, 시각화 생성기 |
| 모델 로더/어댑터 (`app/eval/model_loader.py`) | 업로드된 `.py` 스크립트를 동적 import, `predict` 존재/호출 가능 여부 검증(ADR-002) | Python `importlib` | backend | 로컬 파일 저장소 |
| 호환성 필터 (`app/eval/compatibility.py`) | `problem_type` ↔ 선택 지표 호환성 검사, `METRIC_COMPATIBILITY` 매핑(ADR-003) | Python | backend | 데이터 접근 계층 |
| 평가 실행기 (`app/eval/engine.py`) | Run 1건에 속한 (model,dataset,metric) 조합 순회, 모델 호출→호환성 검사→지표 계산→결과 저장 오케스트레이션 | Python | backend | 모델 로더, 호환성 필터, 지표 계산기, 데이터 접근 계층 |
| 지표 계산기 (`app/eval/metrics.py`) | accuracy/f1/rmse 계산 | scikit-learn.metrics | backend | — |
| 데이터 접근 계층 (Repository) | Model/Dataset/Link/Run/Evaluation CRUD, SQLite 스키마 관리 | Python `sqlite3` | dba | SQLite 파일 |
| 로컬 파일 저장소 | 업로드된 CSV·모델 스크립트 원본 보관 (`workspace/data/`) | 파일시스템 | backend | — |
| 시각화 생성기 (`app/eval/visualize.py`) | Run 결과를 pandas 로 집계해 지표 비교(P1)·상관관계(P2) 그래프 생성 | pandas, matplotlib(Agg) | frontend | 데이터 접근 계층 |
| 실행 엔트리포인트 (`app/__main__.py`, `python -m app`) | `uvicorn` 구동, 호스트를 `127.0.0.1` 로 고정 (ADR-005: 저장소 루트 `run.py` 는 AI-DLC Monitor 전용이라 경로 충돌을 피해 `python -m app` 사용) | Python/uvicorn | backend | API 라우터 |

## 5. 주요 데이터 흐름 & 인터페이스
| 흐름 | 출발 → 도착 | 방식 (sync/async) | 계약 (API/이벤트 스키마) |
|------|-------------|-------------------|--------------------------|
| 모델 업로드 | Web UI → API 라우터 → 모델 로더 → 파일 저장소 + 데이터 접근 계층 | sync REST (multipart/form-data) | `POST /models` {file, name, framework, problem_type} → 201 {model_id} (ADR-002: `predict` 존재 검증 실패 시 4xx) |
| 모델 목록 조회 | Web UI → API 라우터 → 데이터 접근 계층 | sync REST (JSON) | `GET /models` → 200 [{model_id, name, framework, problem_type}] |
| 데이터셋 업로드 | Web UI → API 라우터 → 파일 저장소 + 데이터 접근 계층 | sync REST (multipart/form-data) | `POST /datasets` {file, name} → 201 {dataset_id} (CSV 파싱 가능 여부 검증, 마지막 컬럼 = 라벨 컨벤션, ADR-002 §3) |
| 데이터셋 목록 조회 | Web UI → API 라우터 → 데이터 접근 계층 | sync REST (JSON) | `GET /datasets` → 200 [{dataset_id, name}] |
| N:M 연결 | Web UI → API 라우터 → 데이터 접근 계층 | sync REST (JSON) | `POST /links` {model_id, dataset_id} → 201 / `GET /links` |
| 지표 선택 | Web UI (상태 보관) → Run 요청 payload 에 포함 | sync REST (JSON) | 별도 엔드포인트 없음 — `POST /runs` 요청의 일부 |
| Run 실행 | Web UI → API 라우터 → 평가 실행기(호환성 필터→모델 로더→지표 계산기)→ 데이터 접근 계층 | sync REST (JSON, 블로킹) | `POST /runs` {combinations: [{model_id, dataset_id, metrics:[...]}]} → 201 {run_id, evaluations:[{model_id,dataset_id,metric,status,value}]} |
| 결과 조회/시각화 | Web UI → API 라우터 → 데이터 접근 계층 → 시각화 생성기 | sync REST (HTML/JSON) | `GET /runs/{run_id}/results` → HTML(그래프 임베드) 또는 JSON(차트 데이터) |

## 6. 배포 & 인프라
- **환경**: 로컬 PC 단일 환경, dev/prod 구분 없음 (03§6)
- **배포 파이프라인 개요**: 없음. `python -m app` 실행 시 `app/__main__.py` 가 `uvicorn.run(app, host="127.0.0.1", port=8000)` 로 구동(ADR-005). 포트만 환경변수/인자로 조정 가능. 저장소 루트 `run.py` 는 이 프로젝트와 무관한 AI-DLC Monitor(포트 8765, `monitor/.venv`) 전용 파일이므로 ML_miniops 는 이 경로를 쓰지 않는다.
- **관측성**: 표준 `logging` 모듈, 콘솔 출력만. 레벨 기준은 02§7 그대로 사용 — ERROR=평가 실패(`status=error`), WARN=`status=skipped_incompatible`, INFO=Run 시작/완료. 메트릭/트레이스/알림 없음(03§7).

## 7. 기술 스택 확정안
| 영역 | 기술 | 버전 | user/02·03 근거 |
|------|------|------|----------------|
| Backend 언어/프레임워크 | Python + FastAPI + Uvicorn | Python 3.12 | 02§1 |
| DB | SQLite (표준 `sqlite3`, ORM 없이 직접 SQL) | 표준 라이브러리 내장 | 03§3·§4 (별도 DB 서버 없이 로컬 파일 하나), 03 선호 |
| 모델 실행 프레임워크 (사용자 스크립트 내부에서 사용) | PyTorch / scikit-learn | PyTorch 2.14.1 (2026-09-30 GA), scikit-learn 1.9.0 (2026-06-02) — 참고용 최신 안정판, 구현 시 `requirements.txt` 핀 버전 재확인 | 01 FR-002, 웹 검색 출처(아래) |
| 지표 계산 | scikit-learn.metrics (`accuracy_score`, `f1_score`, `mean_squared_error`) | scikit-learn 1.9.0 과 동일 | 02§1 Data 영역 |
| 시각화 | pandas `DataFrame.plot` + matplotlib(Agg 백엔드), PNG → base64 임베드 | pandas 최신 안정판(구현 시 고정) | 02§1 Frontend "Node 빌드 없음" 제약과 합치 — 클라이언트 차트 JS 라이브러리 불필요 |
| 프런트엔드 | Jinja2 템플릿 + 바닐라 JS | FastAPI 내장 Jinja2 | 02§1 |
| 테스트 | pytest (선택) | — | 02§5 |
| 린트/포맷 | ruff format + ruff check | — | 02§2 |

> 버전 출처: PyTorch — dev-discuss.pytorch.org "PyTorch 2.14.1 General Availability" (2026-09-30 공지, PyPI/download.pytorch.org 게시 확인). scikit-learn — PyPI 미러·Wikipedia 기준 1.9.0(2026-06-02 릴리스)이 최신 안정판으로 확인(2026-10-26 검색 기준, 그 이후 패치 유무는 구현 시 재확인 권장).

## 8. ADR 목록
| ADR | 제목 | 상태 | 파일 |
|-----|------|------|------|
| ADR-001 | 아키텍처 스타일: 단일 프로세스 모놀리스 선택 | Accepted | `workspace/project/adr/ADR-001-single-process-monolith.md` |
| ADR-002 | 모델 호출 인터페이스: `predict(X) -> y` 고정 계약 | Accepted | `workspace/project/adr/ADR-002-model-invocation-contract.md` |
| ADR-003 | 지표-문제유형 호환성 전략 및 KPI-02 산식 확정 | Accepted | `workspace/project/adr/ADR-003-metric-problem-type-compatibility.md` |
| ADR-004 | 동일 (model, dataset) 재업로드 시 신규 레코드 생성 정책 확정 | Accepted | `workspace/project/adr/ADR-004-model-dataset-reupload-policy.md` |
| ADR-005 | 실행 엔트리포인트를 `python -m app`(`app/__main__.py`)로 확정 — 저장소 루트 `run.py`(AI-DLC Monitor 전용)와의 경로 충돌 해소 | Accepted | `workspace/project/adr/ADR-005-launcher-entrypoint-path.md` |

## 9. 아키텍처 리스크 & 기술 부채 예상
| ID | 리스크 | 확률 | 영향 | 대응 |
|----|--------|------|------|------|
| R1 | 사용자 스크립트가 `predict(X)->y` 계약(ADR-002)을 지키지 않음 | 중 | 중 (FR-002/004 실패) | 업로드 시 import + `hasattr` 검증으로 fail fast(QS-6), 에러 메시지에 계약 명시, 문서(user-guide)에 예시 스크립트 제공 |
| R2 | 임의 Python 코드를 그대로 import/실행(샌드박싱 없음) | 낮음 | 낮음 (보안 7위, NFR-003 전제: 본인 작성 스크립트만 업로드) | 문서에 "본인이 작성/신뢰하는 스크립트만 업로드" 경고 문구. 샌드박싱은 범위 밖으로 명시(원칙 1 과설계 금지) — **예외 사유로 명시**: 03§8 "인증/암호화 불필요"의 로컬 신뢰 전제를 임의 코드 실행에도 그대로 확장 적용 |
| R3 | "하루" 일정 내 FR-003 호환성 필터/FR-005 상관관계 그래프까지 못 미침 (Q9) | 중 | 중 | Compatibility Filter·상관관계 그래프를 Evaluation Engine/기본 그래프와 분리된 모듈로 설계(§0, §4) → P1(핵심 파이프라인)만으로 먼저 end-to-end 동작, P2 로 점진 추가 |
| R4 | SQLite 동시 쓰기 경합 | 매우 낮음 (NFR-004: 동시 사용자 1명) | 낮음 | 별도 커넥션 풀/락 로직 불필요. 필요 시 WAL 모드만 고려(과설계 금지) |
| R5 | `predict()` 블로킹 호출로 동기 REST 요청이 길게 대기(대형 모델/데이터) | 낮음 (개인 소규모 실험 전제) | 낮음 (NFR-001 목표 없음) | 필요 시 프런트엔드에 "처리 중" 표시만 추가, 백엔드 구조 변경 없음 |
| R6 | 업로드 CSV의 "마지막 컬럼 = 라벨" 컨벤션(ADR-002 §3)을 사용자가 모르고 다른 형태로 업로드 | 중 | 중 (잘못된 X/y 분리로 평가 결과 왜곡) | 업로드 폼/문서에 컨벤션 명시, 업로드 시 열 수 ≥2 검증, 향후(P2) 라벨 컬럼명을 사용자가 지정할 수 있는 옵션 추가 가능하도록 스키마에 여지(컬럼명은 코드 상수로 분리) |
