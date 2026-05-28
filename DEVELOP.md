**Project Overview**
- **Purpose**: Cap Art MVP — collect colored bottle caps and compose pixel art.
- **Scope**: Local dev, simple APIs, WebSocket updates, static multi-page frontend.

**Tech Stack**
- Backend: `FastAPI` + `uvicorn`
- DB: SQLAlchemy (default SQLite, configurable via `DATABASE_URL`)
- Frontend: Static HTML/CSS/JS with `anime.js` (ESM)
- Realtime: WebSockets using FastAPI + `websockets`
- Testing: `pytest`, `httpx`, FastAPI `TestClient`

**Getting Started (Windows)**
1. Create & activate a virtualenv

```bash
python -m venv .venv
source .venv/Scripts/activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Set optional env vars
- `ADMIN_TOKEN`: token required for admin endpoints
- `CORS_ORIGINS`: comma-separated origins (defaults to `*`)
- `DATABASE_URL`: override default DB (e.g. `sqlite:///./data/cap_art.db` or a Postgres URL)

4. Run the dev server

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Frontend pages:
- http://127.0.0.1:8000/
- http://127.0.0.1:8000/live
- http://127.0.0.1:8000/checkin
- http://127.0.0.1:8000/rewards

**Running Tests**

```bash
pytest -q
```

Notes:
- Tests are integration-style and will use the local SQLite DB. Consider setting `DATABASE_URL` to a temporary DB during CI.
- Admin endpoints require `ADMIN_TOKEN` to be set.

**Development Workflow**
- Create a feature branch, make small focused commits (e.g., `feat: add parse utilities`), run tests locally.
- Use `git push` to remote and open PR for review.

**Deploy / Docker (recommendation)**
- Use a production DB (Postgres) and set `DATABASE_URL` to the connection string.
- Build a small `Dockerfile` running `uvicorn app.main:app --host 0.0.0.0 --port 80`.

**Troubleshooting**
- If WebSockets fail, ensure `websockets` is installed (`pip install websockets`).
- If SQLite file can't be created, check folder permissions. The app will try to create the parent directory on startup.

