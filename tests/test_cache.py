from greentastic import cache

from .conftest import BrokenRedis


def test_loader_runs_once_until_deleted(app):
    calls = []

    def load():
        calls.append(1)
        return [{"name": "Apple"}]

    with app.app_context():
        assert cache.get_or_load("k", load) == [{"name": "Apple"}]
        assert cache.get_or_load("k", load) == [{"name": "Apple"}]  # second call is served by Redis
        assert len(calls) == 1
        cache.delete("k")
        cache.get_or_load("k", load)
        assert len(calls) == 2


def test_shop_keeps_working_without_redis(app):
    app.extensions["redis"] = BrokenRedis()
    with app.app_context():
        assert cache.get_or_load("k", lambda: [1]) == [1]
        cache.delete("k")
