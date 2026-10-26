---
status: active
task: T-014
team: product
outcome: none
opened_at: 2026-10-26T00:00:00+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-014 [product] UAT(KPI-01 질문 3개, KPI-02 설치 리허설) + 문서화 — /aidlc-docs(OpenAPI export → docs/api, 사용자 가이드, monitor/README) | deps: T-013
- 완료 조건(DoD, tasks.md 원문): aidlc.py check docs 통과 + `docs/README.md` 존재(I-15), stories/FR-005.md AC-18 문구를 D-39 규칙으로 갱신, UAT 기록(...), A11 PO 화면 리뷰 후 FR-001 assumption 해제(D-21)
- **이번 STM 의 범위(사용자에게 설명·합의됨, 2026-10-26)**: 컨테이너에서 가능한 문서화 + AC-18 갱신 + 컨테이너 측정 가능한 참고값만. 사람/사용자 PC 가 필요한 UAT(KPI-01 스톱워치, K2-W/K2-U 리허설, R-1~R-3, statusLine 실세션 I-42, R-01 메인 세션·Windows 재측정, A11 PO 리뷰, I-18 PO 질문)는 수행하지 않고 uat-checklist §6 에 `미실행` 유지. 이를 STM §5 에 `[product] UAT 실기 (사용자 PC)` Task 후보로 남겨 P1 이 UAT 없이 완료되지 않게 한다. PASS 로 쓰지 말 것.

## 2. 로드한 컨텍스트
- 관련: SCOPE-01, KPI-01·02, FR-001~005 구현본(T-005~T-012), 10 §6 MVP 성공 기준, 40 §1.1("monitor/README.md = product; /aidlc-docs 산출물은 오케스트레이터가 작성, 내용 검토 A = product")
- 입력: workspace/project/uat/uat-checklist.md, stories/*, .claude/skills/aidlc-docs/SKILL.md, aidlc/templates/docs/{api-overview,user-guide}.md, docs/api/reference.md(자동 생성, 직접 편집 금지), workspace/project/ops/ 런북, run.py/run.sh/run.bat
- LTM: D-39(seq 발급·제어 파일 삭제=없음), D-21(A11), D-41(R-01 완화, 메인 세션·Windows 미측정), D-37(run.bat 실패 시 창 유지 기본값), I-15, I-18, I-32, I-42
- 규칙: 구현된 FR 만 사용자 가이드에. user/ 수정 금지. 코드 수정 금지(결함은 §5 [팀] 후보). docs/aidlc/ 수정 금지(프레임워크 문서)

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
