---
status: active
task: T-026
team: architecture
outcome: done
opened_at: 2026-10-23T18:49:49+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-026 [architecture] loop-cli §7 / control.schema `seq` 보강: 루프 도중 `.control.json` 이 깨지거나 삭제된 경우 대시보드가 다음 seq 를 `max(이전 seq(없으면 0), loop-status.baseline_seq) + 1` 로 쓰는지 결정·명시(또는 FR-005 AC-18 복구 경로로 대체) — I-16, FR-005 | deps: T-004
- 완료 조건(DoD): loop-cli.md·control.schema·ADR-004 정합, FR-005 AC 와 모순 없음 (출처: STM-0006 §5) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: LTM I-16(루프 도중 .control.json 깨짐/삭제 → seq 1 ≤ baseline_seq → CLI 가 새 pause/resume 무시), D-04(파일당 쓰기 주체 1개), D-09·D-10(exit code, episode 상한), stories/FR-005.md(AC-18 복구 경로)
- 근거: workspace/project/contracts/loop-cli.md §7, control.schema.json `seq`, loop-status.schema.json `baseline_seq`, ADR-004

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->
- loop-cli §2.1·§3·§7, control/loop-status 스키마, ADR-004, FR-005 AC-1·4·10·18 확인. 원인: 대시보드 seq 계산이 제어 파일만 보고, CLI 는 `seq > baseline_seq` 만 적용.
- 대안 비교: (a) 대시보드가 `max(prev, loop-status.baseline_seq)+1` / (b) CLI 가 broken·없음 뒤에는 변경만으로 새 요청 판정 / (c) 시각 기반 id. (a) 채택 — 수정 1곳(대시보드), CLI·스키마 구조 무변경, D-04 유지(loop-status 는 읽기만). (b) 는 CLI 상태 저장(스키마 변경)·"없음" 정상 상태와 모호·1초 tick 사이 변화 누락, (c) 는 벽시계 비단조로 기각. "loop-status last-seen seq" 항목은 CLI 판정이 baseline 만 쓰므로 불필요(새 필드 = 스키마 변경)라 넣지 않음.
- contracts/loop-cli.md §7 재작성(7.1 발급 규칙, 7.2 CLI 규칙 명시, 7.3 경쟁 조건, 7.4 시나리오 SQ-1~SQ-15), §10 테스트 기준에 SQ 추가. control.schema.json `seq` 설명 갱신(JSON 파싱 확인). ADR-004 Decision 1.1, Alternatives F·G, Consequences, 변경 이력 추가.
- `python3 aidlc/scripts/aidlc.py check project` → GATE PASS.
- (security FAIL 조치 1회차) control.schema `seq`·loop-status.schema `baseline_seq` 에 `maximum: 9007199254740991` 추가(iterations_*·max_pause_sec 는 이미 상한 있음). loop-cli §2.1 엄격 정수 판정(`type(x) is int` + 범위, CLI·대시보드 공통, NaN 거부, 4300자리 ValueError → broken), §7.1 상한 초과 시 미기록 + 500 CONTROL_WRITE_FAILED, §7.3 락 타임아웃 2 s·락 안 작업 한정·임시 파일 삭제·고정 message(D-26 집합 안), §7.4 SQ-16~SQ-21, §10 갱신. ADR-004 Decision 1.1·변경 이력 갱신.
- 검증: monitor/.venv jsonschema(Draft 2020-12) check_schema 통과, examples 유효. 음성: seq 0/-1/2^53/true/"7"/1e20 거부, baseline -1/2^53/true/"7" 거부. `7.0` 은 두 스키마 모두 통과(확인) → 술어 필수 근거. 술어+parse_int(16자리 초과 거부) 데모: 7.0·8e0·true·2^53·4301자리 모두 거부/broken. `aidlc.py check project` 재실행.

## 4. 발견 사항 (LTM 후보)
- 결정: I-16 해결 — 대시보드 `next_seq = max(prev(없음/broken 0), loop-status.baseline_seq(없음/깨짐 0)) + 1`, 매 쓰기마다 두 파일 재판독(메모리 캐시 없음) + 프로세스 내 락으로 읽기-계산-쓰기 직렬화. CLI 판정은 `(seq > baseline_seq, state)` 만, 이전 seq 기억 안 함(재생성 파일의 seq 재사용 허용). 원칙 2·D-04·R-10 유지 (ADR-004 Decision 1.1, loop-cli §7)
- 패턴: 단일 작성자 파일에서 "단조 카운터" 가 필요하면 작성자가 상대 파일(읽기 전용)의 기준값을 하한으로 쓴다 — 작성자 수를 늘리지 않고 파일 손실에서 복구
- 이슈/리스크: Windows 에서 읽는 쪽이 파일을 연 순간 `os.replace` 가 PermissionError 가능 → 쓰는 쪽 짧은 재시도(권고 5회·50 ms), 대시보드는 실패 시 500 `CONTROL_WRITE_FAILED`. 대시보드 2개 동시 실행은 락 미공유로 seq 중복 가능(ADR-001 중복 실행 방지에 의존)
- 교훈: 상태 파일 손상 시나리오는 "삭제" 와 "손상" 을 따로 다뤄야 한다 — CLI 에서 없음 = 정상(대기 유지), broken = exit 2(계속 진행)로 동작이 다르다

## 5. 새로 발견된 Task (Task 후보)
- [product] stories/FR-005.md AC-18 문구 갱신: "다음 POST 는 이전 seq 를 0 으로 보고 새 파일을 쓴다(loop-cli §7, 단 STM §5 질문 참고)" → "다음 POST 는 `max(이전 seq(읽을 수 없으면 0), loop-status.baseline_seq) + 1` 로 새 파일을 쓰고 CLI 는 이를 새 요청으로 적용한다(loop-cli §7.1, SQ-5~SQ-7)". "질문 참고" 문구 제거(T-026 으로 해소). 선택: AC-18 에 "제어 파일 **삭제**는 broken 이 아니라 없음 — 대기 중이면 계속 대기, 다음 POST 로 복구(SQ-1~SQ-4)" 한 줄 추가. AC-1·AC-4·AC-10 의 "이전 seq + 1" 은 정상 경로에서 그대로 참이라 변경 불필요 — FR-005, I-16
- [backend] T-008 범위 확인: `services/control.py` 의 seq 계산을 loop-cli §7.1 대로(두 파일 재판독 + 프로세스 내 락 + Windows `os.replace` 재시도) 구현하고 §7.4 SQ-1~SQ-15 를 테스트로 옮긴다(T-008 DoD 의 "일시정지/재개 시나리오 테스트" 에 포함) — FR-005, I-16
- [architecture] T-026 security 리뷰 FAIL 조치: (1) control.schema.json `seq` 와 loop-status.schema.json `baseline_seq` 에 `maximum: 9007199254740991`(2^53-1) 추가, loop-cli §2.1·§7.1 에 "정수 = JSON 정수 리터럴만(bool·`7.0`·지수 표기 거부), 범위 밖은 broken / baseline 0" 명시, `max(prev, baseline)+1` 이 상한을 넘으면 쓰지 않고 500 `CONTROL_WRITE_FAILED`(파일 보존). (2) §7.3 에 락 획득 타임아웃(예: 2 s → `CONTROL_WRITE_FAILED`), `os.replace` 재시도 소진·쓰기 실패 시 임시 파일 삭제(P-12 임시 파일 0), 오류 메시지는 고정 문구(경로·예외 텍스트·seq 미포함) 명시. (3) §7.4 에 SQ 추가: loop-status `baseline_seq` 가 음수/문자열/bool/`7.0`/상한 초과/스키마 위반이면 baseline 0 으로 보고 스키마 통과 파일만 씀, prev 또는 baseline = 상한이면 500 + 파일 무변경, POST 연타(예: 50개 동시) 시 seq 연속·파일 schema 통과·락 타임아웃 응답, 재시도 소진 시 임시 파일 0·기존 파일 보존 — I-16, FR-005 AC-18·AC-20, threat-model A-4
- [backend] T-008: 위 보강을 `services/control.py`·CLI 판독(`type(x) is int` + 범위 검사, dashboard/CLI 동일 판정)에 반영하고 추가 SQ 를 테스트로 옮긴다 — T-026 security 리뷰

## 6. 결과 & 인수인계
- 산출물(파일/PR): workspace/project/contracts/loop-cli.md (§2.1 엄격 정수, §7 재작성·SQ-16~21, §10), workspace/project/contracts/loop-status.schema.json (`baseline_seq` maximum), workspace/project/contracts/control.schema.json (`seq` description, maximum 2^53-1), workspace/project/adr/ADR-004-loop-control.md (Decision 1.1, Alternatives F·G, Consequences, 변경 이력)
- 검증 결과: `python3 aidlc/scripts/aidlc.py check project` GATE PASS. control.schema.json `json.loads` 정상. 계약 하위 호환: 파일 형식·필드·`schema` 값·CLI exit code/stdout 무변경, 바뀐 것은 대시보드 seq 계산(정상 경로에서는 기존 `prev+1` 과 동일). 코드 변경 없음 → 테스트 실행 대상 없음
- 남은 일: §5 [product] AC-18 문구 갱신, [backend] T-008 에서 §7.1 구현·SQ-1~SQ-15 테스트. LTM I-16 은 "해결(ADR-004 Decision 1.1)" 로 갱신 후보

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
| security | FAIL | (OK) 단일 작성자 유지: 대시보드는 loop-status.json 읽기만, 쓰기 경로는 .control.json 1개(§7.1, SQ-15, W-01). 원자적 교체+프로세스 락으로 반쪽 파일·seq 유실 없음(§7.3). SQ-13(수동 편집 seq<baseline)은 max() 로 안전. 대시보드 2개는 ADR-001 중복 실행 방지 전제의 잔여 위험(seq 중복만, 작성자 종류 불변)으로 수용 가능. (FAIL) `seq`·`baseline_seq` 에 상한·엄격 정수 규칙이 없다: control.schema.json/loop-status.schema.json 모두 `maximum` 없음. 직접 확인(Python 3.13, jsonschema 4.26.0): JSON Schema 2020-12 는 `7.0` 을 integer 로 통과시킴 → baseline 7.0 이면 next_seq=8.0 이 쓰여 stdlib CLI(isinstance int) 와 판정이 갈릴 수 있음(pause 무시=무결성). 4300자리 넘는 정수는 json.loads/dumps 가 ValueError(int max_str_digits) → baseline 이 상한 근처면 대시보드 쓰기가 루프 끝까지 500 CONTROL_WRITE_FAILED 고착(가용성), 2^53 초과는 프론트 JS 정밀도 손실. 공격자=같은 사용자 로컬 프로세스라 심각도 L 이나 손상 입력 견고성 계약 누락. 부수: 락 대기 상한 없음(POST 연타 시 스레드풀 점유, 재시도 5×50 ms 가 락 안에서 실행), 쓰기 실패 시 임시 파일 삭제·CONTROL_WRITE_FAILED 메시지 고정(경로·예외문 미포함)이 §7.3 에 명시 안 됨, SQ 에 loop-status 손상(baseline 비정수·음수·float·초대형·스키마 위반)·POST 연타·쓰기 재시도 소진 시나리오 없음 | §5 [architecture] seq 상한·엄격 정수·락 타임아웃·실패 정리 계약 보강 + SQ 추가, [backend] T-008 구현 반영 |
