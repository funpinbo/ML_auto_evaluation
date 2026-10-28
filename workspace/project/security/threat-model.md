---
doc: security-threat-model
layer: project
owner: security
status: draft
source: user/01-project-overview.md§6, user/02-development-standards.md§8·§11, user/03-architecture-philosophy.md§2·§8, workspace/project/20-architecture-analysis.md§4·§6·§9, workspace/project/adr/ADR-002-model-invocation-contract.md, workspace/teams/security/charter.md
---
# 위협 모델 — ML_miniops

> security 팀 소유(charter §3). 보안 품질속성은 7위(최하위, 03§2)이고 인증/암호화는 명시적으로 불필요(03§8, NFR-003)하다.
> 전체 STRIDE 를 정식으로 적용하지 않고(과설계 금지, 03 원칙 1) **NFR-003(로컬 전용 바인딩) / NFR-005(개인정보 없음) / R2(임의 코드 실행, 20§9)** 3가지에만 집중한다.
> NFR-005 상세 체크리스트는 `workspace/project/security/privacy.md` 로 분리한다.

## 0. 범위가 아닌 것
| 항목 | 상태 | 근거 |
|------|------|------|
| 인증/인가 | N/A | NFR-003, 02§6 "인증/인가 없음" |
| 전송/저장 암호화 | N/A | 03§8 로컬 전용 전제 |
| 샌드박싱/정적분석(업로드 스크립트) | N/A, 설계상 명시적 제외 | 20§9 R2, ADR-002, 과설계 금지 |
| 의존성 취약점 스캔(SAST 등) | 선택, 이번 Task 범위 아님 | 02§8 "선택" |
| 비밀값 하드코딩 검사 | 해당 없음(외부 API 키/비밀값 자체가 없음) | 02§8 |

## 1. NFR-003 — 로컬 전용 바인딩(`127.0.0.1`)

### 1.1 요구사항
- 서버는 `127.0.0.1` 에만 바인딩하고 LAN/외부 네트워크로 노출하지 않는다(user/01§6 NFR-003, QS-3).
- 호스트를 바꾸는 옵션 자체를 두지 않는다(20§6: "포트만 환경변수/인자로 조정 가능").
- Agent 가 사람 승인 없이 외부 노출 설정을 변경하는 것은 금지된다(02§11).

### 1.2 코드 리뷰 결과 (수동 확인, 이 Task 시점)
- 저장소 루트 `run.py`(이 저장소 자체의 **AI-DLC Monitor** 런처, ML_miniops 와는 별개 — LTM I-08): `BIND_HOST = "127.0.0.1"` 상수로 고정(L36), `port_free`/`probe_health`/`server_command` 등 모든 바인딩·헬스체크 경로가 이 상수만 사용. 호스트를 바꾸는 CLI 인자/환경변수가 전혀 없음(`argparse` 에 `--port` 만 존재, L379-384). → **의도된 고정 바인딩 패턴 확인.**
- `monitor/backend/app/__main__.py`: `uvicorn.run(create_app(settings), host=BIND_HOST, port=settings.port, ...)` 호출 확인(L23-28), `BIND_HOST` 는 `app/config.py` 의 `BIND_HOST = "127.0.0.1"` 상수(L16)를 그대로 import. → 실제 uvicorn 바인딩 코드에서도 `127.0.0.1` 하드코딩 확인.
- **ML_miniops 자신의 런처**(20§4 "실행 런처(`run.py`)", 20§6 `uvicorn.run(app, host="127.0.0.1", port=8000)` 설계)는 이 Task 시점에 **아직 구현되지 않음** — 저장소 루트 `app/`(ML_miniops 스캐폴드, D-08)에는 `config.py`/`__main__.py`/`uvicorn.run` 호출이 없고, `run.py` 가 구동하는 대상은 ML_miniops 가 아니라 AI-DLC Monitor(`monitor/backend/app`) 이다(LTM I-08, 경로 충돌 미해소).

### 1.3 결론
- 설계 문서(20§4/§6, QS-3) 수준에서는 `127.0.0.1` 고정 바인딩이 명확히 명시돼 있고, 같은 저장소 안에 이미 존재하는 동일 패턴(AI-DLC Monitor 런처)은 실제 코드로도 고정 바인딩·호스트 변경 옵션 없음을 확인했다 — **PASS(설계 수준)**.
- ML_miniops 자체의 바인딩 코드는 아직 존재하지 않아 **코드 리뷰로 실측 검증은 불가능**(검증 대상 코드 없음). I-08(run.py 경로 충돌)이 해소되고 backend 가 런처를 구현한 뒤 이 섹션을 재검증해야 한다.
- Agent는 바인딩 주소를 바꾸는 어떤 변경도 수행하지 않았다(02§11 — 사람 승인 필요 영역, 손대지 않음).

### 1.4 재검증 조건 (Task 후보)
- `[architecture]` I-08(run.py 경로 충돌) 해소 필요 — 이미 LTM/ops runbooks.md §5 에 기록된 미해결 Task.
- `[backend]` ML_miniops 런처(`uvicorn.run(..., host="127.0.0.1", ...)`) 구현 완료 후 `[security]` 가 실제 코드로 본 섹션을 재검증해야 한다.

### 1.5 재확인 (T-019, 2026-10-27)
- 저장소 상태를 다시 읽어 §1.2/§1.3 의 결론이 여전히 유효한지 확인했다: 저장소 루트 `app/`(ML_miniops 스캐폴드)에는 여전히 `run.py`/`config.py`/`uvicorn.run` 호출이 없다(`app/api/__init__.py`, `app/web/__init__.py` 만 존재, `app/web/{static,templates}` 는 `.gitkeep` 뿐). `tasks.md` 의 `T-033`(architecture, I-08 경로 충돌 해소)과 ML_miniops 런처 구현을 맡을 backend Task 는 모두 아직 미착수(미생성)이다.
- 저장소 루트 `run.py` 는 여전히 AI-DLC Monitor 런처(포트 8765, `monitor/backend/app`)이며 `BIND_HOST = "127.0.0.1"` 고정, 호스트 변경 옵션 없음(§1.2 와 동일, 재확인됨).
- **결론: §1.3 의 "설계 문서 수준 PASS, 실측 검증 대상 코드 없음"이 그대로 유지된다.** T-019 의 DoD("run.py 코드 리뷰로 바인딩 주소 확인")는 ML_miniops 런처 코드가 존재하지 않아 문자 그대로 충족할 수 없다 — 이는 이미 T-008 시점(LTM I-10)에 예견된 상황이고 이번 재확인으로도 바뀌지 않았다. `T-034`(deps: T-033, T-012, T-019, T-020)가 실측 재검증을 맡도록 이미 설계돼 있으므로, 이 섹션의 실측 검증은 그 때까지 보류한다(02§5 — 실행하지 않은 검증을 통과로 쓰지 않는다).

## 2. R2 — 업로드된 임의 Python 코드 실행 (샌드박싱 없음, 20§9)

### 2.1 리스크 정의
사용자가 업로드한 `.py` 모델 스크립트를 `importlib` 로 그대로 import(=실행)한다. 샌드박싱·정적분석이 전혀 없다 — 일반적으로는 임의 코드 실행(RCE) 취약점이지만, 이 프로젝트는 **의도된 예외**로 수용한다.

### 2.2 수용 근거 (예외 사유, 그대로 유지)
- 03§8: "로컬 전용이 핵심 원칙, 그 외 인증/암호화 불필요" — 이 로컬 신뢰 전제를 임의 코드 실행에도 그대로 확장 적용한다(20§9 R2, ADR-002 "보안 관련 예외 사유" 명시).
- 전제: **본인이 작성/신뢰하는 스크립트만 업로드**한다(NFR-003 로컬 전용 + 01 NFR-003). ml 팀이 없어(40§2) AI 안전성 관점이 아니라 이 로컬 신뢰 전제로만 다룬다(security charter §1).
- 샌드박싱/코드 정적분석은 범위 밖으로 명시 제외(원칙 1 과설계 금지, 20§9).

### 2.3 경고 문구 요구사항 확인
- 설계/요구사항 문서에는 경고 문구 요건이 이미 명시돼 있다:
  - 20§9 R2: "문서에 '본인이 작성/신뢰하는 스크립트만 업로드' 경고 문구"
  - ADR-002: "본인이 작성/신뢰하는 스크립트만 업로드한다는 가정 하에 허용되는 리스크로 명시적으로 수용"
  - `workspace/project/stories/FR-002.md` L68: 동일 전제를 Out-of-scope 근거로 재인용
- **실제 구현 확인(이 Task 시점)**: 업로드 화면(`app/web/templates`, `app/web/static`)은 아직 플레이스홀더(`.gitkeep`)뿐이고, tasks.md 기준 `T-012 [frontend] 업로드 화면 구현`이 아직 미완료(`[ ]`)다. 따라서 경고 문구가 실제 업로드 폼이나 사용자 문서에 노출되는지는 **코드/문서가 존재하지 않아 검증 불가**(실행하지 않은 검증을 통과로 쓰지 않는다, 02§5).

### 2.4 결론 및 재검증 조건 (Task 후보)
- 설계 문서 수준에서는 경고 문구 요건이 일관되게 반영돼 있음 — **PASS(설계 수준)**.
- `[frontend]` T-012(업로드 화면 구현) DoD 에 "본인이 작성/신뢰하는 스크립트만 업로드" 경고 문구 노출을 포함해야 한다.
- `[product]` 사용자 가이드/문서(T-020 등 P1 문서 갱신)에도 동일 경고 문구를 포함해야 한다.
- 두 Task 완료 후 `[security]` 가 리뷰 모드로 실제 화면/문서에 경고 문구가 노출되는지 재확인 필요.

## 3. NFR-005 — 개인정보
`workspace/project/security/privacy.md` 참고. 결론만 요약: 04§6 "개인정보 포함 여부: 아니오(확인됨)" 이 이 Task 시점까지 유지되며, 업로드 대상(모델 스크립트 + CSV)이 변경되지 않았으므로 재검증 불필요.

## 4. STRIDE 간략 매핑 (참고용, 상세 분석 생략)
| STRIDE | 이 프로젝트에서의 취급 | 근거 |
|--------|------------------------|------|
| Spoofing | N/A — 인증 없음(의도) | NFR-003 |
| Tampering | 수용된 리스크 — 업로드 스크립트/CSV 변조는 로컬 신뢰 전제로 범위 밖 | 03§8, 20§9 R2 |
| Repudiation | N/A — 단일 사용자, 감사로그 요구 없음 | 03§7 |
| Information Disclosure | 낮음 — 외부 노출 없음(§1), PII 없음(§3) | NFR-003, NFR-005 |
| Denial of Service | 낮음 — 단일 사용자 로컬 전용, 공격 표면 사실상 없음 | NFR-004 |
| Elevation of Privilege | 수용된 리스크 — R2(§2)와 동일 범주, 별도 권한 상승 경로 없음(프로세스 권한=사용자 권한) | 20§9 R2 |

## 5. 결론
- NFR-003: 설계 수준 PASS, 실측은 ML_miniops 런처 구현 후 재검증(§1.4) — T-019(2026-10-27) 재확인 결과도 동일(§1.5), T-034 로 이전.
- R2: 설계 수준 PASS, 경고 문구의 실제 노출은 T-012/T-020 구현 후 재검증(§2.4).
- NFR-005: PASS, 변경 없음 확인(privacy.md).
- 발견된 신규 보안 결함 없음. High 이상 취약점 0, 비밀값 하드코딩 0(해당 항목 자체가 없음, 02§8).
