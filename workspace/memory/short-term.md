---
status: active
task: T-021
team: architecture
outcome: done
opened_at: 2026-10-23T09:46:49+00:00
---
# Short-term Memory

> **계층 4 (작업 단위).** Task 1개를 수행하는 동안의 작업 메모리. 한 번에 하나만 열린다.
> 수명: `status: active` 로 열고 → 작업 → `outcome` 기록 → `status: closed` 로 닫는다.
> 닫히는 순간 Hook 이 이 파일을 `archive/STM-xxxx_<task>.md` 로 옮기고 Long-term memory 갱신(cascade 1/3)을 요구한다.
> frontmatter 값: status(idle|active|closed) / outcome(done|partial|blocked)

## 1. 목표
- Task: T-021 [architecture] ADR-011 보강: (a) §5 에 "비-JSON Content-Type 변경 요청도 403 `FORBIDDEN_ORIGIN`" 한 줄 명시(D-14), (b) §4 Host 가드가 포트를 검사할지 결정 — 검사하면 구현 방식 명시, 안 하면 privacy.md N-02 포트 케이스를 선택 항목으로 유지 — NFR-003 | deps: T-002
- 완료 조건(DoD): ADR-011 에 두 항목 반영, 20 §8 에러 코드·privacy.md N-02 와 정합, LTM I-04·I-05 해소. (c) ADR-006 Decision 2 dev 의존성 목록에 jsonschema(+전이 4종, MIT) 추가 — I-08 해소 (출처: STM-0003 §5, STM-0004 §5; T-009 도 ADR-011 을 수정하므로 같은 파일 충돌 주의) + user/02 §10 공통 DoD

## 2. 로드한 컨텍스트
- 관련: NFR-003, LTM D-14(비-JSON Content-Type → 403), D-15(Origin 없는 로컬 POST 잔여 위험), I-04(Host 가드 포트 검사 미정), I-05, I-08(ADR-006 jsonschema)
- 근거 문서: workspace/project/adr/ADR-011, ADR-006, workspace/project/security/privacy.md (N-02 포트 케이스), 20 §8 에러 코드
- 주의: T-009 도 ADR-011 을 수정(TOO_MANY_STREAMS, I-02) — 이번에 함께 넣을 수 있으면 넣고 STM §4 에 기록

## 3. 작업 로그
<!-- 시간순으로 짧게. 무엇을 했고 무엇을 봤는지 -->
- charter·user/02·user/03·LTM(D-12, D-14, D-15, I-02, I-04, I-05, I-08)·ADR-011·ADR-006·20 §5·privacy.md N-02·sse-events.md 읽음. 20 §1 QS-05 가 이미 Host `127.0.0.1:<port>`/`localhost:<port>` 를 기준으로 적고 있어 ADR-011 §4(TrustedHostMiddleware, 포트 무시)가 QS-05 와 어긋나 있었음.
- (b) ADR-011 §4: 포트 검사로 확정. 근거 = 03 §2 보안 2순위, 03 §8, QS-05 일치, 원칙 3(새 의존성 없음). 구현 = `app/security.py` 순수 ASGI `HostGuardMiddleware`, 가장 바깥에 등록, 허용 `{127.0.0.1:<settings.port>, localhost:<settings.port>}` 소문자 정확 일치, 포트 생략·불일치·빈 Host·`[::1]`·끝 점 거부, 메시지에 Host 원문 미포함. `settings.port` 를 바인딩·Host·Origin 가드의 단일 출처로, 포트 0 금지, TestClient 는 `base_url="http://127.0.0.1:<port>"`. Alternatives 에 TrustedHostMiddleware 기각 사유 추가.
- (a) ADR-011 §5: 비-JSON Content-Type(누락 포함) → 403 `FORBIDDEN_ORIGIN`, 415 금지(계약 위반), `; charset=utf-8` 허용, `.control.json` 쓰기 전 거부. Alternatives 에 415 기각 추가.
- 추가: ADR-011 §9 에 HTTP 에러 코드 닫힌 집합 신설 + `TOO_MANY_STREAMS`(503). 20 §5 에러 코드 줄에도 `TOO_MANY_STREAMS`(503), "FORBIDDEN_ORIGIN 비-JSON 포함", "닫힌 집합, ADR-011 §9 와 동일(415 없음)" 반영. 20 §4 API 앱 셸 행의 "TrustedHost + Origin 가드" 를 "Host 가드(호스트+포트, 자체 ASGI) + Origin/Content-Type 가드" 로 수정.
- (c) ADR-006 Decision 2: jsonschema==4.26.0 + referencing 0.37.0, jsonschema-specifications 2025.9.1, rpds-py 2026.9.1, attrs 26.1.0(모두 MIT, `monitor/.venv` dist-info METADATA 의 License-Expression 로 확인) 추가, 근거(표준 라이브러리에 2020-12 검증기 없음, dev 전용이라 사용자 설치 무영향, 런타임 import 금지).
- 참고: 프롬프트·tasks 의 "20 §8 에러 코드" 는 실제로 20 §5 (API 표 아래) 에 있음. §8 은 ADR 목록.
- 검증: `python3 aidlc/scripts/aidlc.py check project` → GATE PASS (exit 0).

## 4. 발견 사항 (LTM 후보)
- 결정: Host 가드는 호스트+포트 정확 일치(`127.0.0.1:<bound port>`, `localhost:<bound port>`), 자체 순수 ASGI 미들웨어로 구현, TrustedHostMiddleware 미사용 — 근거 03 §2(보안 2순위)·03 §8·QS-05·원칙 3 (ADR-011 §4). I-04 해소.
- 결정: `settings.port` 가 uvicorn 바인딩·Host 가드·Origin 가드의 단일 출처, 포트 0 금지 (ADR-011 §4).
- 결정: 비-JSON Content-Type → 403 `FORBIDDEN_ORIGIN`, 415 금지를 ADR-011 §5 에 명시 (D-14 반영, I-05 해소).
- 결정: jsonschema 4.26.0 + 전이 4종(MIT) 을 ADR-006 dev 의존성으로 승인, 런타임 import 금지 (I-08 해소).
- 결정: HTTP 에러 코드 닫힌 집합을 ADR-011 §9 에 신설, `TOO_MANY_STREAMS`(503) 추가 — ADR-011·20 §5 반영함. → I-02 중 "TOO_MANY_STREAMS" 부분은 이번에 해소, loop-cli 결정(exit 64/1, episode 상한, NO_LOOP)의 ADR-004·20 §5 반영은 T-009 에 남음.
- 패턴: 미들웨어 테스트는 TestClient `base_url="http://127.0.0.1:<fixture port>"` 필수(기본 `testserver` 는 BAD_HOST).
- 이슈/리스크: `jsonschema-specifications 2025.9.1` 은 02 §9 "최근 1년 내 릴리스" 경계(2026-10-23 기준 약 13개월). dev·전이 전용이라 수용, T-007 고정 시 최신 확인.
- 이슈/리스크: privacy.md N-02 가 여전히 "포트 불일치 거부는 선택, TrustedHostMiddleware 는 포트를 안 봄" 으로 적혀 있어 ADR-011 §4 와 불일치 → [security] 후보(§5).
- 교훈: Task 문구의 문서 절 번호("20 §8 에러 코드")는 실제 위치(20 §5)와 다를 수 있으니 grep 으로 확인 후 수정한다.

## 5. 새로 발견된 Task (Task 후보)
- [security] privacy.md N-02 를 ADR-011 §4(T-021) 에 맞춰 갱신: 포트 불일치 `127.0.0.1:1`·포트 생략 `127.0.0.1`·`localhost:<다른포트>`·`[::1]:<port>`·`localhost.:<port>` 거부를 **필수** 항목으로 바꾸고 "TrustedHostMiddleware 는 포트를 보지 않으므로…" 문구 삭제. 정적 dist·SSE 요청도 포함. (I-04 의 security 측 마무리, T-005 전에)
- [backend] T-005 DoD 보강 참고: Host 가드는 TrustedHostMiddleware 가 아닌 자체 ASGI `HostGuardMiddleware`(ADR-011 §4), `settings.port` 단일 출처, 비-JSON 403 `FORBIDDEN_ORIGIN`. (T-005 에 이미 Host/Origin 가드가 있으므로 새 Task 가 아니라 DoD 문구 반영 후보)
- [cicd] T-007 런처: 실제 선택된 포트를 `--port`/환경변수로 서버 `settings.port` 에 넘기고 포트 0 사용 금지(ADR-011 §4) — T-007 DoD 문구 반영 후보.

## 6. 결과 & 인수인계
- 산출물(파일/PR): workspace/project/adr/ADR-011-api-contract-and-local-security.md (§4 재작성, §5 보강, §9 신설, Alternatives 2건, Consequences, 변경 이력), workspace/project/adr/ADR-006-backend-dependencies.md (Decision 2 jsonschema + 전이 4종, 변경 이력), workspace/project/20-architecture-analysis.md (§5 에러 코드 줄, §4 API 앱 셸 행)
- 검증 결과: `python3 aidlc/scripts/aidlc.py check project` GATE PASS (exit 0). 코드 변경 없음(문서·ADR 만) → pytest 해당 없음. openapi.json 미변경.
- 남은 일: privacy.md N-02 정합은 security 소유라 §5 후보로 넘김(DoD "privacy.md N-02 와 정합" 은 그 Task 완료 시 충족). I-02 의 loop-cli 결정 반영은 T-009. 리뷰 게이트: security(Host/Origin 위협 모델), qa 는 코드 변경 없음이라 선택.

## 7. 리뷰 기록 (리뷰 게이트)
<!-- /aidlc-run 이 리뷰 게이트 대상 팀을 리뷰 모드로 호출하면 각 팀이 한 줄씩 추가 -->
| 팀 | 결과 | 근거 | 필요한 조치 |
|----|------|------|-------------|
