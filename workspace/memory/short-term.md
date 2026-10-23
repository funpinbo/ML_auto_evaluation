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

## 4. 발견 사항 (LTM 후보)
- 결정: I-16 해결 — 대시보드 `next_seq = max(prev(없음/broken 0), loop-status.baseline_seq(없음/깨짐 0)) + 1`, 매 쓰기마다 두 파일 재판독(메모리 캐시 없음) + 프로세스 내 락으로 읽기-계산-쓰기 직렬화. CLI 판정은 `(seq > baseline_seq, state)` 만, 이전 seq 기억 안 함(재생성 파일의 seq 재사용 허용). 원칙 2·D-04·R-10 유지 (ADR-004 Decision 1.1, loop-cli §7)
- 패턴: 단일 작성자 파일에서 "단조 카운터" 가 필요하면 작성자가 상대 파일(읽기 전용)의 기준값을 하한으로 쓴다 — 작성자 수를 늘리지 않고 파일 손실에서 복구
- 이슈/리스크: Windows 에서 읽는 쪽이 파일을 연 순간 `os.replace` 가 PermissionError 가능 → 쓰는 쪽 짧은 재시도(권고 5회·50 ms), 대시보드는 실패 시 500 `CONTROL_WRITE_FAILED`. 대시보드 2개 동시 실행은 락 미공유로 seq 중복 가능(ADR-001 중복 실행 방지에 의존)
- 교훈: 상태 파일 손상 시나리오는 "삭제" 와 "손상" 을 따로 다뤄야 한다 — CLI 에서 없음 = 정상(대기 유지), broken = exit 2(계속 진행)로 동작이 다르다

## 5. 새로 발견된 Task (Task 후보)
- [product] stories/FR-005.md AC-18 문구 갱신: "다음 POST 는 이전 seq 를 0 으로 보고 새 파일을 쓴다(loop-cli §7, 단 STM §5 질문 참고)" → "다음 POST 는 `max(이전 seq(읽을 수 없으면 0), loop-status.baseline_seq) + 1` 로 새 파일을 쓰고 CLI 는 이를 새 요청으로 적용한다(loop-cli §7.1, SQ-5~SQ-7)". "질문 참고" 문구 제거(T-026 으로 해소). 선택: AC-18 에 "제어 파일 **삭제**는 broken 이 아니라 없음 — 대기 중이면 계속 대기, 다음 POST 로 복구(SQ-1~SQ-4)" 한 줄 추가. AC-1·AC-4·AC-10 의 "이전 seq + 1" 은 정상 경로에서 그대로 참이라 변경 불필요 — FR-005, I-16
- [backend] T-008 범위 확인: `services/control.py` 의 seq 계산을 loop-cli §7.1 대로(두 파일 재판독 + 프로세스 내 락 + Windows `os.replace` 재시도) 구현하고 §7.4 SQ-1~SQ-15 를 테스트로 옮긴다(T-008 DoD 의 "일시정지/재개 시나리오 테스트" 에 포함) — FR-005, I-16

## 6. 결과 & 인수인계
- 산출물(파일/PR): workspace/project/contracts/loop-cli.md (§7 재작성, §10), workspace/project/contracts/control.schema.json (`seq` description), workspace/project/adr/ADR-004-loop-control.md (Decision 1.1, Alternatives F·G, Consequences, 변경 이력)
- 검증 결과: `python3 aidlc/scripts/aidlc.py check project` GATE PASS. control.schema.json `json.loads` 정상. 계약 하위 호환: 파일 형식·필드·`schema` 값·CLI exit code/stdout 무변경, 바뀐 것은 대시보드 seq 계산(정상 경로에서는 기존 `prev+1` 과 동일). 코드 변경 없음 → 테스트 실행 대상 없음
- 남은 일: §5 [product] AC-18 문구 갱신, [backend] T-008 에서 §7.1 구현·SQ-1~SQ-15 테스트. LTM I-16 은 "해결(ADR-004 Decision 1.1)" 로 갱신 후보

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
