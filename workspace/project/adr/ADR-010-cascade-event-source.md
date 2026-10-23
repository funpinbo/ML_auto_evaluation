---
adr: 010
title: FR-006 cascade 이벤트 출처 — 파일 변화 추론 (Hook 이벤트 로그 보류)
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [FR-006, FR-010, A6, A10, Q8, 원칙 2, 03 §5]
---
# ADR-010. cascade 이벤트를 어디서 얻는가

## Context
- FR-006(Should, M2): STM 작업 로그와 cascade 이벤트(STM 보관, LTM rev 증가, tasks 동기화, Phase 완료)를 시간순, 5초 이내 갱신.
- 현재 Hook 은 이벤트를 파일로 남기지 않는다. 파일로 남는 것: `archive/STM-*.md`(frontmatter `opened_at`, `archived_at`, `seq`, `task`, `team`, `outcome`), long-term/tasks/plan frontmatter 값과 mtime, `.cascade-state.json`(Stop 차단 횟수).
- 00 Q8 답: A6 가정 그대로 — 파일 변화로 **추론**, Hook 이벤트 로그는 프레임워크 변경이라 사용자 승인 후.
- 03 §5: 대시보드는 자체 데이터를 저장하지 않는다.

## Decision
1. 타임라인 = 다음 항목을 시각순 병합(최대 200개):
   - STM §3 작업 로그 줄(현재 STM + 최근 archive). 시각이 줄에 없으면 STM `opened_at` 기준 순서만.
   - archive 마다 "STM 열림"(`opened_at`), "STM 보관"(`archived_at`).
   - LTM: 현재 `rev`, `last_merged_stm`, 파일 mtime → "LTM rev N 반영(STM-xxxx)" (시각 = mtime, **추정** 표기).
   - tasks: `synced_ltm_rev` 값 + mtime → "Task 동기화".
   - plan: `completed_phases` 각 항목 → "Phase 완료"(시각 = plan mtime, 추정).
   - 서버 실행 중 관찰한 전이(rev 증가, synced 변경, completed_phases 추가, Stop 차단 횟수 증가)는 1초 폴링(ADR-008)에서 감지한 시각으로 메모리 링 버퍼(최대 500)에 기록 → 정확한 시각. 재시작하면 사라짐(디스크 미저장).
2. FR-010 "cascade 막힘"(A10): 미처리 cascade 가 관찰 시작 후 10분 이상 지속 또는 `.cascade-state.json` `stop_blocks` 가 3 에 도달.
3. Hook 이벤트 로그(`workspace/memory/.monitor/events.jsonl`, Hook 이 append)는 **이번 범위에서 만들지 않는다.** 추론 정확도가 부족하다는 사용자 피드백이 있으면 후속 ADR 로 제안(소유: architecture, 변경 대상 `aidlc/hooks/memory_cascade.py`, Hook 테스트 `aidlc/tests` 갱신 필수).

## Alternatives
- **Hook 이 events.jsonl 을 append**: 정확한 시각·서버 꺼진 동안도 기록. 하지만 프레임워크 Hook 변경(사용자 승인 필요, Q8 은 추론 선택), 파일이 계속 커져 보존 정책 필요. 보류.
- **git 로그로 추론**: workspace/memory 커밋 주기가 일정하지 않음. 기각.

## Consequences
- (+) 프레임워크 Hook 무변경, 대시보드 쓰기 0.
- (−) 서버가 꺼져 있던 동안의 LTM/Task/Plan 이벤트 시각은 mtime 기반 근사(한 파일이 여러 번 바뀌면 마지막만). 화면에 "추정" 배지 — 기술 부채 R-12.
- 테스트: archive·frontmatter fixture 로 정렬·추정 표기, 실행 중 전이 감지(시간 주입).
