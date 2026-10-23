---
rev: 0
last_merged_stm: 0
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

## 2. 확립된 패턴 & 컨벤션 (Patterns)
- 공통 DoD: 테스트 통과, ruff/eslint/타입 검사, frontend 변경 시 dist 재빌드, 문서 갱신, run 스크립트로 화면 확인 (user/02§10)
- Claude 기록에서는 usage·model·timestamp·requestId·isSidechain 만 읽는다. 실제 `~/.claude` 기록은 테스트에 쓰지 않는다 (user/02§5, 00 Q2)
- Windows 에서는 `python3` 대신 `python`/`py`, 셸 스크립트는 LF (CLAUDE.md 실행 환경)
- (예: 모든 API 응답은 `{data, error}` 래퍼 사용 (STM-0002))

## 3. 알려진 이슈 & 리스크 (Known Issues)
| ID | 내용 | 영향 범위 | 상태 | 출처 |
|----|------|-----------|------|------|

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

### ops
- (아직 없음)

### security
- (아직 없음)

### backend
- (아직 없음)

### frontend
- (아직 없음)

## 5. 교훈 (Lessons Learned)
- (반복하지 말아야 할 실수, 효과가 있었던 방법)

## 6. 용어집 (Glossary)
| 용어 | 정의 |
|------|------|
