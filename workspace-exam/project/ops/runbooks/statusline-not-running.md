---
doc: runbook
owner: ops
sources: [ADR-003, R-09, contracts/claude-status.schema.json]
---
# 런북 — statusLine 미실행 (한도 % 가 안 나옴)

**증상:** 한도 게이지가 "정보 없음"/폴백, health `data.sources.statusline` 이 `missing` 또는 `stale`.

## 판단
| health 값 | 뜻 |
|-----------|----|
| `missing` | 스냅샷 파일이 아직 없다: statusLine 미등록, 스크립트 실패, 또는 등록 후 Claude Code 첫 응답 전 |
| `stale` | 파일 수정 시각이 10분 넘음: Claude Code 세션이 없거나 statusLine 이 멈춤 (ADR-003 §4) |
| `unreadable` | 파일 자리에 디렉터리가 있거나 권한 문제 |
| `ok` 인데 한도 없음 | 비구독(API 키)·첫 응답 전이면 `rate_limits` 가 null — 정상 |

## 조치
1. Claude Code 세션에서 한 번 응답을 받은 뒤 health 를 다시 본다(스냅샷은 응답 때 갱신).
2. statusLine 등록 확인(읽기만): 프로젝트 `.claude/settings.json` 의 `statusLine.command` 가 `aidlc/hooks/statusline.*` 을 가리키는지. 등록은 T-010 산출물이다.
3. Windows: bash(Git Bash)가 PATH 에 있는지 `bash --version` (R-09). 없으면 statusLine 이 돌지 않고 한도 패널은 JSONL 폴백만 쓴다 — 기능상 허용된 상태.
4. 스크립트 단독 실행으로 오류 종류 확인(입력 JSON 은 표준입력). 오류 메시지에 경로가 나오면 이슈로 남긴다(로그 규칙 위반).

## 하지 않는 것
- 사용자 전역 `~/.claude/settings.json` 을 직접 고치지 않는다(02 §11 — 사람 승인 필요). 전역 statusLine 은 체이닝 방식(ADR-003)으로만 다룬다.
