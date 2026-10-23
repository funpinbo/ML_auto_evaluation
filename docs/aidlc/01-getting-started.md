# 1. 시작하기

## 준비물
- **Claude Code** — VSCode 확장(권장) 또는 CLI
- **Python 3.10 이상**
- **Windows:** [Git for Windows](https://git-scm.com/download/win) (Git Bash 포함). Hook 이 Git Bash 로 실행됩니다.
- (선택) PyYAML — YAML 형식 OpenAPI 명세를 문서화할 때만 필요. JSON 명세는 없어도 됩니다.

## 명령은 어디에 입력하나요?

이 문서에는 두 종류의 명령이 나옵니다. **입력하는 곳이 다릅니다.**

| 모양 | 예 | 입력하는 곳 |
|------|----|------------|
| `/` 로 시작 | `/aidlc-init`, `/aidlc-run 3` | **Claude Code 채팅 입력창** (터미널 아님) |
| `python ...` | `python aidlc/scripts/aidlc.py check user` | **터미널** (VSCode 통합 터미널 등) |

### `/aidlc-*` 명령 (Claude Code 채팅 입력창)
1. VSCode 에서 **이 저장소 폴더(최상위)** 를 엽니다 — `파일 > 폴더 열기`. 하위 폴더를 열면 `.claude/` 를 못 찾아 명령이 안 보입니다.
2. Claude Code 패널을 엽니다 (사이드바의 Claude 아이콘, 또는 명령 팔레트 `Claude Code: Open`).
3. 입력창에 `/` 를 치면 명령 목록이 뜹니다. `/aidlc-init` 을 고르고 Enter.

CLI 를 쓰는 경우: 터미널에서 저장소 폴더로 이동해 `claude` 를 실행한 뒤, 그 안의 입력창에 `/aidlc-init` 을 입력합니다.

> 터미널(bash, PowerShell)에 `/aidlc-init` 을 직접 치면 "command not found" 가 납니다. Claude Code 안에서만 동작하는 명령입니다.
>
> 처음 열 때 Claude Code 가 이 프로젝트의 Hook 사용을 확인하면 허용하세요. Hook 은 `.claude/settings.json` 에 등록돼 있습니다.

### `python ...` 명령 (터미널)
Python 실행 명령은 OS 마다 다릅니다. 이 문서는 `python3` 로 적지만, 아래 표에 맞게 바꿔 입력하세요.

| OS | 명령 | 확인 |
|----|------|------|
| macOS / Linux | `python3` | `python3 --version` |
| Windows | `python` 또는 `py` | `python --version` |

> Windows 에서 `python3` 를 치면 Microsoft Store 가 열리거나 "Python was not found" 가 나올 수 있습니다. `python` 이나 `py` 를 쓰세요.
> Hook 은 `aidlc/hooks/run.sh` 가 사용 가능한 Python 을 자동으로 찾으므로 따로 설정할 필요가 없습니다.

`/aidlc-*` 명령 일부는 터미널 명령으로도 할 수 있습니다:

| Claude Code 명령 | 같은 일을 하는 터미널 명령 |
|------------------|---------------------------|
| `/aidlc-init` | `python aidlc/scripts/aidlc.py init` |
| `/aidlc-status` (일부) | `python aidlc/scripts/aidlc.py status` |

나머지(`/aidlc-interpret`, `/aidlc-analyze` …)는 Agent 가 문서를 읽고 쓰는 단계라 Claude Code 안에서만 실행됩니다.

## 설치 확인 (터미널)
```bash
python3 -m unittest discover -s aidlc/tests    # OK 가 나오면 준비 완료 (Windows: python -m unittest ...)
python3 aidlc/scripts/aidlc.py teams           # 팀 카탈로그가 출력되면 정상
```

## 따라 하기: 첫 Task 실행까지

### 1단계 — 작업공간 만들기
Claude Code 채팅 입력창에:
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
