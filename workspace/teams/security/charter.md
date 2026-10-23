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
- 프로젝트 적용: core. 20 §4 "보안 정책 (허용 필드 목록, Host/Origin 정책, `~/.claude` 접근 범위, 의존성 점검) → security", NFR-003, 00 Q2 허용 필드 규칙, QS-05·06·07, 30 §7 "개인정보 규칙은 security 리뷰" (40 §1)

## 2. 책임 범위
**소유 (Owns)**
- 위협 모델 (threat-model.md)
- 보안 요구·체크리스트
- 보안 스캔 정책 (SAST, 의존성, 시크릿, 컨테이너)
- 개인정보 처리 흐름도와 보존 정책 검증
- 개인정보 허용 필드 체크리스트 (구현 `privacy_filter.py` 는 backend 소유)

**하지 않음 (Not owns)**
- 기능 구현 (취약점은 담당 팀 Task 후보로)
- 법률 자문

- 프로젝트 적용 (실제 디렉토리/컴포넌트):
  - `workspace/project/security/threat-model.md` (STRIDE: LAN 접속, DNS rebinding/CSRF, 본문 노출, `~/.claude` 인증 파일)
  - `workspace/project/security/privacy.md` — **허용 필드 체크리스트**: `timestamp`, `requestId`, `message.model`, `message.usage` 4종, `isSidechain`, (디렉터리 해석 폴백 때만) `cwd`; `"usage":` 사전 필터; 응답·로그·캐시에 본문·경로·sessionId/requestId 원문 금지
  - `workspace/project/security/security-checklist.md` — Host 허용 목록, POST Origin·`Content-Type: application/json`, CORS 미설정, 쓰기 경로 = `.control.json` 1개, `~/.claude` 읽기 = `projects/<enc>/**/*.jsonl` + `settings.json` statusLine 키
  - **하지 않음:** 수집기·가드 코드(backend), 감사 도구 실행 자동화(cicd)

## 3. 산출물
- threat-model.md (STRIDE)
- security-checklist.md
- privacy.md (개인정보 항목·처리·보존·마스킹)
- 취약점 리포트

## 4. 입력 문서
- workspace/user/01-project-overview.md §6
- workspace/user/02-development-standards.md §8
- workspace/user/04-data-definition.md §6
- workspace/project/20-architecture-analysis.md

## 5. 담당 요구사항
| FR/NFR | 내용 | Phase |
|--------|------|-------|
| NFR-003 | 127.0.0.1 전용, 대화 본문 비접근·비저장 | P1 |
| CON-07 / 00 Q2 | 허용 필드 복사 규칙, `~/.claude` 접근 범위 | P1 (FR-004 리뷰 게이트) |
| QS-05 | Host/Origin 가드(BAD_HOST 400, FORBIDDEN_ORIGIN 403) | P1 |
| QS-07 | 대시보드 쓰기 = `.control.json` 1개 | P1 |
| 02 §8 | pip-audit/npm audit 결과 High 이상 0 | P1 말 / P2 말 |

## 6. 협업 인터페이스
- architecture: 보안 설계
- cicd: 보안 스캔 게이트
- data/ml: 개인정보·프롬프트 인젝션
- infra: IAM·네트워크

| 방향 | 상대 팀 | 계약 | 위치 |
|------|---------|------|------|
| 제공 | backend | 허용 필드·Host/Origin·접근 범위 체크리스트 | `workspace/project/security/privacy.md`, `security-checklist.md` |
| 제공 | qa | 본문 비노출 테스트 기준 | `workspace/project/security/privacy.md` |
| 협의 | architecture | 위협 모델 ↔ ADR-002·003·011 | `workspace/project/security/threat-model.md` |
| 사용 | cicd | 의존성 취약점 점검 결과 | `workspace/project/release/release.md` |

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
- 언어/프레임워크: Markdown 체크리스트, 검증 시 pytest·grep
- 디렉토리: `workspace/project/security/`
- 테스트 명령: `cd monitor/backend && python -m pytest` (본문 비노출·Host/Origin 테스트 포함), `pip-audit -r monitor/backend/requirements.txt`, `cd monitor/frontend && npm audit`
- 규칙: `~/.claude` 의 인증 파일은 리뷰 중에도 열지 않는다(02 §8). 실제 공격 코드를 저장소에 남기지 않는다
