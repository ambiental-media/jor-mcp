from starlette.testclient import TestClient


def test_health_endpoint() -> None:
    from src.server import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "jor-mcp"}
