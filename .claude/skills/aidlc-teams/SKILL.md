---
name: aidlc-teams
description: 분석서와 팀 카탈로그로 실제 운영할 팀(core 6 + 조건부 팀)을 결정하고 팀 구성서, 팀 charter, 팀 실행 Agent 를 생성한다.
disable-model-invocation: true
---
# /aidlc-teams — 3단계: 팀 생성 & 팀 문서

1. 10/20/30 분석서가 모두 있는지 확인한다. 없으면 `/aidlc-analyze` 를 안내하고 멈춘다.
2. `python3 aidlc/scripts/aidlc.py teams` 로 카탈로그를 보여준다.
3. `team-architect` 서브에이전트에 위임한다.
4. 결과 검증 (직접 수행):
   - core 팀 6개(product, architecture, qa, cicd, ops, security)가 모두 있는가
   - `40-team-composition.md` frontmatter `teams` 의 id 마다 `workspace/teams/<id>/charter.md` 와 `.claude/agents/team-<id>.md` 가 있는가
   - 두 팀 이상이 같은 디렉토리/컴포넌트를 "소유"하지 않는가, 모든 FR 이 최소 한 팀에 배정되었는가
   - 제외한 conditional 팀마다 책임 인수 팀이 적혀 있는가
5. 보고: 그룹별 팀 표(id, tier, 근거), 제외 팀과 인수 팀, 리뷰 게이트 목록.
   새 팀 Agent 가 목록에 안 보이면 세션 재시작을 안내. 다음 단계 `/aidlc-plan`.
