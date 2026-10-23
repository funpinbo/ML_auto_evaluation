# 8. 문제 해결 & FAQ

## 자주 막히는 곳

| 증상 | 원인 | 해결 |
|------|------|------|
| `/aidlc-interpret` 가 바로 멈춤 | user 문서에 `{{ }}` 가 남음 | `python3 aidlc/scripts/aidlc.py check user` 로 위치 확인. 해당 없음이면 `N/A (이유)` |
| 해석 결과가 계속 HOLD | 확신도 L 인 Must FR 또는 미해결 충돌 | 00 해석서 §3·§4 를 보고 user 문서 수정 후 재실행 |
| `team-qa` 등 팀 Agent 가 안 보임 | 세션 시작 후 생성된 Agent | 세션 재시작 |
| 대화를 끝내려는데 계속 이어서 작업함 | Stop Hook 이 미처리 cascade 를 막는 중 (정상 동작) | 지시대로 LTM/Task/Plan 갱신. 3회 연속이면 자동 해제 |
| cascade 메시지가 같은 단계를 반복 요구 | frontmatter 값이 갱신되지 않음 | 메시지에 적힌 값(`rev`, `last_merged_stm`, `synced_ltm_rev`, `completed_phases`)을 정확히 설정 |
| Phase 를 다 끝냈는데 Plan 갱신이 안 나옴 | Phase 섹션 제목 형식 | tasks.md 섹션은 반드시 `## P1 ...` 처럼 `## P<숫자>` 로 시작 |
| STM 을 닫았는데 아카이브가 안 생김 | `status: closed` 오타 또는 Bash 로 수정 | 값을 확인. Bash 로 고친 경우 PostToolUse 가 안 불리지만 다음 Stop/SessionStart 에서 처리됨 |
| `openapi_docs.py render` 가 YAML 오류 | PyYAML 미설치 | `pip install pyyaml` 또는 명세를 JSON 으로 |
| "OpenAPI 3.x 명세가 아닙니다" | Swagger 2.0 명세 | swagger2openapi 등으로 3.x 로 변환 |
| reference.md 에 "외부 참조" 표시 | 다른 파일을 가리키는 `$ref` | 명세를 하나로 번들 (예: `redocly bundle`) |
| Hook 이 아무 반응 없음 | `workspace/memory/` 없음, 또는 Hook 미허용 | `/aidlc-init` 실행, Claude Code 에서 프로젝트 Hook 허용 |

## FAQ

**Q. User 문서를 Agent 가 대신 써 줄 수 있나요?**
대화로 질문하며 답을 옮겨 적는 것은 가능합니다. 하지만 내용 자체를 지어내지는 않습니다. User Layer 는 사용자의 의도이기 때문입니다.

**Q. 중간에 요구가 바뀌면?**
user 문서를 고치고 `/aidlc-interpret` → 영향 범위에 따라 `/aidlc-analyze` 부터 다시. 이미 진행된 Task 는 다음 cascade 2/3 에서 재조정됩니다.

**Q. tasks.md 를 손으로 고쳐도 되나요?**
가능하지만 규칙상 cascade 2/3 단계에서만 고치는 것을 권장합니다. 체크박스를 직접 바꾸면 Phase 완료 판정(cascade 3/3)이 바로 반응합니다.

**Q. 팀을 나중에 추가할 수 있나요?**
`python3 aidlc/scripts/aidlc.py new-team <id>` 후 team-architect 에게 charter 구체화와 40 팀 구성서 갱신을 요청하세요. 그리고 `/aidlc-plan` 대신 다음 cascade 2/3 에서 그 팀 Task 를 추가하면 됩니다.

**Q. API 가 없는 프로젝트(배치, CLI, 라이브러리)는?**
`/aidlc-docs` 가 API 문서를 건너뛰고 사용자 가이드만 만듭니다. 라이브러리 API 문서는 docs 팀 charter 에 별도 산출물로 추가하세요.

**Q. 모든 상태를 처음부터 다시 하고 싶어요.**
`workspace/memory/` 를 지우고 `python3 aidlc/scripts/aidlc.py init` (user 문서는 남습니다). user 문서까지 초기화하려면 `init --force` — **작성한 내용이 사라집니다.**
