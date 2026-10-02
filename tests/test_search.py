from .conftest import FakeElasticsearch


def test_search_page_shows_hits(client, app):
    response = client.get("/search?q=appel")
    assert response.status_code == 200
    assert b"Apple" in response.data and b"/static/fruits/AP.jpg" in response.data
    assert app.extensions["elasticsearch"].queries[0]["multi_match"]["fuzziness"] == "AUTO"


def test_search_unavailable(client, app):
    app.extensions["elasticsearch"] = FakeElasticsearch(broken=True)
    response = client.get("/search?q=apple")
    assert b"currently unavailable" in response.data


def test_suggest(client):
    assert client.get("/api/suggest?q=app").get_json() == [{"name": "Apple", "category": "fruits"}]
    assert client.get("/api/suggest?q=").get_json() == []


def test_suggest_without_elasticsearch(client, app):
    app.extensions["elasticsearch"] = FakeElasticsearch(broken=True)
    assert client.get("/api/suggest?q=app").get_json() == []
