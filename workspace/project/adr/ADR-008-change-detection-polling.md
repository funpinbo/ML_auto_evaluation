---
adr: 008
title: 파일 변경 감지 — 표준 라이브러리 stat 폴링, watchfiles 미도입
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [FR-008, NFR-001, 원칙 3, 03 §4, 03 §9]
---
# ADR-008. 파일 변경 감지 방식 (새 외부 의존성 watchfiles 여부, 03 §9 필수)

## Context
- NFR-001/FR-008: 상태 변화 5초 이내 반영. 03 §4: watchfiles 는 "폴링보다 반응이 빠를 때만" 허용.
- 감시 대상은 작다: workspace/memory 4파일 + archive 디렉터리 목록 + `.control.json` + `.monitor/` 2파일 + `workspace/project`·`workspace/teams` 목록 + Claude 프로젝트 디렉터리의 JSONL(30일 내, 세션 수십 개 수준).
- watchfiles 1.3.0(MIT)은 Rust 네이티브 휠. 휠이 없는 플랫폼은 Rust 빌드 필요. 네트워크 드라이브·WSL 경로에서는 OS 알림이 누락돼 결국 폴링 모드로 떨어지기도 한다.
- EDA: 증분 1 MB 처리 수 ms, stat 수십 건은 1 ms 미만.

## Decision
1. asyncio 백그라운드 태스크 1개가 **1초마다** 감시 대상의 `os.stat`(size, mtime_ns, inode)과 디렉터리 목록(`os.scandir`)을 비교한다. JSONL 디렉터리는 하위까지 scandir 하되 30일 지난 파일은 제외.
2. 변경된 항목을 topic(pipeline, plan, tasks, memory, teams, timeline, usage, control, alerts)으로 매핑해 SSE 허브에 전달. 같은 주기 안의 여러 변경은 한 이벤트로 묶는다.
3. 주기는 설정값(`AIDLC_MONITOR_POLL_SEC`, 0.5~5). 기본 1초.
4. watchfiles 는 설치하지 않는다(uvicorn 기본 설치와 일관, ADR-006).

## Alternatives
- **watchfiles**: 반응은 즉시지만 요구(5초) 대비 이득이 사실상 없고(1초 폴링 최대 지연 약 1초), 네이티브 의존성 추가 → 03 §4 허용 조건("폴링보다 빠를 때만")의 실익 없음. 기각.
- **프론트 주기 폴링만(SSE 없음)**: 단순하지만 03 §3 "실시간 갱신은 SSE" 와 다르고 패널 수만큼 요청 발생. SSE 실패 시 폴백으로만 사용.
- **OS 별 API 직접(inotify/FSEvents/ReadDirectoryChangesW)**: 표준 라이브러리로 이식성 있게 불가. 기각.

## Consequences
- (+) 의존성 0, OS·파일시스템 무관하게 같은 동작.
- (+) 테스트에서 시간을 주입해 결정적으로 검증 가능.
- (−) 유휴 중에도 초당 수십 회 stat (CPU 무시할 수준). 노트북 배터리 영향 미미.
- (−) 최대 약 1초 지연(요구 5초 이내 충족). 측정 테스트로 확인(qa).
