---
doc: team-charter
layer: team
team: security
group: governance
tier: core
status: draft
---
# Security / DevSecOps 팀 Charter

> 팀 Agent(`.claude/agents/team-security.md`)가 작업 전 항상 읽는 문서입니다. `aidlc/teams/catalog.json` 기본값으로 생성되며,
> team-architect 가 프로젝트 분석서 근거로 구체화합니다 ("프로젝트 적용" 칸).
> 상위 문서와 충돌하면 user/02(개발 표준) > user/03(아키텍처 철학) > 이 문서 순으로 따릅니다.

## 1. 미션
위협 모델링과 보안 검증으로 서비스와 데이터를 보호하고 규정 준수를 증명한다.

- 생성 근거: 항상 — 보안·개인정보·규정 준수
- 프로젝트 적용: 보안 품질속성은 7위(최하위, 03§2)이고 인증/암호화는 불필요(03§8, NFR-003)하지만, NFR-003(localhost 전용 바인딩, QS-3), NFR-005(PII 없음 확인), R2(임의 Python 코드 실행 리스크, 20§9) 3가지는 명시적으로 확인·문서화가 필요한 항목이다. ml 팀이 없으므로(40§2) "임의 코드 실행"은 AI 안전성이 아니라 로컬 신뢰 전제(03§8 확장 적용)로 다룬다.

## 2. 책임 범위
**소유 (Owns)**
- 위협 모델 (threat-model.md)
- 보안 요구·체크리스트
- 보안 스캔 정책 (SAST, 의존성, 시크릿, 컨테이너)
- 개인정보 처리 흐름도와 보존 정책 검증

**하지 않음 (Not owns)**
- 기능 구현 (취약점은 담당 팀 Task 후보로)
- 법률 자문

- 프로젝트 적용 (실제 디렉토리/컴포넌트): `workspace/project/security/threat-model.md`, `workspace/project/security/privacy.md` (1일 프로젝트라 STRIDE 는 간략화해 R2/NFR-003/NFR-005 3가지에 집중).

## 3. 산출물
- threat-model.md: R2(임의 코드 실행 — 샌드박싱 없음, 03§8 로컬 신뢰 전제 확장 적용, 20§9), NFR-003(127.0.0.1 바인딩 코드 리뷰 확인)
- privacy.md: NFR-005 "개인정보 없음(확인됨)" 근거 재확인(04§6), 별도 마스킹/전송 제한 불필요 명시
- 취약점 리포트: 해당 없음(SAST/의존성 스캔 선택, 02§8) — 발견 시에만 작성

## 4. 입력 문서
- workspace/user/01-project-overview.md §6
- workspace/user/02-development-standards.md §8
- workspace/user/04-data-definition.md §6
- workspace/project/20-architecture-analysis.md

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| NFR-003 | 로컬 전용 바인딩(`127.0.0.1`) 검증 | P1 |
| NFR-005 | PII 없음 확인(이미 사용자 확인됨, 재검증 불필요) | 완료(변경 시 재확인) |
| (20§9 R2) | 임의 코드 실행 리스크 문서화·사용자 경고 문구 확인 | P1 |

## 6. 협업 인터페이스
- architecture: 보안 관련 설계 결정(바인딩, 코드 실행 신뢰 전제) 공유
- backend: 업로드/모델 로더 구현이 R2 경고 문구를 포함하는지 리뷰 (data/ml/infra 팀 부재 — 해당 없음, 40§2)

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| security → backend | NFR-003 바인딩 코드 리뷰 피드백 | 리뷰 코멘트(STM §7) | `workspace/memory/short-term.md` |

## 7. 팀 Definition of Done
- [ ] user/02 §10 공통 DoD
- [ ] High 이상 취약점 0
- [ ] 비밀값 하드코딩 0
- [ ] 개인정보 처리 항목이 privacy.md 와 일치

## 8. 품질 지표
- 미해결 취약점 수(심각도별)
- 취약점 해결 리드타임

## 9. 리뷰 게이트 (다른 팀 Task 검증)
- 대상: 인증·인가·입력 처리·개인정보·비밀값·외부 노출 엔드포인트·AI 프롬프트 입력을 다루는 Task
- 확인 항목:
  - [ ] OWASP Top 10 / LLM Top 10 관점 취약점이 없는가
  - [ ] 비밀값·개인정보가 노출되지 않는가
  - [ ] 최소 권한을 지켰는가

## 10. 팀 표준 (user/02 구체화)
- 언어/프레임워크: 해당 없음(문서+코드 리뷰). 비밀값 관리 N/A(외부 API 키 없음, 02§8)
- 디렉토리: `workspace/project/security/`
- 테스트 명령: 코드 리뷰로 `uvicorn.run(..., host="127.0.0.1", ...)` 고정 여부 확인(수동, QS-3). 의존성 취약점 점검은 선택(02§8) — 실행 시 `pip list --outdated` 수동 확인
