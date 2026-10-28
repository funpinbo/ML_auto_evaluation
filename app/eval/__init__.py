"""평가 로직 패키지 (소유 팀: backend, 데이터 접근 계층은 dba).

20-architecture-analysis.md §4 컴포넌트 표와 1:1 대응하는 모듈 경계(파일명 고정,
ADR 없이 이름을 바꾸지 않는다):

- model_loader.py    모델 로더/어댑터 — 업로드 스크립트 동적 import, predict 계약 검증 (ADR-002, QS-6)
- compatibility.py   호환성 필터 — problem_type <-> METRIC_COMPATIBILITY 검사 (ADR-003)
- engine.py          평가 실행기 — (model,dataset,metric) 조합 순회 오케스트레이션
- metrics.py         지표 계산기 — accuracy/f1/rmse (scikit-learn.metrics)
- repository.py       데이터 접근 계층 (dba 소유) — Model/Dataset/Link/Run/Evaluation CRUD
- visualize.py       시각화 생성기 (frontend 소유) — pandas+matplotlib 집계/그래프

engine.py 는 model_loader -> compatibility -> metrics -> repository 순서로 호출한다
(20-architecture-analysis.md §4 다이어그램). 각 모듈은 서로 다른 소유 팀이 구현하므로
함수 시그니처를 바꿀 때는 architecture 리뷰(팀 간 계약 변경 여부 확인)를 거친다.
"""
