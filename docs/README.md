---
doc: docs-index
layer: docs
generated_at: 2026-10-26T00:00:00Z
spec: workspace/project/contracts/openapi.json
---
# AI-DLC Monitor 문서 인덱스

마지막 생성: 2026-10-26 (P1 / M1, 앱 버전 0.1.0). 이 문서들은 `/aidlc-docs` 단계에서 만들었고, 기능 설명의 정확성은 product 팀이 구현·스토리와 대조해 검토했습니다.

| 문서 | 내용 | 대상 독자 | 생성 방식 |
|------|------|-----------|-----------|
| [guide/README.md](guide/README.md) | 사용자 가이드 — 화면 읽는 법, 일시정지/재개, FAQ, 문제 해결, 용어 | AI-DLC 운영자(최종 사용자) | 직접 작성 (구현 완료된 FR-001~005·SCOPE-01·FR-008 최소만) |
| [api/README.md](api/README.md) | API 가이드 — 인증 없음·Host/쓰기 가드, 응답 봉투, 상태·에러 코드, SSE | 프론트엔드·연동·운영 담당 개발자 | 직접 작성 (명세·user/02 §6 근거) |
| [api/reference.md](api/reference.md) | REST API 레퍼런스 — 엔드포인트 11개, 파라미터, 스키마, curl 예시 | 개발자 | **자동 생성** (직접 수정 금지) |
| [../monitor/README.md](../monitor/README.md) | 설치·실행(`run.bat` / `run.sh` / `python run.py`)·첫 화면·보안 약속 | 처음 설치하는 사용자 | 직접 작성 |

## 사용한 명세
- OpenAPI 3.1: `workspace/project/contracts/openapi.json` (FastAPI 가 생성한 명세를 `monitor/backend/scripts/export_openapi.py` 로 내보냄, `--check` 로 최신 여부 확인)
- 레퍼런스 재생성: `python3 aidlc/scripts/openapi_docs.py render workspace/project/contracts/openapi.json -o docs/api`
- SSE 계약: `workspace/project/contracts/sse-events.md` (OpenAPI 에는 `text/event-stream` 응답으로만 기재됨)

## 운영 문서 (ops 팀)
| 문서 | 언제 보나 |
|------|-----------|
| [ops 색인](../workspace/project/ops/README.md) | 로컬 실행 환경 전제, `health` 응답 읽는 법 |
| [로그 규칙](../workspace/project/ops/logging.md) | 콘솔 로그 형식·금지 항목 |
| [서버가 안 뜸](../workspace/project/ops/runbooks/server-wont-start.md) | "서버가 시작되지 않았습니다" |
| [포트 사용 중](../workspace/project/ops/runbooks/port-in-use.md) | 8765 충돌 |
| [statusLine 미실행](../workspace/project/ops/runbooks/statusline-not-running.md) | 한도 %가 안 나옴 |
| [일시정지가 안 풀림](../workspace/project/ops/runbooks/pause-not-releasing.md) | `세션 없음` 등 |
| [사용량 집계가 느림](../workspace/project/ops/runbooks/warmup-slow.md) | `사용량 집계 중` 이 오래 감 |

(SLO 문서 `slo.md` 는 아직 없습니다.)

## 검증 상태
- 문서 Gate: `python3 aidlc/scripts/aidlc.py check docs`
- 레퍼런스 최신 여부: `export_openapi.py --check` → "openapi.json 최신", 재생성 결과와 `reference.md` 동일 (2026-10-26)
- 실서버 호출 확인: Linux 컨테이너에서 `GET /api/v1/health` 외 조회·오류 응답 확인 (자세한 내용은 [api/README.md §12](api/README.md))
- **미검증**: Windows 실행, 실제 Claude Code 세션에서의 한도 %·일시정지/재개(UAT 미실행, [UAT 체크리스트](../workspace/project/uat/uat-checklist.md) 참고)

## 프레임워크 문서
AI-DLC 프레임워크 자체의 사용 설명서는 [aidlc/README.md](aidlc/README.md) 입니다(이 프로젝트 문서가 아님).
