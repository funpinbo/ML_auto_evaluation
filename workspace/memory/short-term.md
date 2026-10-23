---
status: active
task: T-001
team: architecture
outcome: done
opened_at: 2026-10-23T07:36:23+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-001 [architecture] 파일 계약 3종(.control.json, loop-status.json, claude-status.json JSON Schema) + loop-cli.md(서브커맨드·exit code) + sse-events.md + contracts/README — FR-004, FR-005, FR-008 | deps: -
- 완료 조건(DoD): workspace/project/contracts/ 에 스키마·문서 존재, ADR-003·004·011 과 일치 + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련 FR: FR-004(사용량·스냅샷), FR-005(루프 제어), FR-008(SSE) — 00-interpretation.md §2
- 근거 문서: workspace/project/20-architecture-analysis.md §5, adr/ADR-003·004·010·011
- 팀 charter: workspace/teams/architecture/charter.md (contracts/ 소유, openapi.json 은 backend 가 export)
- LTM: D-03(스냅샷 경로), D-04(파일당 쓰기 주체 1개, exit 0/10/20/2), D-08(envelope·에러 포맷)

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->
- charter, user/02·03, LTM, 20 §4·§5·§9, ADR-003·004·010·011, SKILL.md 확인. contracts/ 디렉터리 없음, .gitignore 에 .control.json·.monitor/ 없음 확인
- control/loop-status/claude-status.schema.json(2020-12) 작성 — 필드는 20 §5 F4·F5·F7 / ADR-003 Decision 3·ADR-004 §1 그대로, additionalProperties false, loop-status 는 if/then 으로 state↔ended_reason·paused_since 불변식 표현
- jsonschema 4.26 로 check_schema + examples 통과, 음성 케이스(범위 밖 seq/max_pause_sec, 경로 필드 추가, 잘못된 session_hash 등) 거부 확인. format date-time 이 assertion 이 아니라 통과돼서 RFC 3339 pattern 추가 후 재검증 통과
- loop-cli.md(인자, 파일 판독 규칙, 서브커맨드별 동작, exit code, stdout, heartbeat, baseline_seq, 상태 전이, 스킬 규칙 요약, 테스트 기준), sse-events.md(연결, 이벤트 3종+keep-alive, topic 9개·감시 대상·M1 4개, 호환성), README.md(색인, 런타임 파일 위치·단일 작성자·gitignore) 작성
- 중간 schema 3종이 오케스트레이터 WIP 커밋 c1888f7 에 포함됨 → 이후 date-time pattern 추가분은 미커밋 상태
- `aidlc.py check project` GATE PASS, `python3 -m unittest discover -s aidlc/tests` OK

## 4. 발견 사항 (LTM 후보)
- 결정 (ADR 이 모호해서 정한 것, ADR-004 갱신 때 반영 후보):
  - [loop-cli] usage 오류 exit = 64 (argparse 기본 2 가 "control broken" 과 겹침). 예기치 못한 예외 = exit 1 → 스킬은 경고 후 계속. 루프를 멈추는 건 일시정지 요청뿐 (원칙 2 부작용 최소, QS-11)
  - [loop-cli] 제어 파일 broken 은 loop-start·loop-check 에서도 exit 2(계속 진행). 없음 = seq 0·running(정상). 스키마 위반(범위 밖 max_pause_sec 포함) = broken
  - [loop-cli] 일시정지 상한은 **일시정지 1회(episode) 기준** — paused_since 는 반복 wait-resume 호출을 넘어 유지, 재개 시 null. 루프 전체 누적 아님 (00 Q5 "최대 일시정지 2시간" 해석). max_pause_sec 는 판독 시점의 .control.json 값
  - [loop-cli] 활성 루프 없음(loop-status 없음/ended)에서 loop-check·wait-resume·loop-end 는 쓰지 않고 exit 0(NO_LOOP). loop-end 는 이미 ended 면 no-op(pause_timeout 보존), exit 20 후 loop-end 생략 가능
  - [loop-cli] --max-wait 범위 1~580(기본 540), loop-end 에 `--done <n>` 선택 인자 추가, loop-status 쓰기 실패는 exit code 에 영향 없음
  - [loop-cli] stdout = `AIDLC-LOOP <subcommand> <RESULT> key=value...` 한 줄, 진단은 stderr. 스킬은 exit code 로만 분기
  - [schema] run_id = uuid4 hex 32자, iterations_total 1~10(aidlc-run 최대), seq 첫 쓰기 = 1(최소 1), 시각 = RFC 3339 tz 포함(pattern 으로 강제), resets_at = 정수 epoch 초, transcript_dir_name = 경로 구분자 없는 단일 세그먼트
  - [heartbeat] running 상태에서는 heartbeat 나이로 세션 생존을 판정하지 않음(사이클 경계에서만 갱신). paused 에서만 120 s 기준
  - [SSE] ready = 데우기 완료(연결 시 이미 완료면 즉시 전송), 연결 첫 프레임 `retry: 5000`, id 미사용, 연결 상한 초과 = 503 `TOO_MANY_STREAMS`(**새 에러 코드** — 20 §5 에러 코드 목록·ADR-011 에 추가 필요), alerts topic 은 memory/tasks/usage 발행 시 파생 발행, 45 s 무프레임이면 프론트 재연결
- 패턴: 파일 계약은 "스키마 = 작성자 검증(additionalProperties false), 읽는 쪽은 관대 + schema 버전 불일치는 broken/SOURCE_PARSE_ERROR". JSON Schema 2020-12 의 format 은 기본 annotation 이라 시각은 pattern 으로 함께 강제한다
- 이슈/리스크: `.gitignore` 에 `workspace/memory/.control.json`, `workspace/memory/.monitor/` 미등록 — 런타임 파일이 커밋될 위험. SSE 503 TOO_MANY_STREAMS 는 ADR-011 에 없는 코드
- 교훈: jsonschema 로 examples + 음성 케이스를 돌려야 format 비강제 같은 구멍이 보인다

## 5. 새로 발견된 Task (Task 후보)
- [cicd] `.gitignore` 에 `workspace/memory/.control.json`, `workspace/memory/.monitor/` 추가 (contracts/README §2, ADR-003 §6·ADR-004 §1)
- [architecture] ADR-004 를 contracts/loop-cli.md 결정(exit 64/1, episode 기준 상한, NO_LOOP, loop-end --done)으로 갱신 + ADR-011·20 §5 에러 코드에 `TOO_MANY_STREAMS`(503) 추가 — R-01 스파이크 결과 반영 시 함께
- [backend] loop_control.py·control 서비스·watcher/SSE 구현 시 contracts/*.schema.json 으로 쓰기 결과를 검증하는 테스트 포함 (jsonschema 는 dev 의존성 후보 → 도입 시 ADR-006 갱신 필요, 아니면 수기 검증)

## 6. 결과 & 인수인계
- 산출물(파일/PR): workspace/project/contracts/{control.schema.json, loop-status.schema.json, claude-status.schema.json, loop-cli.md, sse-events.md, README.md} (schema 3종 초판은 WIP 커밋 c1888f7, 이후 수정·md 3종은 미커밋). openapi.json 미작성(backend export 대상)
- 검증 결과: jsonschema 4.26 Draft202012 check_schema 3/3, examples 6/6 통과, 음성 케이스 20건 거부 확인 / `python3 aidlc/scripts/aidlc.py check project` GATE PASS / `python3 -m unittest discover -s aidlc/tests` OK. pytest·ruff·run 스크립트는 코드 없음으로 해당 없음
- 남은 일: §5 후보(gitignore, ADR-004·011 반영, backend 구현 시 스키마 검증 테스트). 리뷰 게이트 대상: qa(계약 테스트 가능성), security(claude-status 허용 필드), backend(구현 가능성)

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
