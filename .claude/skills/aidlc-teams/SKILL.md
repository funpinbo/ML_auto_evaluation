---
name: aidlc-teams
description: 분석서를 근거로 팀(Back/Front/Data/CICD/Ops 등)을 결정하고 팀 구성서, 팀 charter, 팀 실행 Agent 를 생성한다.
disable-model-invocation: true
---
# /aidlc-teams — 3단계: 팀 생성 & 팀 문서

1. 10/20/30 분석서가 모두 있는지 확인한다. 없으면 `/aidlc-analyze` 를 안내하고 멈춘다.
2. `team-architect` 서브에이전트에 위임한다.
3. 결과 검증 (직접 수행):
   - `workspace/project/40-team-composition.md` frontmatter `teams` 의 id 마다
     `workspace/teams/<id>/charter.md` 와 `.claude/agents/team-<id>.md` 가 존재하는가
   - 두 팀 이상이 같은 디렉토리/컴포넌트를 "소유"하지 않는가
   - 모든 FR 이 최소 한 팀에 배정되었는가
4. 보고: 팀 표(id, 근거, 담당 FR), 제외한 팀. 새 팀 Agent 가 목록에 안 보이면 세션을 재시작하라고 안내. 다음 단계 `/aidlc-plan`.
