---
status: active
task: T-009
team: architecture
outcome: none
opened_at: 2026-10-24T00:09:45+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-009 [architecture] aidlc-run SKILL.md 루프 경계 로직(loop-start → 사이클마다 loop-check → 일시정지면 wait-resume 반복 → loop-end, Windows Python 안내) + ADR-004 확정(D-09·D-10 반영, R-01 "완화" 표기 + 메인 세션·Windows 미측정 단서, D-41) + SKILL.md wait-resume 기본 540 s 유지 + 20 §5 ControlView 실제 필드·resume 본문 `{}` 전용·"loop-status 없음 = ended + empty" 반영, `aidlc.py` docstring loop-* 줄 결정(I-37) + ADR-006(전이 opentelemetry-api·annotated-doc, 텔레메트리 외부 전송 없음 근거)·ADR-009(기본 로더 .pyc 부작용)·ADR-011 §4(`MonitorApp.__call__`)·§9(router.default + redirect_slashes=False)·20 §4(디렉터리 트리·정적 서빙 문구) 갱신(I-22·I-23) + 20 §5 health 행·ADR-001 §4 `data.app` 판정·contracts/README 내부 인터페이스 절(`app.state.warmup.progress()`) 갱신(I-27, D-34) + ADR-011·20 §5 에러 코드에 `TOO_MANY_STREAMS` 추가 — FR-005, I-02 | deps: T-008
- 완료 조건(DoD): SKILL.md 가 loop-cli.md 계약과 일치, R-01 결과 반영, I-02 해소 (출처: STM-0001 §5) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: FR-005(AC-6·7 스킬 쪽), stories/FR-005.md, contracts/loop-cli.md(§10 SKILL.md 규칙 요약), ADR-004, D-09·D-10·D-39~D-43, D-41(R-01 완화, 540 s 유지)
- 범위(tasks.md T-009): SKILL.md 루프 경계 로직 + ADR-004 확정 + I-02 + I-22/I-23(ADR-006·009·011·20 §4) + I-27(health 문서·ADR-001 §4·contracts/README 내부 인터페이스) + I-37(20 §5 ControlView·resume `{}`·aidlc.py docstring)
- 주의: `.claude/skills/aidlc-run/SKILL.md` 는 architecture 소유(40 §1.1), 실행 환경(CLAUDE.md: Windows python/py)

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
