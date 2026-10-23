---
name: aidlc-init
description: AI-DLC 작업공간(workspace/)을 템플릿으로 초기화한다. User Layer 문서 4종과 Plan/Task/LTM/STM 메모리 파일을 생성.
disable-model-invocation: true
argument-hint: "[--force]"
---
# /aidlc-init — 0단계: 작업공간 초기화

1. `python3 aidlc/scripts/aidlc.py init $ARGUMENTS` 를 실행한다. (`--force` 는 기존 파일을 덮어쓰므로, 사용자가 명시했을 때만 전달)
2. 생성 결과를 보여주고, 사용자가 작성해야 할 문서를 안내한다:

| 순서 | 문서 | 내용 |
|------|------|------|
| 1 | `workspace/user/01-project-overview.md` | 프로젝트 개요 & 기능 요구서 |
| 2 | `workspace/user/02-development-standards.md` | 개발 표준 정의서 |
| 3 | `workspace/user/03-architecture-philosophy.md` | 아키텍처 철학 |
| 4 | `workspace/user/04-data-definition.md` | 데이터 정의서 (EDA 입력, 데이터 파일은 `workspace/data/`) |

3. `{{ }}` 표시가 필수 항목이며, `python3 aidlc/scripts/aidlc.py check` 로 미작성 항목을 확인할 수 있다고 알린다.
4. 사용자가 원하면 대화로 질문하며 문서 작성을 도와줄 수 있다고 제안한다 (이때 사용자 답을 그대로 옮겨 적고, 지어내지 않는다).
