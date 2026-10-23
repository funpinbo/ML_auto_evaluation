---
doc: data-definition
layer: user
version: 0.1
---
# 04. 데이터 정의서 (EDA 입력)

> **작성자: 사용자.** data-analyst Agent 가 EDA 를 수행할 데이터와 질문을 정의합니다.
> 아직 데이터가 없다면 1번 표에 `N/A (데이터 없음 — 생성 예정)` 이라고 적고 2번(예상 엔티티)을 채우세요. `{{ }}` = 필수.

## 1. 데이터 소스
| ID | 이름 | 유형 (CSV/DB/API/로그...) | 위치 | 규모 (행/용량) | 갱신 주기 | 소유자 | 민감도 |
|----|------|---------------------------|------|----------------|-----------|--------|--------|
| DS-01 | AI-DLC 메모리 | Markdown + frontmatter | `workspace/memory/` (plan, tasks, long-term, short-term, archive/) | 파일 수십 개, 수 MB 이하 | Task 마다 | AI-DLC Hook·오케스트레이터 | 내부 |
| DS-02 | AI-DLC 문서 Gate | CLI 출력 | `python3 aidlc/scripts/aidlc.py check/status` | 수십 줄 | 조회 시 | AI-DLC | 내부 |
| DS-03 | Claude Code 세션 기록 | JSONL 로그 | `~/.claude/projects/<프로젝트>/*.jsonl` 의 `message.usage`, `message.model`, `timestamp` | 세션당 수천 줄, 수십 MB 가능 | 메시지마다 | Claude Code | 개인정보 (대화 내용 포함) |
| DS-04 | Claude Code 상태 스냅샷 | JSON | status line 스크립트가 받은 JSON (`rate_limits`, `cost`, `context_window`) 을 파일로 저장 | 1 파일, 수 KB | 메시지마다 | Claude Code | 내부 |
| DS-05 | 팀 정의 | Markdown | `workspace/teams/*/charter.md`, `workspace/project/40-team-composition.md` | 팀 수만큼 | 팀 생성 시 | team-architect | 내부 |

## 2. 핵심 엔티티 & 관계
- Phase 1─N Task, Task 1─N STM 아카이브, STM 1─N 리뷰 기록, 팀 1─N Task
- Claude 세션 1─N 메시지(usage), 메시지는 시각으로 STM(opened_at ~ archived_at)에 매핑

### 2.1 주요 필드 (알고 있는 만큼)
| 엔티티 | 필드 | 타입 | 설명 | 비고 (PK/FK/개인정보) |
|--------|------|------|------|----------------------|
| usage 메시지 | timestamp | ISO 문자열 | 응답 시각 | |
| usage 메시지 | message.model | 문자열 | 모델 ID | |
| usage 메시지 | message.usage.input_tokens / output_tokens / cache_creation_input_tokens / cache_read_input_tokens | 정수 | 토큰 수 | |
| usage 메시지 | message.content | - | 대화 본문 | **개인정보 — 읽지 않음** |
| 상태 스냅샷 | rate_limits.five_hour.used_percentage, resets_at | 숫자, epoch 초 | 5시간 한도 사용률 | Pro/Max 에서만 존재 |
| 상태 스냅샷 | rate_limits.seven_day.used_percentage, resets_at | 숫자, epoch 초 | 7일 한도 사용률 | Pro/Max 에서만 존재 |
| 상태 스냅샷 | cost.total_cost_usd | 숫자 | 세션 예상 비용 | |
| STM 아카이브 | task, team, outcome, opened_at, archived_at | 문자열 | Task 실행 기록 | |

## 3. EDA 로 답하고 싶은 질문
1. 오늘, 그리고 현재 5시간 구간에 토큰을 얼마나 썼나 (입력/출력/캐시별)
2. 모델별 사용 비중은 어떤가
3. Task 하나를 수행하는 데 평균 토큰과 시간이 얼마나 드나 (팀별)
4. 캐시 적중률(cache_read / 전체 입력)은 얼마인가
5. 세션 기록 파일이 클 때(수십 MB) 집계에 걸리는 시간은 얼마인가

## 4. 알려진 데이터 품질 문제
- 기록에 usage 가 없는 줄(사용자 메시지, 도구 결과)이 섞여 있다
- 같은 응답이 여러 줄로 기록될 수 있어 중복 집계 위험 (requestId 기준 확인 필요)
- `rate_limits` 는 Pro/Max 구독에서, 세션 첫 응답 이후에만 존재한다

## 5. 데이터 활용 목적
- **기능과의 연결:** DS-01·02·05 → FR-001·002·003·007, DS-03·04 → FR-004·009·010, KPI-01 측정
- **ML/AI 사용 여부:** 없음

## 6. 개인정보 & 규정
- **개인정보 포함 여부:** 예 — DS-03 에 대화 내용(프롬프트, 응답, 파일 내용)이 들어 있다
- **처리 규칙:** usage·model·timestamp·requestId 필드만 추출하고 본문은 메모리에 올리지도, 저장·전송하지도 않는다
