"""The simulated errors (the ones that need PostgreSQL are covered by the load test)."""
from .conftest import FakeElasticsearch


def test_overview(client):
    paths = [entry["path"] for entry in client.get("/api/simulate/").get_json()]
    assert "/api/simulate/error" in paths and "/api/simulate/timeout" in paths


def test_error(client):
    response = client.get("/api/simulate/error")
    assert response.status_code == 500 and "simulated failure" in response.get_json()["error"]


def test_crash(client, app):
    app.config["PROPAGATE_EXCEPTIONS"] = False  # behave like production instead of raising in the test
    assert client.get("/api/simulate/crash").status_code == 500


def test_timeout(client):
    response = client.get("/api/simulate/timeout?seconds=0.01")
    assert response.status_code == 504 and "payment provider" in response.get_json()["error"]


def test_search_error(client, app):
    app.extensions["elasticsearch"] = FakeElasticsearch(broken=True)
    assert client.get("/api/simulate/search-error").status_code == 502
