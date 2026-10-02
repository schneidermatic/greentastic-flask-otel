import pytest


@pytest.mark.parametrize("path", ["/", "/about", "/contact", "/login", "/register"])
def test_pages_without_database(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/profile", "/cart", "/checkout", "/orders", "/orders/1", "/manage/products", "/manage/users"])
def test_login_required(client, path):
    response = client.get(path)
    assert response.status_code == 302 and response.headers["Location"] == "/login"


def test_customer_may_not_manage(client):
    with client.session_transaction() as session:
        session.update(username="user", role="customer")
    assert client.get("/manage/products").status_code == 403


def test_unknown_category(client):
    assert client.get("/category/cars").status_code == 404


def test_euro_filter(app):
    euro = app.jinja_env.filters["euro"]
    assert euro("12.9") == "€12.90"
    assert euro(1234.5) == "€1,234.50"
