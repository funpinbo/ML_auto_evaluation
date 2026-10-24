---
adr: 009
title: AI-DLC 상태 읽기 — Hook 읽기 함수 재사용, status 서브프로세스 금지, check 서브프로세스 허용
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [FR-001, FR-002, FR-003, FR-010, CON-03, A17, 원칙 2, 03 §5, 03 §10]
---
# ADR-009. AI-DLC 상태를 읽는 방식

## Context
- FR-003: cascade 1/2/3 미처리 여부를 Hook 과 같은 규칙으로 판정. FR-001: Gate 결과.
- 30 EDA §3: `aidlc.py status` → `memory_cascade.py status` → `handle("status")` 가 요약 출력 전에 `archive_stm_if_closed()` 를 호출 → STM 이 closed 면 아카이브 생성 + short-term.md 초기화. **읽기 전용이 아니다.** 대시보드가 부르면 원칙 2 위반이고 Hook cascade 순서에 끼어든다.
- `aidlc.py check` 는 파일을 읽기만 한다(코드 확인). `cmd_status` 와 달리 쓰기 경로 없음.
- `memory_cascade.py` 의 `read_doc`, `Memory.exists/phases/archived/latest_seq/pending/load_state` 는 읽기만 한다. `Memory.summary()` 도 읽기만 하지만 문자열이라 구조화 데이터가 필요. 쓰기 함수: `write_doc`, `reset_stm`, `archive_stm_if_closed`, `snapshot_stm`, `save_state`, `handle`, `main`. 모듈 최상위 코드는 부작용이 없지만, **importlib 기본 로더(`SourceFileLoader`)는 import 시 `aidlc/hooks/__pycache__/memory_cascade.*.pyc` 를 쓴다**(I-23, STM-0010 실측) — 대시보드가 프레임워크 디렉터리에 파일을 만드는 셈이라 원칙 2·03 §10 위반.
- 유지보수성(03 §2 순위 3): 판정 규칙이 두 곳에 있으면 어긋난다.

## Decision
1. `services/aidlc_reader.py` 가 `importlib.util.spec_from_file_location` 으로 `<AIDLC_ROOT>/aidlc/hooks/memory_cascade.py` 를 로드하고 **허용 목록**만 노출한다: `read_doc`, `as_int`, `FM_RE`, `PHASE_RE`, `CHECKBOX_RE`, `ARCHIVE_RE`, `Memory(root).exists/phases/archived/latest_seq/pending/load_state`. `pending()` 은 `level` 만 쓰고 메시지 문자열은 화면에 내보내지 않는다.
   - **바이트코드 미기록 로더 필수**: spec 의 loader 는 `.pyc` 를 쓰지 않는 로더(`SourceFileLoader` 하위 클래스에서 `set_data` 를 no-op 으로 둔 `_NoBytecodeLoader`)를 쓴다. 프로세스 전역 `sys.dont_write_bytecode` 를 바꾸는 방식은 다른 import 에 영향을 주므로 쓰지 않는다. 테스트: 조회 API 호출 전후 `aidlc/hooks/` 아래 파일 목록 불변(`__pycache__` 생성 없음). 같은 이유로 `aidlc.py` 의 loop-* 블록도 바이트코드를 쓰지 않는다(ADR-004 Decision 2.3).
2. 쓰기 함수(`write_doc`, `reset_stm`, `archive_stm_if_closed`, `snapshot_stm`, `save_state`, `handle`, `main`)는 어댑터에서 참조하지 않는다. 테스트가 이 함수들을 예외를 던지는 가짜로 바꾼 상태에서 모든 조회 API 를 호출해 통과해야 한다.
3. `read_doc` 의 UnicodeDecodeError·OSError 는 어댑터가 잡아 패널 `meta.status = error`(`SOURCE_PARSE_ERROR`/`SOURCE_UNREADABLE`)로 변환(NFR-002).
4. Task 줄 상세(T-ID, `[팀]`, 제목, FR, deps), `## Blocked` 섹션, STM §3 작업 로그·§7 리뷰 표는 Hook 에 없는 파싱이라 같은 정규식 상수를 재사용해 리더 안에 구현.
5. Gate 는 `subprocess.run([sys.executable, "<root>/aidlc/scripts/aidlc.py", "check", layer], capture_output=True, timeout=10, stdin=DEVNULL)` 로 실행, 출력 정규식 파싱(30 §1 DS-02, 못 읽은 줄 0). 결과 TTL 5 s + 대상 디렉터리 mtime 같으면 재사용. **`status` 는 어떤 경로로도 부르지 않는다.**
6. Hook 규칙 대조 테스트: fixture(cascade 1/2/3 각각, 없음)에서 어댑터 판정 == `Memory(root).pending().level`, 그리고 closed STM fixture 에서 조회 전후 workspace 해시 불변.

## Alternatives
- **`aidlc.py status` 서브프로세스 + 출력 파싱**: 쓰기 부작용(30 §3). 기각.
- **판정 규칙 재구현**: Hook 과 독립이지만 규칙 중복 → 프레임워크 변경 시 어긋남. 허용 목록 import 가 더 안전. 기각(단, Hook 모듈 로드 실패 시 대비해 "AI-DLC 엔진을 찾을 수 없음" 패널 오류로 처리).
- **Hook 에 `--read-only` status 옵션 추가**: 깔끔하지만 프레임워크 변경 + 서브프로세스 비용. 필요해지면 후속 ADR.

## Consequences
- (+) cascade 판정이 Hook 과 항상 같다(규칙 단일 출처).
- (+) 대시보드 쓰기 범위가 `.control.json` 하나로 유지.
- (−) Hook 모듈 API 에 결합 → 프레임워크가 함수 이름을 바꾸면 어댑터 테스트가 실패해 바로 드러남(의도된 결합).
- (−) `check` 서브프로세스 1회 약 30 ms → TTL 캐시로 상쇄.

## 변경 이력
- 2026-10-24 T-009 (I-23): Context 의 "모듈 import 자체는 부작용 없음" 을 정정 — 기본 로더가 `__pycache__/*.pyc` 를 쓴다. Decision 1 에 바이트코드 미기록 로더 요구(구현 `services/aidlc_reader.py` `_NoBytecodeLoader`)와 검증 기준 추가. 근거: 원칙 2(대시보드 쓰기는 `.control.json` 하나), 03 §10(대시보드가 AI-DLC 파일을 고치지 않음). 구조 결정 변경 없음(구현에 맞춘 문구·요구 명시).
