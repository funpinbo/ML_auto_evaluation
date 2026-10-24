---
status: active
task: T-010
team: backend
outcome: none
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

## 4. 발견 사항 (LTM 후보)
- 결정:
- 패턴:
- 이슈/리스크:
- 교훈:

## 5. 새로 발견된 Task (Task 후보)
- 

## 6. 결과 & 인수인계
- 산출물(파일/PR):
- 검증 결과:
- 남은 일:

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
