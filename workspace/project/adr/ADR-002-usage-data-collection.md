---
adr: 002
title: 사용량 데이터 수집 — JSONL 증분 파싱 + 허용 필드 복사 + 프로세스 메모리 캐시
status: proposed
date: 2026-10-23
author: architecture-analyst
related: [FR-004, FR-009, NFR-001, NFR-003, C2, C3, A13, A15, Q2, Q7, 원칙 2, 원칙 3, 03 §5, 03 §9]
---
# ADR-002. 사용량 데이터 수집 방식 (03 §9 ADR 필수 대상)

## Context
- FR-004: 시간대별·모델별 토큰 그래프. 데이터는 `~/.claude/projects/<인코딩된 프로젝트 경로>/` 아래 JSONL(DS-03).
- 30 EDA 실측: 메인 파일 + `<세션>/subagents/agent-*.jsonl`(서브에이전트 몫 output 의 22.8%) → **재귀 탐색 필수**. 줄 기준 중복 57.95%(requestId 그룹, usage 동일) → **중복 제거 필수**. `"usage":` 사전 필터 권장. 처리 속도 실측 4.4 ms/MB, 30일 외삽 329~658 MB → 콜드 1.45~2.89 s, 증분 1 MB 약 1.5~4.4 ms.
- 00 Q2: 줄은 읽되 `"usage"` 없는 줄은 파싱 전 버리고, 허용 필드만 복사. 본문은 접근·보관·로그·응답·저장 안 함.
- 00 C3 해석: "서버 무상태" = 디스크에 자기 데이터를 영속하지 않음. 프로세스 메모리 파생 캐시 허용.
- 00 Q7/A13: 이 저장소 프로젝트 디렉터리만 집계, "이 프로젝트 기준" 표기.
- 03 §4 금지: DB 서버. 원칙 3: 표준 라이브러리로 되면 라이브러리 추가 안 함.

## Decision
1. **프로젝트 디렉터리 해석 (resolver, 순서대로)**
   1. 규칙 인코딩: 저장소 절대 경로(`Path.resolve()`)의 영숫자 외 문자를 모두 `-` 로 바꾼 이름. Linux 실측 `/home/user/chatbot` → `-home-user-chatbot` 확인. Windows `C:\x\y` → `C--x-y`, macOS 는 같은 규칙으로 **가정**(리허설에서 확인, 대소문자 차이는 대소문자 무시 비교로 보완).
   2. 상태 스냅샷(ADR-003)의 `transcript_dir_name`(statusLine stdin `transcript_path` 의 상위 디렉터리 이름) 이 있으면 그것.
   3. 폴백: `~/.claude/projects/*` 중 최근 30일 파일의 usage 줄(사전 필터 통과 줄만)에서 `cwd` 만 복사해 저장소 경로와 같은 디렉터리. 결과는 프로세스 수명 동안 캐시.
   4. 모두 실패 → `PROJECT_DIR_NOT_FOUND`, 패널에 안내.
   `~/.claude` 아래에서 여는 파일은 `projects/<enc>/**/*.jsonl` 과 (ADR-003 의) `settings.json` 의 statusLine 키뿐. 인증 파일은 열지 않는다(02 §8).
2. **증분 읽기**: 파일별 커서 `(inode, size, mtime, offset)`. 1초 stat 폴링(ADR-008)에서 size/mtime 변경 시 offset 부터 바이너리로 읽고 마지막 완전한 줄 끝까지만 처리(잘린 줄은 다음 주기). size < offset 또는 inode 변경 → 그 파일만 처음부터(그 파일 기여분은 requestId 단위로 빼고 다시 더함). mtime 30일 초과 파일은 건너뜀.
3. **개인정보 필터 (`privacy_filter.py`, security 리뷰 대상)**: 원문 줄에 `b'"usage":'` 가 없으면 버림 → `json.loads` → `message.usage` 가 dict 인지 확인 → 새 dataclass 에 `timestamp`, `requestId`, `message.model`, usage 숫자 4종, `isSidechain` 만 복사(해석 폴백 시에만 `cwd`) → 원본 dict 즉시 폐기. `message.content` 등 다른 키는 접근하지 않음. 파싱 실패·형식 오류는 건수만 WARN.
4. **중복 제거**: 키 `requestId`, 30일 전역 dict(`requestId → 기여값`). 같은 값이면 무시, 다르면 이전 기여분을 빼고 새 값 반영(last-wins). requestId 없는 줄은 1건으로 세고 WARN 건수.
5. **집계 저장**: 프로세스 메모리만. UTC 시간 버킷 `(hour, model, is_sidechain) → {responses, 토큰 4종}`. 응답 시 `range`·`bucket`·`tz_offset_min` 으로 합산(파싱 없음, ms). 30일 지난 버킷·requestId 정리. requestId·sessionId·파일 경로는 응답·로그에 내보내지 않는다.
6. **데우기**: 서버 시작 시 백그라운드 스레드 1개가 mtime 내림차순으로 읽기. 진행률을 `/health`·`/usage/*` 의 `meta.status = warming` 과 SSE `warming` 이벤트로 노출. 최근 파일 우선이라 "오늘/현재 5시간" 값이 먼저 완성.
7. **5시간 구간**: 스냅샷 `rate_limits.five_hour.resets_at` 이 있으면 `[resets_at − 5h, now]`, 없으면 이동 5시간 + "추정" 표기.
8. **동시성**: 집계 구조는 `threading.Lock` 하나로 보호(데우기 스레드 + 폴링 태스크). 응답은 스냅샷 복사본으로 생성.

## Alternatives
- **매 요청 전량 재파싱 (TTL 수 초)**: 03 §5 문자 그대로지만 30일치에서 NFR-001 2초 불가(30 §4 Q5). 기각.
- **SQLite 등 디스크 캐시**: 재시작 후 빠르지만 03 §5 "자체 데이터를 저장하지 않는다" 위반, 파생 데이터가 디스크에 남아 보안 노출면 증가. 기각.
- **스트리밍 JSON 파서(ijson 등)로 usage 만 추출**: 본문을 파이썬 객체로 만들지 않는 장점이 있으나 외부 의존성(원칙 3), 줄 단위 사전 필터 + 즉시 폐기로 Q2 승인 범위 충족. 기각.
- **정규식으로 usage 숫자만 추출(json 파싱 없음)**: 더 빠르지만 키 순서·이스케이프에 취약(30 §3 사전 필터 비교). 기각.
- **`~/.claude/projects` 전체 집계**: 계정 한도와 맞추기 쉽지만 다른 저장소 기록을 읽어 범위·개인정보 노출 확대(01 §3 여러 저장소 범위 밖). 기각.

## Consequences
- (+) 버킷 조회 ms 단위, 증분 반영 수 ms → NFR-001 의 5초 반영 여유 큼.
- (+) 디스크에 자기 데이터 없음, 재시작 시 원천에서 재구축(03 §5).
- (−) 재시작 직후 수 초 데우기(느린 PC 는 더 길 수 있음) → `warming` UI 필요.
- (−) 메모리 사용 수 MB~수십 MB(30일 requestId 약 2.4만 건 + 버킷 수천 칸).
- (−) 비공식 JSONL 형식 변경에 민감 → 관대한 파서 + WARN 건수 + health 표시.
- 테스트(qa): 가짜 JSONL 생성기(중복 requestId, usage 없는 줄, 잘린 마지막 줄, subagents/, 파일 교체), 본문 표식 문자열 비노출, 성능 fixture(30일 분량).
