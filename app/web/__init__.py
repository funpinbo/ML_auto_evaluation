"""Web UI 패키지 (소유 팀: frontend).

책임 (20-architecture-analysis.md §4): 업로드 폼, N:M 연결 화면, 지표 선택, Run 버튼,
결과 화면 렌더링. 기술: FastAPI 내장 Jinja2 템플릿 + 바닐라 JS (Node 빌드 없음, user/02§1).

하위 구조:
- templates/  Jinja2 템플릿 (.html)
- static/     바닐라 JS/CSS 등 정적 파일

app.web 은 app.api 가 호출하는 렌더링 대상일 뿐, 자체적으로 app.eval 을 직접 호출하지
않는다 (모든 데이터는 app.api 라우터를 거친다).

이 패키지를 import 하면 `app/web/routes.py` 가 로드되어 공유 FastAPI `app` 인스턴스
(`app.api.app`)에 Web UI 라우트와 정적 파일을 자가 등록한다(T-012). 런처(`app/__main__.py`,
T-036)는 `from app.api import app` 뒤에 `import app.web` 한 줄을 추가해야 웹 UI 가
실제로 서빙된다.
"""

from app.web import routes as routes
