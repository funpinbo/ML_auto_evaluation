---
status: active
task: T-009
team: architecture
outcome: done
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
- [architecture] 대조 기준 읽음: contracts/loop-cli.md, `aidlc/scripts/loop_control.py`(exit 0/10/20/2/64/1, reason = done|blocked|no_task, max-wait 1~580 기본 540), `aidlc.py` loop-* 블록, `app/main.py`(MonitorApp.__call__ 가드 체인, router.default = StaticFallback, redirect_slashes=False, telemetry off), `security.py` wrap_guards 순서, `aidlc_reader._NoBytecodeLoader`(set_data no-op), `api/health.py`·`models/health.py`, `services/control.py`(LABELS V1~V6, ended_message, meta empty/error/partial), `run.py` probe_health/is_our_server, `contracts/openapi.json`(ControlData 24필드, ResumeRequest = 빈 object additionalProperties false, 본문 optional).
- SKILL.md: 기존 0~7단계 무변경. 머리말 한 줄 + "## 루프 경계" 절 추가(Python 명령 선택, exit code 로만 분기, `.control.json`/`loop-status.json` 쓰기 금지, 흐름 의사코드, 호출×exit code 분기표, 대기 진입 절차 timeout 600000·기본 540, exit 20 후 loop-end 생략, 대시보드 화면 라벨 6종 설명). "반복 & 보고" 에 경계 규칙 언급 추가.
- 드라이런(scratchpad 사본, 실제 CLI): loop-start 3 → 0, loop-check 1 → 0, 대시보드 흉내 pause seq 1 → loop-check 10, wait-resume --max-wait 2 → 10 ×2, 대기 중 resume seq 2 → 0, loop-check 2 → 0, loop-end done --done 3 → ENDED, 재호출 ALREADY_ENDED 0, `loop-end completed` → 64, ended 후 loop-check → NO_LOOP 0, 제어 파일 broken → loop-start 2·loop-check 2. 스크립트 디렉터리에 `__pycache__` 없음. exit 20(상한 600 s 이상)은 드라이런하지 않음 — backend test_loop_cli 가 시계 주입으로 검증.
- ADR-004: status accepted, Decision 2.1(D-09 exit 64/1·stdout·exit code 분기), 2.2(D-10 episode·NO_LOOP), 2.3(바이트코드), Decision 3 SKILL 과 일치(python3+Windows, 2·1 계속/64 중단, exit 20 후 loop-end 생략, reason 3종 + --done), Decision 7 R-01 결과(D-41, 메인 세션·Windows → T-014), 대안 B 재표기, Consequences, 변경 이력. D-39·D-40 은 Decision 1.1 에 이미 있어 변경 없음.
- ADR-009: Context "import 부작용 없음" 정정(기본 로더 .pyc), Decision 1 에 no-bytecode 로더 요구 + 검증 기준, 변경 이력 절 신설.
- ADR-011: §4 등록 방식 = `MonitorApp.__call__` 가드 체인(FastAPI 내부 미들웨어보다 바깥), §9 정적 서빙 = router.default StaticFallback + redirect_slashes=False, 변경 이력.
- ADR-006: Decision 1 에 `telemetry=` 전 항목 False 명시(I-24) 근거 추가 — opentelemetry-api·annotated-doc 은 STM-0012 에서 이미 기록됨, 변경 이력.
- ADR-001: Decision 2.4 중복 실행 판정 상세(200 + 봉투 data.app, 400 BAD_HOST·비 JSON → 다음 포트, 프록시 우회), 변경 이력. (Task 문구의 "§4" 는 실제로 Decision 2.4 — grep 확인)
- 20: §4 mermaid 앱 셸 라벨, 디렉터리 트리(실제 파일 + `(예정)` 표기), 앱 셸 행(가드 체인·StaticFallback·redirect_slashes), 루프 CLI 행(episode 상한); §5 F3(pause/resume 본문, resume `{}` 만, 409/200/500, D-39), F6(loop-cli 전체 exit code·NO_LOOP), health 행(D-34 실제 계약), control 행(ControlData 실제 필드, loop-status 없음 = ended + empty, D-43); §8 ADR-004 확정; §9 R-01 완화. TOO_MANY_STREAMS·METHOD_NOT_ALLOWED 는 이미 §5·ADR-011 §9 에 있음 확인.
- contracts/README: §4 프로세스 내부 인터페이스 절 신설(`app.state.warmup.progress() -> {state, progress}`, services, settings, source_status I-26).
- aidlc.py docstring(I-37): `main()` 이 인자 없을 때 `__doc__` 를 도움말로 출력하는데 loop-* 4줄이 없어 발견 불가 → 한 줄 추가로 결정. aidlc.py 는 수정하지 않고 §5 [backend] 후보로 남김.
- 검증: `python3 aidlc/scripts/aidlc.py check project` → GATE PASS(exit 0). `monitor/.venv/bin/python -m pytest monitor/backend/tests -q` → 811 passed, 1 warning(기존 StarletteDeprecationWarning). `python3 -m unittest discover -s aidlc/tests` → OK.

## 4. 발견 사항 (LTM 후보)
- 결정: ADR-004 확정(accepted) — R-01 완화, `--max-wait` 기본 540 유지, 대안 B 는 T-014 재측정 실패 시 후퇴안. 스킬은 exit 20 후 `loop-end` 를 부르지 않고(이미 ended·pause_timeout), exit 64 는 `loop-end blocked --done <i>` 후 중단, 2·1 은 경고 후 계속. loop-end reason 은 `done|blocked|no_task` 3종뿐(그 밖은 64)
- 결정: I-37 — `aidlc.py` 모듈 docstring 은 도움말로 출력되므로 loop-* 한 줄을 추가한다(구현은 backend 후보)
- 패턴: 스킬은 Bash 호출 끝에 `; echo "exit=$?"` 를 붙여 exit code 를 명시적으로 읽는다(stdout RESULT 토큰은 보고용)
- 패턴: ADR 은 구현 방식이 계약 결과와 같으면 "결과가 계약, 방식은 backend" 로 두되, 실제 방식(`MonitorApp.__call__`, `router.default`)을 구현 절에 한 줄로 고정해 문서-코드 불일치를 막는다
- 이슈/리스크: R-01 메인 세션·Windows 미측정(T-014). exit 20 경로는 실시간 드라이런 안 함(테스트로만 확인)
- 교훈: Task 문구의 절 번호("ADR-001 §4")와 실제 위치(Decision 2.4)가 다를 수 있다 — grep 으로 확인 후 고친다

## 5. 새로 발견된 Task (Task 후보)
- [backend] `aidlc/scripts/aidlc.py` 모듈 docstring(인자 없을 때 도움말로 출력)에 한 줄 추가: `aidlc.py loop-start|loop-check|wait-resume|loop-end  루프 제어 CLI (contracts/loop-cli.md, /aidlc-run 전용)` — I-37 (architecture 결정, T-009). 테스트 영향 없음 확인 후 architecture 리뷰
- [ops] 런북 `workspace/project/ops/runbooks/pause-not-releasing.md` 조치 절 정정: "세션 없음 / pause_timeout: 대시보드에서 재개 후 /aidlc-run" → V6·V1 에서는 재개 버튼이 비활성(FR-005 §2.2, control.py _BUTTONS)이고 loop-start 가 baseline=현재 seq 로 남은 요청을 무시하므로 재개 없이 `/aidlc-run <남은 수>` 만 실행하도록 고친다. SKILL.md 루프 경계(T-009)의 흐름·라벨 표를 출처에 추가 — T-009 ops 리뷰
- [ops] 같은 런북에 "사이클 진행 중(running) 세션이 닫힘 → 화면은 V3 `실행 중` 그대로(D-11, AC-17), 일시정지를 눌러도 V2 에서 멈춤" 판단·조치(`/aidlc-run <남은 수>` 재실행, loop-start 가 덮어씀) 항목 추가 — T-009 ops 리뷰

## 6. 결과 & 인수인계
- 산출물(파일/PR): `.claude/skills/aidlc-run/SKILL.md`, `workspace/project/adr/ADR-004-loop-control.md`, `ADR-009-…`, `ADR-011-…`, `ADR-006-…`, `ADR-001-…`, `workspace/project/20-architecture-analysis.md`, `workspace/project/contracts/README.md` (커밋 안 함)
- 검증 결과: check project GATE PASS / backend pytest 811 passed / aidlc unittest OK / SKILL 흐름 실제 CLI 드라이런 일치(§3). 코드 변경 없음, openapi.json·reference.md 변경 없음
- 남은 일: I-02·I-22·I-23·I-27·I-37 문서 쪽 해소(I-37 의 aidlc.py docstring 은 §5 [backend]). R-01 메인 세션·Windows 재측정은 T-014. 리뷰 게이트 대상: qa·ops(20 §4 aidlc-run 스킬 행 리뷰 팀), 필요 시 security(ADR-011 문구)

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
| ops | PASS | (실행 방식) SKILL 루프 경계: Bash `timeout: 600000`(도구 상한) 안에서 `wait-resume` 기본 540 s(loop_control.py MAX_WAIT_DEFAULT 540, 상한 580) = 60 s 여유, `run_in_background` 금지·exit code 분기표가 CLI 0/10/20/2/1/64 와 일치. (관측) 화면 라벨 6종이 services/control.py LABELS V1~V6·FR-005 §2.1 문자열과 동일, V2→V4 전환은 첫 wait-resume 이 paused 기록할 때(그 사이 V2 유지 = 정상). heartbeat 30 s(HEARTBEAT_SEC) + 540 s 마다 재호출 시 즉시 갱신 → 120 s(HEARTBEAT_STALE_SEC) 규칙에 여유 충분, 재호출 간 공백은 LLM 한 턴. 세션 종료 시 loop-status 는 paused 로 남아 V6 고정 → 다음 /aidlc-run 의 loop-start 가 새 run_id·baseline=현재 seq 로 덮어써 남은 pause 요청 무시(코드 확인). (설정) Python 선택 python3→python→py -3 은 CLAUDE.md 와 일치, run.bat(py -3→python, 3.11 확인)과 순서는 다르나 용도(스킬 Bash vs 더블클릭 cmd)가 달라 충돌 없음. (health 문서) 20 §5 health 행·ADR-001 D2.4·contracts/README §4 가 health.py/models/health.py 와 일치(app Literal 고정, dist, usage_warming 4상태·0~1, statusline 600 s stale, control missing 경고 없음, progress 예외→unknown+예외 종류만 로그). tests/ops 40 passed 실행. (롤백) 문서·스킬만 변경 → git revert 로 원복, SLO 영향 없음 | 비차단: ops 런북 `pause-not-releasing.md` 갱신(§5 [ops] 2건) |
