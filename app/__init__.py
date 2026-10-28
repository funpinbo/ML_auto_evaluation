"""ML_miniops application package.

단일 FastAPI 프로세스 모놀리스 (ADR-001). 모듈 경계는
workspace/project/20-architecture-analysis.md §4(컴포넌트)·§5(데이터 흐름/API 계약)를
단일 출처로 한다. 이 패키지 하위 구조를 바꾸는 경우(신규 하위 패키지 추가 등)
architecture 팀 리뷰(ADR 선행 여부 확인)를 거친다.

하위 패키지:
- app.api  (backend 소유) — FastAPI 라우터
- app.eval (backend/dba 소유) — 모델 로더/호환성 필터/평가 실행기/지표 계산기/Repository
- app.web  (frontend 소유) — Jinja2 템플릿 + 정적 파일
"""
