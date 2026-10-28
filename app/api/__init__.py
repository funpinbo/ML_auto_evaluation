"""API 라우터 패키지 (소유 팀: backend).

책임 (20-architecture-analysis.md §4): REST 엔드포인트, 요청 검증(pydantic), 라우팅.
의존: app.eval (모델 로더, 평가 실행기, Repository), app.web (렌더링 응답 시).

계약 원천: workspace/project/20-architecture-analysis.md §5 (이 패키지에 contracts/
디렉토리를 별도로 두지 않는다 — user/02§6: OpenAPI 는 FastAPI 자동생성 문서 사용).
구현 중인 엔드포인트가 §5 표와 달라지면 같은 Task 안에서 §5 표를 갱신한다.

§5 가 정의하는 엔드포인트:
- POST /models                 -> 201 {model_id}              (ADR-002)
- GET /models                  -> 200 [{model_id,name,framework,problem_type}]  (T-040/D-21, T-011)
- POST /datasets                -> 201 {dataset_id}            (ADR-002 §3, 마지막 컬럼=라벨)
- GET /datasets                 -> 200 [{dataset_id,name}]     (T-040/D-22, T-011)
- POST /links, GET /links      -> 201 / 200
- POST /runs                   -> 201 {run_id, evaluations:[...]}  (ADR-003)
- GET /runs/{run_id}/results   -> 200 (HTML 또는 JSON)

이 패키지의 `app` 은 FastAPI 애플리케이션 인스턴스다(T-010 에서 최초 생성). 각 기능별
라우터(`models.py`, `datasets.py`(T-011, 완료), `links.py`(T-013, 완료), `runs.py`(T-015) 등)를
`include_router` 로 여기에 등록한다. 서버 기동(`uvicorn.run(app, host="127.0.0.1")`)은
별도 런처(`app/__main__.py`, ADR-005/T-036)의 책임이며, 이 모듈은 FastAPI 인스턴스
생성과 라우터 등록만 담당한다. 단위/통합 테스트는 `fastapi.testclient.TestClient(app)`
으로 실제 서버 기동 없이 검증한다.
"""

from fastapi import FastAPI

from app.api.datasets import router as datasets_router
from app.api.links import router as links_router
from app.api.models import router as models_router

app = FastAPI(title="ML MiniOps")
app.include_router(models_router)
app.include_router(datasets_router)
app.include_router(links_router)

__all__ = ["app"]
