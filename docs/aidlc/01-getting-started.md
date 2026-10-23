# 1. 시작하기

## 준비물
- Claude Code (CLI, 데스크톱, 웹 어디서든)
- Python 3.10 이상 — `python3 --version`
- (선택) PyYAML — YAML 형식 OpenAPI 명세를 문서화할 때만 필요. JSON 명세는 없어도 됩니다.

설치 확인:
```bash
python3 -m unittest discover -s aidlc/tests    # OK 가 나오면 준비 완료
python3 aidlc/scripts/aidlc.py teams           # 팀 카탈로그가 출력되면 정상
```

> Hook 은 `.claude/settings.json` 에 등록돼 있어 저장소를 열면 자동으로 켜집니다. 처음 열 때 Claude Code 가 프로젝트 Hook 사용을 확인하면 허용하세요.

## 따라 하기: 첫 Task 실행까지

### 1단계 — 작업공간 만들기
```text
/aidlc-init
```
`workspace/` 가 생깁니다.
```
workspace/
  user/      01-project-overview.md, 02-development-standards.md,
             03-architecture-philosophy.md, 04-data-definition.md   ← 여기를 채웁니다
  project/   (분석 결과가 들어올 곳)
  teams/     (팀 문서가 들어올 곳)
  memory/    plan.md, tasks.md, long-term.md, short-term.md, archive/
  data/      (EDA 할 데이터 파일을 여기에)
```

### 2단계 — 사용자 문서 작성
`workspace/user/` 4개 문서의 `{{ }}` 를 채웁니다. 작성법은 [2. 사용자 문서 작성법](02-writing-user-docs.md).
진행 상황 확인:
```bash
python3 aidlc/scripts/aidlc.py check user
# TODO  user/01-project-overview.md  (12개 미작성)
#         L18: {{해결하려는 문제}}
# GATE FAIL — user layer: 미작성 31개, 누락 문서 0개
```
> 혼자 채우기 어렵다면 Claude 에게 "01 문서 작성 도와줘" 라고 하세요. 질문을 하나씩 하며 답을 문서에 옮겨 줍니다.

### 3단계 — 해석
```text
/aidlc-interpret
```
- GATE FAIL 이면 멈추고 빈 항목을 알려 줍니다.
- 통과하면 `workspace/project/00-interpretation.md` 가 생기고 **질문 목록**이 나옵니다.
- 판단이 **HOLD** 면 질문에 답하도록 user 문서를 고치고 다시 `/aidlc-interpret`.

### 4단계 — 분석 → 팀 → 계획
```text
/aidlc-analyze
/aidlc-teams
/aidlc-plan
```
> `/aidlc-teams` 후 새 팀 Agent(`team-qa` 등)가 Agent 목록에 안 보이면 세션을 다시 시작하세요.

### 5단계 — 실행
```text
/aidlc-run        # Task 1개
/aidlc-run 5      # Task 5개 연속
/aidlc-run T-007  # 특정 Task
```
Task 하나가 끝날 때마다 Hook 이 **STM → LTM → Task → (Phase 완료 시) Plan** 순서로 갱신을 강제합니다.

### 6단계 — 문서화
```text
/aidlc-docs
```
API 가 있으면 `docs/api/reference.md`(REST API 레퍼런스)와 `docs/api/README.md`(API 가이드), 그리고 `docs/guide/README.md`(사용자 가이드)가 생깁니다.

## 언제든
```text
/aidlc-status
```
지금 몇 단계인지, 다음에 무엇을 하면 되는지 알려 줍니다.
