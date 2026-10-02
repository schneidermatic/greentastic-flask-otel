"""REST API: the parts that work without a database (the rest is exercised by the Locust load test)."""
import pytest

from .conftest import FakeElasticsearch


def test_categories(client):
    keys = [c["key"] for c in client.get("/api/categories").get_json()]
    assert keys == ["fruits", "vegetables", "handmade", "handcraft"]


def test_search(client):
    assert client.get("/api/search?q=appel").get_json()[0]["name"] == "Apple"


def test_search_unavailable(client, app):
    app.extensions["elasticsearch"] = FakeElasticsearch(broken=True)
    response = client.get("/api/search?q=apple")
    assert response.status_code == 503 and response.get_json() == {"error": "search is unavailable"}


@pytest.mark.parametrize("method, path", [("get", "/api/cart"), ("post", "/api/checkout"), ("get", "/api/orders"),
                                          ("get", "/api/profile"), ("post", "/api/products")])
def test_login_required_as_json(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401 and response.get_json() == {"error": "login required"}


def test_customer_may_not_manage(client):
    with client.session_transaction() as session:
        session.update(username="user", role="customer")
    response = client.get("/api/manage/orders")
    assert response.status_code == 403 and "error" in response.get_json()


def test_missing_fields(client):
    response = client.post("/api/login", json={"username": "user"})
    assert response.status_code == 400 and response.get_json() == {"error": "missing fields: password"}


def test_unknown_category(client):
    assert client.get("/api/products?category=cars").status_code == 404
