---
doc: ops-runbooks
layer: project
owner: ops
status: draft
source: user/02-development-standards.md§7, user/03-architecture-philosophy.md§7, workspace/project/20-architecture-analysis.md (QS-2, §4, §6), workspace/teams/ops/charter.md
---
# Ops 런북 — ML_miniops

> ops 팀 소유(workspace/teams/ops/charter.md §3). 03§7("관측성: 콘솔 로그만, 메트릭/트레이스/알림 불필요")·NFR-001(성능 목표 없음) 전제상
> 이 프로젝트에는 정식 SLO/SLI·알림 규칙·대시보드·용량 계획이 없다 — **N/A로 명시**하고 작성하지 않는다.
> ops 의 실질 범위는 아래 2가지로 축소된다: (1) QS-2 재시작 복구 절차, (2) 02§7 로그 레벨 규칙 준수 검증.
> infra 팀이 없음(40§2) — 로컬 실행 환경 전제(포트, 바인딩)도 이 문서가 흡수한다.

## 0. 범위가 아닌 것 (N/A)
| 항목 | 상태 | 근거 |
|------|------|------|
| SLO/SLI 수치 목표 | N/A | NFR-001 성능 목표 없음, 03§7 |
| 알림 규칙(PagerDuty 등) | N/A | 03§7 "알림 불필요" |
| 대시보드/메트릭 수집(Prometheus 등) | N/A | 03§7 "메트릭/트레이스 불필요" |
| 용량 계획 | N/A | 로컬 단일 사용자 전제(NFR-004), infra 없음 |

## 1. 로그 레벨 규칙 (02§7, 20§6) 매핑표

표준 `logging` 모듈, 콘솔 출력만 사용한다(다른 출력 경로/포맷터 없음).

| 레벨 | 트리거 조건 | 연계 데이터 상태 | 예시 메시지(권장 형식) |
|------|-------------|------------------|------------------------|
| ERROR | 평가 1건이 실행 중 예외로 실패 | `Evaluation.status = 'error'` | `evaluation failed run_id=<id> model_id=<id> metric=<m>: <exception>` |
| WARNING | 선택한 (model, metric) 조합이 `problem_type` 과 호환되지 않아 스킵됨 | `Evaluation.status = 'skipped_incompatible'` | `evaluation skipped (incompatible) run_id=<id> model_id=<id> metric=<m>` |
| INFO | Run 시작 / Run 완료, 평가(Evaluation) 시작/완료 | 상태 변화 없음(진행 로그) | `run started run_id=<id> combinations=<n>` / `run completed run_id=<id>` |

### 1.1 검증 체크리스트 (backend 구현 대상 코드: `app/eval/engine.py` 등)
- [ ] `status='error'` 로 레코드를 쓰는 모든 분기에서 동일 이벤트에 대해 `logging.error(...)` 가 호출되는가
- [ ] `status='skipped_incompatible'` 로 레코드를 쓰는 모든 분기에서 동일 이벤트에 대해 `logging.warning(...)` 가 호출되는가
- [ ] Run 시작/완료 시점에 `logging.info(...)` 가 각각 1회 호출되는가
- [ ] ERROR/WARNING 로그에 사후 추적 가능한 식별자(run_id, model_id, dataset_id, metric)가 포함되는가
- [ ] 콘솔 출력 외 별도 로그 수집기(파일 핸들러, 외부 로깅 서비스 등)를 추가하지 않았는가(03§7 범위 초과 방지)

### 1.2 현재 상태
- 이 Task(T-007) 시점에는 backend 의 평가 실행기(`app/eval/engine.py`, T-009 이후)가 아직 구현되지 않았다. 위 체크리스트는 **구현 전 규칙 명시**이며, 실행 코드 자체의 "검증"은 아니다.
- backend 가 로깅 호출을 구현하는 Task(T-009 이후, 평가 실행기 관련)의 **qa 리뷰 게이트에 ops 를 리뷰어로 추가**하거나, 별도 ops 리뷰 라운드에서 이 체크리스트 대비 재확인이 필요하다. ops 는 `app/**` 의 로깅 호출을 직접 작성하지 않는다(ops charter §2 "하지 않음").

## 2. QS-2 — 재시작 복구 절차 (NFR-002, 수동 확인)

### 2.1 전제
- 단일 FastAPI 프로세스 + SQLite 파일 영속 저장(20-architecture-analysis.md §3 선택 아키텍처 A). 별도 캐시/인메모리 상태를 신뢰하지 않고, 모든 Model/Dataset/Link/Run/Evaluation 레코드는 SQLite 파일에 커밋된다는 전제다.
- 자동화된 pytest 로 "프로세스 강제 종료 → 재시작"을 재현하기 어렵다(subprocess 기반 재기동 필요) — 수동 체크리스트로 남긴다.

### 2.2 절차
1. `python run.py` 로 ML_miniops 서버를 기동한다(§4.1 주의 사항 참고).
2. 브라우저 또는 API 호출로 Model 1개, Dataset 1개를 업로드하고 N:M 링크를 만든다.
3. Run 1건을 실행해 Evaluation 레코드가 최소 1개 이상 생성됨을 확인한다 (`GET /runs/{run_id}/results` 등).
4. 서버 프로세스를 **강제 종료**한다(정상 종료 아님 — 비정상 종료 시나리오 재현):
   - Windows: 작업 관리자에서 해당 python 프로세스 종료, 또는 `taskkill /PID <pid> /F`
   - Unix 계열: `kill -9 <pid>`
5. `python run.py` 로 재기동한다.
6. 재기동 후 아래를 `GET` 조회로 확인한다:
   - [ ] 2~3단계에서 만든 Model/Dataset/Link/Run/Evaluation 레코드가 그대로 조회됨
   - [ ] 신규 Run(새 조합)을 추가 실행할 수 있음(기존 데이터와 충돌 없이 동작)
7. 결과를 수행한 Task 의 STM §3 작업 로그에 통과/실패와 함께 기록한다(02§5 "실행하지 않은 검증을 통과로 쓰지 않는다").

### 2.3 실패 시 체크포인트
| 증상 | 1차 확인 지점 |
|------|---------------|
| 재기동 후 데이터가 비어 있음 | SQLite 파일 경로가 기동마다 동일한지(상대경로 기준 cwd 가 바뀌지 않았는지), DB 파일이 `.gitignore`/임시 디렉토리에 생성되지 않았는지 |
| 재기동 자체가 실패 | §4(로컬 실행 환경) 포트 충돌 여부, venv/의존성 설치 여부 |
| FK 참조 오류 | LTM I-03(연결마다 `PRAGMA foreign_keys = ON` 미설정 가능성) 재확인 |

## 3. 포스트모템 (장애 대응)
- 정식 포스트모템 템플릿은 과설계(03 원칙 1) — 1인 로컬 프로젝트 규모에 맞춰 생략한다.
- 장애 발생 시 최소 기록: STM 작업 로그에 "증상 → 원인 → 조치 → 재발 방지(코드/문서 변경)" 4줄만 남기면 충분하다.

## 4. 로컬 실행 환경 전제 (infra 팀 부재 흡수, 40§2)

### 4.1 주의 — `run.py` 경로 중복 (미해결, 아래 §5 참고)
이 저장소에는 서로 무관한 두 프로젝트가 공존한다(LTM D-13):
- **AI-DLC Monitor**(이 저장소 자체의 운영용 메타 도구): 저장소 루트의 `run.py` 가 이미 이 도구를 기동한다(`monitor/.venv` 사용, 기본 포트 8765, `/api/v1/health`).
- **ML_miniops**(이 프로젝트의 실제 평가 대상 앱): `40-team-composition.md` §1 과 `20-architecture-analysis.md` §4(실행 런처)·§6 모두 backend 소유 런처 파일을 **동일하게 `run.py`**로 지정하고 있고(기본 포트 8000 가정), ops charter §10 의 QS-2 테스트 명령도 `python run.py` 를 그대로 인용한다.
- 두 설계 문서가 같은 저장소 루트 경로(`run.py`)를 서로 다른 프로그램에 지정하고 있어, backend 가 ML_miniops 런처를 그대로 구현하면 기존 AI-DLC Monitor 런처를 덮어쓰게 된다. **이 문서의 §2.2 절차("python run.py")는 이 충돌이 해소된 이후에만 그대로 실행 가능하다.**
- ops 는 이 파일을 직접 고치지 않는다(backend/architecture 소유) — §5 에 Task 후보로 남긴다.

### 4.2 포트 충돌 대응
- 서버는 `127.0.0.1` 에만 바인딩한다(NFR-003, D-05). 외부 인터페이스 바인딩 옵션은 두지 않는다.
- 기본 포트가 이미 사용 중이면:
  1. 같은 ML_miniops 서버가 이미 떠 있는지 먼저 확인한다(health 엔드포인트 또는 아무 `GET` 호출로 응답 확인) — 중복 기동이면 기존 프로세스를 그대로 쓴다.
  2. 다른 프로그램이 포트를 점유 중이면 다른 포트로 재시도한다(참고: 저장소 루트 `run.py`/AI-DLC Monitor 가 이미 구현한 "포트 사용 중이면 다음 포트 자동 시도 + 자기 서버인지 health 로 판별" 패턴 — `choose_port`/`is_our_server`, `run.py` L250-303 — 을 ML_miniops 런처가 참고할 수 있다).
  3. Windows 에서 점유 프로세스 확인: `netstat -ano | findstr :<port>` → `taskkill /PID <pid> /F`(본인이 올린 프로세스가 맞는지 확인 후에만 종료).
- 포트를 바꾸는 것 외에 바인딩 주소(`127.0.0.1`)를 바꾸는 선택지는 없다(NFR-003, 사람 승인 필요 영역 — user/02§11).

## 5. 남은 일 / Task 후보
- `[architecture]` §4.1 의 `run.py` 경로 중복(동일 저장소 루트 파일명을 AI-DLC Monitor 와 ML_miniops 양쪽이 쓰도록 설계됨) 해소 필요 — ML_miniops 런처 파일 위치/이름 재지정(예: 별도 서브디렉토리) 또는 설계 문서 정정. 해소 전까지 §2.2 절차는 실제 코드로 재현 불가.
- `[backend]` T-009 이후 평가 실행기(`app/eval/engine.py`) 구현 시 본 문서 §1 로그 레벨 매핑표를 그대로 따르는지 ops 가 재확인 필요(현재는 구현 전이라 코드 대비 검증 불가).
