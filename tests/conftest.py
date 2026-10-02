"""Test helpers: the app with fake Redis and Elasticsearch clients, so no running service is needed."""
import pytest
import redis

from greentastic import create_app


class FakeRedis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def setex(self, key, seconds, value):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)


class BrokenRedis:
    def get(self, *args):
        raise redis.ConnectionError("down")

    setex = delete = get


class FakeElasticsearch:
    def __init__(self, products=(), broken=False):
        self.products, self.broken, self.queries = list(products), broken, []

    def search(self, index, size, query):
        if self.broken:
            raise ConnectionError("down")
        self.queries.append(query)
        return {"hits": {"hits": [{"_source": p} for p in self.products]}}


APPLE = {"id": 1, "category": "fruits", "name": "Apple", "description": "crisp", "price": 2.5,
         "stock": 50, "unit": "kg", "image": "AP.jpg"}


@pytest.fixture
def app():
    app = create_app({"TESTING": True})
    app.extensions["redis"] = FakeRedis()
    app.extensions["elasticsearch"] = FakeElasticsearch([APPLE])
    return app


@pytest.fixture
def client(app):
    return app.test_client()
