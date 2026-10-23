# 7. CLI 레퍼런스

모든 스크립트는 Python 표준 라이브러리만 사용합니다 (YAML 명세만 PyYAML 필요). **저장소 루트의 터미널**에서 실행하세요. 예시는 `python3` 로 적었으며 Windows 에서는 `python` 또는 `py` 로 바꿉니다.

## `aidlc/scripts/aidlc.py`

| 명령 | 설명 | 종료 코드 |
|------|------|----------|
| `init [--force]` | 템플릿으로 `workspace/` 생성. 기존 파일은 건너뜀, `--force` 시 덮어씀 | 0 |
| `check [user\|project\|docs]` | 미작성 `{{내용}}` 플레이스홀더 검사. HTML 주석 안과 내용이 빈 `{{ }}`(안내문의 표기 설명)는 무시. 기본 `user` | PASS 0 / FAIL 1 |
| `teams` | 팀 카탈로그 목록 (tier, 그룹, 리뷰 게이트, 생성 조건) | 0 |
| `new-team <id...>` | 카탈로그 기반 charter + 팀 Agent 생성 | 0 / 잘못된 id 1 |
| `new-team --core` | 필수 6팀 일괄 생성 | 0 |
| `new-team <id> "<제목>"` | 제목 지정 (카탈로그 밖 팀 포함) | 0 |
| `status` | Plan/Task/LTM/STM 상태와 미처리 cascade | 0 |

### `check` 대상
| layer | 검사 파일 | 추가 검사 |
|-------|----------|----------|
| `user` | `workspace/user/*.md` | — |
| `project` | `workspace/project/*.md` | 템플릿 00~40 중 없는 문서를 `MISSING` 으로 |
| `docs` | `docs/**/*.md` (`docs/aidlc/`, `reference.md` 제외) | — |

출력 예:
```text
TODO  user/01-project-overview.md  (3개 미작성)
        L42: {{수용 기준}}
OK    user/02-development-standards.md  (0개 미작성)

GATE FAIL — user layer: 미작성 3개, 누락 문서 0개
```

### `new-team` 규칙
- id: 소문자로 시작, 소문자/숫자/`-`, 2~31자
- 생성: `workspace/teams/<id>/charter.md`, `.claude/agents/team-<id>.md`
- 이미 있으면 `exists ... (건너뜀)` — 덮어쓰지 않음

## `aidlc/scripts/openapi_docs.py`

| 명령 | 설명 | 종료 코드 |
|------|------|----------|
| `detect` | 저장소에서 OpenAPI 3.x 명세 파일 탐지 | 찾음 0 / 없음 1 |
| `render <spec> [-o <dir>]` | `<dir>/reference.md` 생성. 기본 `docs/api` | 0 |

## `aidlc/hooks/memory_cascade.py`
Claude Code 가 `.claude/settings.json` 의 Hook 으로 호출합니다. 입력은 stdin 의 Hook JSON.
Hook 은 `bash aidlc/hooks/run.sh <인자>` 로 실행되고, `run.sh` 가 `python3` → `python` → `py` 순서로 **실제로 실행되는** Python 3.10+ 을 찾아 넘깁니다 (Windows 의 가짜 `python3` 는 건너뜀). Python 이 없으면 경고만 남기고 exit 0.

| 인자 | Hook 이벤트 | 출력 |
|------|------------|------|
| `session-start` | SessionStart | `hookSpecificOutput.additionalContext` 에 상태 요약 |
| `post-tool-use` | PostToolUse (Write\|Edit\|MultiEdit) | 메모리 변경 시 다음 cascade 지시 / OpenAPI 명세 변경 시 재생성 안내 |
| `stop` | Stop | 미처리 cascade 시 `{"decision":"block","reason":...}` (연속 3회까지) |
| `pre-compact` | PreCompact | 진행 중 STM 스냅샷 후 `systemMessage` |
| `status` | (수동) | 사람이 읽는 상태 요약 |

수동 테스트:
```bash
echo '{}' | bash aidlc/hooks/run.sh stop
```
Hook 내부 오류는 stderr 에만 기록하고 항상 exit 0 으로 끝나 세션을 막지 않습니다.

## 테스트
```bash
python3 -m unittest discover -s aidlc/tests -v
```
| 파일 | 검증 내용 |
|------|----------|
| `test_memory_cascade.py` | STM→LTM→Tasks→Plan 전체 흐름, Stop 차단·해제, 스냅샷, 비대상 파일 무시 |
| `test_teams.py` | 카탈로그 필드 완전성, 필수 6팀, 렌더링 후 남은 토큰 없음, 덮어쓰기 방지 |
| `test_openapi_docs.py` | 탐지, `$ref`/`allOf`/중첩 필드, 3.1 nullable, curl 예시, deprecated, 명세 변경 Hook |

## Skill (슬래시 명령)
| 명령 | 파일 |
|------|------|
| `/aidlc-init` | `.claude/skills/aidlc-init/SKILL.md` |
| `/aidlc-interpret` | `.claude/skills/aidlc-interpret/SKILL.md` |
| `/aidlc-analyze` | `.claude/skills/aidlc-analyze/SKILL.md` |
| `/aidlc-teams` | `.claude/skills/aidlc-teams/SKILL.md` |
| `/aidlc-plan` | `.claude/skills/aidlc-plan/SKILL.md` |
| `/aidlc-run` | `.claude/skills/aidlc-run/SKILL.md` |
| `/aidlc-docs` | `.claude/skills/aidlc-docs/SKILL.md` |
| `/aidlc-status` | `.claude/skills/aidlc-status/SKILL.md` |

## Agent
| Agent | 역할 |
|-------|------|
| `doc-interpreter` | User → Project 해석 |
| `business-analyst` | 비즈니스 모델 분석 |
| `architecture-analyst` | 아키텍처 분석 + ADR |
| `data-analyst` | EDA |
| `team-architect` | 팀 결정·생성 |
| `memory-curator` | cascade 1/3, 2/3 위임용 |
| `team-<id>` | 팀 실행 (작업/리뷰 모드), `/aidlc-teams` 가 생성 |
