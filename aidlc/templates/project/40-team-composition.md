---
doc: team-composition
layer: project
author: team-architect
status: draft
teams: []
---
# 40. 팀 구성

> 입력: `aidlc/teams/catalog.json`, 10/20/30 분석서, user/02. core 팀(product, architecture, qa, cicd, ops, security)은 항상 생성.
> 생성한 팀마다 `workspace/teams/<id>/charter.md` 와 `.claude/agents/team-<id>.md` 가 존재해야 합니다.
> frontmatter `teams` 에 생성한 팀 id 목록을 적습니다.

## 1. 팀 구성 결정
| 팀 id | 팀명 | tier | 생성 근거 (분석서 § 인용) | 담당 컴포넌트/디렉토리 |
|-------|------|------|--------------------------|------------------------|

## 2. 생성하지 않은 팀 & 책임 인수
| 후보 팀 | 제외 이유 (create_when 미충족 근거) | 책임을 넘겨받는 팀 |
|---------|-------------------------------------|-------------------|

## 3. 조직도
```mermaid
flowchart TB
  subgraph 기획·설계
  end
  subgraph 개발
  end
  subgraph 데이터·AI
  end
  subgraph 품질
  end
  subgraph 플랫폼·운영
  end
  subgraph 보안·거버넌스
  end
```

## 4. 책임 매트릭스 (RACI)
<!-- 열 = 생성된 팀 id. R=수행, A=최종책임(정확히 1팀), C=협의, I=통보 -->
| 산출물/활동 | | | | | |
|-------------|-|-|-|-|-|
| 요구사항·수용 기준 | | | | | |
| ADR·계약 | | | | | |
| 기능 구현 | | | | | |
| 테스트 전략·E2E | | | | | |
| CI/CD·릴리스 | | | | | |
| 운영·SLO·장애 대응 | | | | | |
| 보안·개인정보 | | | | | |

## 5. 리뷰 게이트
<!-- /aidlc-run 이 Task 완료 후 대상에 해당하면 해당 팀을 리뷰 모드로 호출. catalog.json 의 review_gate 기준 -->
| 리뷰 팀 | 적용 대상 Task | 주요 확인 항목 |
|---------|---------------|---------------|

## 6. 팀 간 인터페이스 (계약)
| 제공 팀 → 사용 팀 | 인터페이스 | 형식 | 계약 문서 위치 |
|-------------------|-----------|------|----------------|

## 7. 팀 의존 그래프
```mermaid
flowchart LR
```

## 8. 팀별 초기 책임 FR / NFR
| 팀 | FR / NFR | 첫 Phase 목표 |
|----|---------|---------------|
