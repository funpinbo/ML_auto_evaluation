---
doc: contracts-index
owner: architecture
sources: [20 §5, ADR-003, ADR-004, ADR-010, ADR-011]
---
# 계약 (contracts/) 색인

팀 간 인터페이스의 단일 기준. 변경은 architecture 리뷰(하위 호환성 판정)를 거친다. JSON Schema 는 2020-12.

## 1. 문서 목록
| 파일 | 계약 | 흐름 (20 §5) | 근거 ADR | 작성(소유) |
|------|------|--------------|----------|-----------|
| `control.schema.json` | `.control.json` 형식 | F4 | ADR-004 | architecture |
| `loop-status.schema.json` | `loop-status.json` 형식 | F5 | ADR-004 | architecture |
| `claude-status.schema.json` | status line 스냅샷 형식 | F7 | ADR-003 | architecture |
| `loop-cli.md` | `aidlc.py loop-start/loop-check/wait-resume/loop-end` 인자·exit code·stdout·heartbeat·`baseline_seq` | F6 | ADR-004 | architecture |
| `sse-events.md` | `GET /api/v1/events` 이벤트·topic·keep-alive | F2 | ADR-008, ADR-010, ADR-011 | architecture |
| `openapi.json` | REST API 명세 (F1·F3, 봉투·에러 코드) | F1, F3 | ADR-011 | **backend 가 `monitor/backend/scripts/export_openapi.py` 로만 생성**. 직접 편집 금지. 바뀌면 같은 Task 에서 `aidlc/scripts/openapi_docs.py` 로 `docs/api/reference.md` 재생성 |

## 2. 런타임 파일 위치와 단일 작성자 (R-10)
| 런타임 파일 | 스키마 | 쓰기 (유일) | 읽기 | git |
|-------------|--------|-------------|------|-----|
| `workspace/memory/.control.json` | `control.schema.json` | **대시보드 backend** (`POST /api/v1/control/pause|resume`) | 루프 제어 CLI, 대시보드 | ignore |
| `workspace/memory/.monitor/loop-status.json` | `loop-status.schema.json` | **루프 제어 CLI** (`aidlc.py loop-*`) | 대시보드 | ignore |
| `workspace/memory/.monitor/claude-status.json` | `claude-status.schema.json` | **status line 스크립트** (`aidlc/hooks/statusline.py`) | 대시보드 | ignore |

공통 규칙:
- 파일마다 작성자는 하나. 다른 주체가 쓰는 변경은 리뷰에서 FAIL(ADR-004 §1).
- 쓰기는 같은 디렉터리 임시 파일 → `os.replace` 원자적 교체, UTF-8(BOM 없음), 시각은 RFC 3339 UTC(`+00:00`).
- 읽는 쪽은 파일 없음·깨짐·스키마 위반에 견딘다(대시보드는 패널 `meta.status`, CLI 는 `loop-cli.md` §2.1).
- 세 파일 모두 Hook 판정(`memory_cascade.py`) 대상이 아니며 `.gitignore` 에 `workspace/memory/.control.json`, `workspace/memory/.monitor/` 가 있어야 한다.
- 대시보드 프로세스의 쓰기 경로는 `.control.json` 하나뿐이다(원칙 2, QS-07).

## 3. 버전·호환성
- JSON 파일은 최상위 `schema` 정수(현재 1). 깨지는 변경(필드 삭제·이름 변경·의미/단위 변경·필수화) 시 +1 하고 읽는 쪽이 모르는 버전은 broken/`SOURCE_PARSE_ERROR` 로 처리한다.
- 스키마는 작성자를 검증한다(`additionalProperties: false`). 새 필드 추가도 스키마 갱신 + 리뷰가 필요하다(특히 `claude-status.json` 은 허용 필드 목록 = 보안 정책, security 리뷰 포함).
- 문서 계약(`loop-cli.md`, `sse-events.md`)은 frontmatter `schema_version` 과 각 문서의 호환성 절을 따른다.
