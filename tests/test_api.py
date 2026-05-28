from fastapi.testclient import TestClient

from app.main import app
from app.db import init_db, SessionLocal


# Ensure DB tables exist before running integration tests
init_db()


def test_get_state():
    with TestClient(app) as client:
        r = client.get("/api/state")
        assert r.status_code == 200
        data = r.json()
        assert "caps" in data
        assert "progress" in data


def test_add_cap():
    # This will create a cap in the local test database. Acceptable for integration smoke test.
    with TestClient(app) as client:
        payload = {"hex": "#00ff00", "nickname": "tester"}
        r = client.post("/api/caps", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert "cap" in data
        assert data["cap"]["color"]["hex"].lower() == "#00ff00"
