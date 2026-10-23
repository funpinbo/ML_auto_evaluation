# 4. 팀 운영

## 팀 카탈로그 (`aidlc/teams/catalog.json`)
실제 조직에서 운영되는 17개 팀입니다. **필수(core) 6팀**은 모든 프로젝트에 생성되고, 나머지는 분석서에 근거가 있을 때만 생성됩니다.

| 그룹 | id | 팀 | 구분 | 리뷰 게이트 대상 (요약) |
|------|----|----|------|------------------------|
| 기획·설계 | `product` | Product (PO/PM) | **필수** | FR 동작을 바꾸는 Task |
| | `design` | UX/UI Design | 조건부 | UI 변경 |
| | `architecture` | Architecture | **필수** | 새 컴포넌트·의존성·데이터 모델·계약 변경 |
| 개발 | `backend` | Backend | 조건부 | — |
| | `frontend` | Frontend | 조건부 | — |
| | `mobile` | Mobile | 조건부 | — |
| | `integration` | 외부 연동 | 조건부 | — |
| | `dba` | Database | 조건부 | 스키마·마이그레이션 |
| 데이터·AI | `data` | Data Engineering | 조건부 | 데이터 스키마·이벤트·로그 포맷 |
| | `analytics` | Analytics / BI | 조건부 | 트래킹 이벤트·KPI 계산 |
| | `ml` | ML/AI (LLM·RAG) | 조건부 | 프롬프트·모델·검색 설정 |
| 품질 | `qa` | **QA / Test** | **필수** | **코드를 바꾸는 모든 Task** |
| 플랫폼·운영 | `cicd` | CI/CD | **필수** | 빌드·의존성·워크플로 |
| | `infra` | Cloud Infra | 조건부 | 리소스·네트워크·IAM |
| | `ops` | Ops / SRE | **필수** | 배포·설정·계측·외부 의존성 |
| 보안·거버넌스 | `security` | Security / DevSecOps | **필수** | 인증·입력·개인정보·비밀값·프롬프트 입력 |
| | `docs` | Technical Writing | 조건부 | 사용자에게 보이는 동작·공개 API |

전체 정의 보기: `python3 aidlc/scripts/aidlc.py teams`

## 팀 하나가 가진 정의
| 필드 | 쓰이는 곳 |
|------|-----------|
| `mission`, `owns`, `not_owns` | charter §1~2 — 수정 가능한 범위의 경계 |
| `deliverables`, `inputs` | charter §3~4 — 무엇을 만들고 무엇을 읽는가 |
| `collaborates` | charter §6 — 팀 간 협의 대상 |
| `dod`, `metrics` | charter §7~8 — 완료 판정, 품질 지표 |
| `review_gate` | charter §9 — 다른 팀 Task 를 검증하는 조건과 확인 항목 |
| `guidance` | 팀 Agent 의 "팀 특화 지침" |
| `create_when` | 조건부 팀 생성 판단 기준 |

## 팀 만들기
```bash
python3 aidlc/scripts/aidlc.py new-team --core            # 필수 6팀
python3 aidlc/scripts/aidlc.py new-team ml integration    # 조건부 팀 여러 개
python3 aidlc/scripts/aidlc.py new-team growth "Growth"   # 카탈로그 밖 팀 (빈 항목은 team-architect 가 채움)
```
생성물: `workspace/teams/<id>/charter.md`, `.claude/agents/team-<id>.md`. 이미 있는 파일은 덮어쓰지 않습니다.

## 팀 Agent 의 두 모드
| | 작업 모드 | 리뷰 모드 |
|-|-----------|-----------|
| 언제 | 자기 팀 Task 를 수행할 때 | 다른 팀 Task 가 리뷰 게이트 대상일 때 |
| 수정 | charter "소유" 범위 안에서만 | **아무것도 수정하지 않음** |
| 기록 | STM §3 작업 로그, §4 발견, §6 결과, `outcome` | STM §7 리뷰 기록 `PASS/FAIL + 근거 + 조치` |
| 범위 밖 필요 | STM §5 에 `[팀id]` Task 후보로 | FAIL 조치를 §5 Task 후보로 |

## 리뷰 게이트 흐름
1. 담당 팀이 작업 모드로 Task 수행
2. 오케스트레이터가 변경이 해당하는 리뷰 팀을 고름 (코드 변경이면 `qa` 는 항상)
3. 리뷰 팀들이 동시에 검증 → STM §7
4. FAIL → 담당 팀 재작업 → FAIL 낸 팀만 재리뷰 (최대 2회)
5. 그래도 FAIL → `outcome: partial`, 남은 조치는 Task 후보로 → cascade 에서 tasks.md 에 반영

## 규칙
- 소유 범위는 팀 간에 겹치지 않습니다. 다른 팀 범위는 고치지 말고 Task 후보로 남깁니다.
- 팀 Agent 는 `tasks.md`, `long-term.md`, `plan.md` 를 직접 고치지 않습니다.
- 우선순위: user/02 개발 표준 > user/03 아키텍처 철학 > 분석서 > charter > LTM
