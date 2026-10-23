---
status: active
task: T-008
team: backend
outcome: none
opened_at: 2026-10-23T18:58:50+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-008 [backend] 루프 제어 CLI(aidlc/scripts/loop_control.py + aidlc.py loop-start/loop-check/wait-resume/loop-end) + GET /control, POST /control/pause·resume + R-01 스파이크 — FR-005 | deps: T-001, T-005, T-020, T-026
- 완료 조건(DoD): exit code 계약(D-09: 0/10/20/2/64/1) 테스트·일시정지/재개/episode 상한 초과·NO_LOOP 시나리오 테스트 통과, 쓰기 결과를 contracts 스키마로 검증하는 테스트(jsonschema 를 dev 의존성으로 쓰면 ADR-006 갱신), loop-cli §2.1·§7.1~§7.3 구현(D-39·D-40: seq 발급 max+1, 엄격 정수 술어 CLI·대시보드 공유, 상한·락 타임아웃·임시 파일·고정 메시지) + SQ-1~SQ-21 전 시나리오 테스트, 스파이크 결과 STM 기록, privacy.md C-01~C-03·H-01~H-03 POST 통과 기대값을 실제 control 라우트 기준("400/403/422 아님", 루프 없음 409)으로 조정(I-25), T-005 하드닝(I-24: `server_header=False`, 텔레메트리 명시 비활성 + 테스트, 가짜 Hook 쓰기 함수 호출을 모든 workspace kind 에서 `calls == []` 단언, `asgi_http` receive 짧은 timeout), backend mypy 오류 5건(aidlc_reader.py:173, pipeline.py:294, security.py:203·204, static_files.py:86) 수정·`monitor/tools/check.py` 게이트 전 단계 통과(I-29·I-30) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련 FR: FR-005 (stories/FR-005.md AC-1~23, 화면 라벨 V1~V6), 01 §10 결정(같은 세션 대기 후 자동 재개)
- 계약: contracts/loop-cli.md (§2.1 엄격 정수, §7 seq 발급, SQ-1~SQ-21, exit 0/10/20/2/64/1, stdout 한 줄), control.schema.json, loop-status.schema.json, ADR-004 Decision 1.1
- LTM: D-04, D-09~D-11, D-26, D-39, D-40, I-24(하드닝), I-25(C/H POST 기대값), I-29·I-30(mypy 5건), R-01(Bash 호출 끊김 위험)
- 실행: `cd monitor/backend && ../.venv/bin/python -m pytest --cov=app -q -p no:cacheprovider`, 게이트 `monitor/.venv/bin/python monitor/tools/check.py`

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
