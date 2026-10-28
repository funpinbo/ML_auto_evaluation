---
doc: adr
id: ADR-004
title: 동일 (model, dataset) 재업로드 시 신규 레코드 생성 정책 확정
status: Accepted
date: 2026-10-27
layer: project
author: architecture (team agent)
---
# ADR-004: 동일 (model, dataset) 재업로드 시 신규 레코드 생성 정책 확정

## Context
- 30-data-analysis.md §(유일성 주의): "Model N─M Dataset 조합이 반복 업로드될 경우 중복 레코드 허용 여부가 04/01 에 명시 안 됨 — 10/20 단계에서 '동일 (model, dataset) 재업로드 시 신규 레코드 vs 갱신' 정책 결정 필요".
- stories/FR-001.md, FR-002.md 의 Out of scope 에 각각 "동일 (model, dataset) 조합/재업로드 정책 — LTM I-02 미해결, [architecture] Task 후보"로 명시되어 있었음.
- 실제 구현된 스키마(`app/eval/repository.py` `SCHEMA_DDL`, D-09, STM-0003): `model`/`dataset` 테이블은 각각 독립적인 `id TEXT PRIMARY KEY`(업로드 시 신규 UUID 발급 전제)를 가지며, `name`/`path` 컬럼에는 **UNIQUE 제약이 없다**. 이 파일 상단 주석(L18-22)에는 "model/dataset 자체의 재업로드 시 신규 id 로 새 레코드를 만들지, 기존 id 를 UPDATE 할지는 쿼리 함수 구현(backend, T-009) 단계에서 별도로 결정해야 한다"고 명시되어 있었음.
- `model_dataset_link` 는 (model_id, dataset_id) 복합 PK — 이는 동일 **링크**의 중복 삽입만 막을 뿐, model/dataset **자체**의 재업로드 정책과는 무관(이미 코드 주석·30§2 에 명시된 전제).
- T-009(backend, Repository 쿼리 함수 구현)가 이 정책 결정에 의존(deps: T-027) — 결정이 없으면 INSERT/UPDATE 분기를 구현할 수 없음.
- user/03 원칙 1(단순함 우선, 과설계 금지) · 원칙 3(결과 비교 용이성 > 성능) · 03§2 가중치(개발속도 1위, 유지보수성 2위)가 채점 기준.

## Decision
1. **Model 업로드(`POST /models`)와 Dataset 업로드(`POST /datasets`)는 항상 신규 레코드를 생성한다.** 기존 레코드와 `name`(또는 파일 내용)이 동일하더라도 매칭·갱신(UPDATE) 로직을 수행하지 않고, 매번 새 UUID 로 새 행을 INSERT 한다.
2. 이는 **추가 구현이 전혀 필요 없는, 이미 확정된 DDL(D-09)이 자연스럽게 제공하는 기본 동작**을 공식적으로 승인하는 것이다 — 스키마 변경 없음.
3. `model_dataset_link` 복합 PK 정책은 그대로 유지한다: 동일 (model_id, dataset_id) **링크**의 중복 생성은 여전히 차단된다. 단, 재업로드로 생성된 모델/데이터셋은 **새 id** 를 가지므로 기존 링크·과거 Run/Evaluation 이력과 자동으로 연결되지 않는다(사용자가 새로 연결해야 함) — 이는 의도된 동작이다.
4. 과거 Run/Evaluation 레코드는 당시 사용된 `model_id`/`dataset_id` 를 그대로 참조하므로, 재업로드가 과거 평가 결과의 의미를 바꾸지 않는다(재현성 보존).
5. 레코드 삭제/정리 UI 는 범위 밖으로 유지한다(FR-001 Out of scope 와 일치) — 03§5 "평가 결과는 사용자가 직접 지우기 전까지 로컬에 보존"과 합치.
6. 사용자가 동일 이름으로 재업로드하면 업로드 목록에 "같은 이름, 다른 id" 항목이 누적되어 보일 수 있다 — UX 상 업로드 시각 등 보조 식별자를 함께 보여주는 것을 frontend 구현 재량으로 권고한다(강제 아님, 02§8).

## Alternatives
| 대안 | 설명 | 기각 이유 |
|------|------|-----------|
| (a) name 등 매칭 키로 기존 레코드 UPDATE | 동일 이름 재업로드 시 기존 행을 갱신 | 매칭 키 정의(이름만? 경로? 파일 해시?)가 불명확하고, 과거 Run 이 참조하는 `model_id` 가 가리키는 내용이 조용히 바뀌어 **재현성이 깨짐**(원칙 3 위반) — 추가 설계·구현 비용도 필요(원칙 1 위반) |
| (b) name 에 UNIQUE 제약 추가 후 upsert | 스키마 변경(D-09 DDL 수정) + 충돌 시 내용 비교/덮어쓰기 로직 필요 | 스키마 변경과 추가 비교 로직이 "하루" 일정에 불필요한 과설계(원칙 1), 현재 어떤 요구사항도 이를 요구하지 않음 |
| (c) 선택한 방안: 항상 신규 INSERT, 매칭/갱신 로직 없음 | 본 ADR의 Decision | 채택 — 이미 확정된 스키마(D-09)가 추가 코드 없이 제공하는 동작, 원칙 1·3 모두 충족 |

## Consequences
- **긍정**: 스키마 변경·추가 매칭 로직 전혀 불필요 — T-009 구현은 단순 INSERT 로 충분(개발속도 1위 충족).
- **긍정**: 한 번 생성된 `model_id`/`dataset_id` 가 다른 파일로 "대체"되는 일이 없어, 과거 Run 결과의 재현성·신뢰도가 보존된다(원칙 3, KPI-02 신뢰도와 동일한 맥락).
- **부정/트레이드오프**: 동일 이름의 레코드가 재업로드마다 누적되어 업로드 목록이 길어질 수 있음 — 1인 로컬 소규모 사용 전제(01 NFR-004)에서는 영향이 작다고 판단. 필요해지면 P2 이후 "목록 정리" 기능을 별도로 검토할 수 있으나 현재는 범위 밖.
- `stories/FR-001.md`, `stories/FR-002.md` 의 Out of scope 문구("LTM I-02 미해결")를 본 ADR 의 확정 결과로 갱신해야 한다 — **product 팀 Task 후보**로 남김(architecture 는 story 파일을 직접 수정하지 않음, charter §2 소유 범위 밖).
- `app/eval/repository.py` 상단 주석(L18-22, "미정"으로 적힌 부분)을 "확정: 항상 INSERT, UPDATE 로직 없음(ADR-004)"으로 갱신해야 한다 — **backend/dba Task 후보**(T-009 구현 시 함께 반영 가능, architecture 는 쿼리 함수 영역을 직접 수정하지 않음).
- LTM I-02 해소.
