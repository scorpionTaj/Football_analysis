import time

from fastapi.testclient import TestClient

from football_analysis.api import queries
from football_analysis.api.app import create_app
from football_analysis.api.response_cache import RedisResponseCache
from football_analysis.ingest import connect
from test_api import seed


class MemoryRedis:
    def __init__(self):
        self.values = {}
        self.ttls = []

    def get(self, key):
        return self.values.get(key)

    def set(self, key, body, ex):
        self.values[key] = body
        self.ttls.append(ex)


def test_catalog_and_overview_hit_cache_with_canonical_full_params(tmp_path, monkeypatch):
    db = tmp_path / "api.duckdb"
    seed(db)
    redis = MemoryRedis()
    calls = {"catalog": 0, "overview": 0}
    original_catalog, original_overview = queries.catalog, queries.overview

    def catalog(store):
        calls["catalog"] += 1
        return original_catalog(store)

    def overview(store, *args):
        calls["overview"] += 1
        return original_overview(store, *args)

    monkeypatch.setattr(queries, "catalog", catalog)
    monkeypatch.setattr(queries, "overview", overview)
    api = TestClient(create_app(db, response_cache=RedisResponseCache(redis)))

    first = api.get("/api/v1/catalog?x=1&y=2")
    same = api.get("/api/v1/catalog?y=2&x=1")
    different = api.get("/api/v1/catalog?x=2&y=2")
    assert first.status_code == same.status_code == different.status_code == 200
    assert first.json() == same.json()
    assert first.headers["ETag"] == same.headers["ETag"]
    assert first.headers["ETag"] != different.headers["ETag"]
    assert calls["catalog"] == 2

    repeated = api.get("/api/v1/catalog?x=1&x=2")
    reversed_repeated = api.get("/api/v1/catalog?x=2&x=1")
    assert repeated.headers["ETag"] != reversed_repeated.headers["ETag"]
    assert calls["catalog"] == 4

    params = {"team": "Arsenal", "competition": "E0", "season": 2024}
    overview = api.get("/api/v1/overview", params=params)
    assert api.get("/api/v1/overview", params=params).json() == overview.json()
    assert api.get("/api/v1/overview", params={**params, "season": 2026}).status_code == 200
    assert calls["overview"] == 2
    assert redis.ttls == [300, 300, 300, 300, 60, 60]


def test_conditional_requests_keep_headers_and_skip_query(tmp_path, monkeypatch):
    db = tmp_path / "api.duckdb"
    seed(db)
    api = TestClient(create_app(db, response_cache=RedisResponseCache(MemoryRedis())))
    for url in ("/api/v1/catalog", "/api/v1/overview?team=Arsenal&season=2024"):
        first = api.get(url)
        assert first.status_code == 200
        def should_not_run(*_args, **_kwargs):
            raise AssertionError("conditional request queried DuckDB")
        name = "catalog" if "catalog" in url else "overview"
        with monkeypatch.context() as patch:
            patch.setattr(queries, name, should_not_run)
            conditional = api.get(url, headers={"If-None-Match": first.headers["ETag"]})
        assert conditional.status_code == 304
        assert conditional.content == b""
        assert conditional.headers["ETag"] == first.headers["ETag"]
        assert conditional.headers["Cache-Control"] == first.headers["Cache-Control"]


def test_refresh_replaces_generation_for_media_and_reference_changes(tmp_path):
    db = tmp_path / "api.duckdb"
    seed(db)
    redis = MemoryRedis()

    def refresh(_request, _progress):
        with connect(db) as con:
            con.execute("""
                INSERT INTO competition_media
                (source, league_code, league_id, league, badge_url, fetched_at)
                VALUES ('test', 'E0', '1', 'Premier League', 'https://example.test/new.png', current_timestamp)
            """)
            con.execute("UPDATE reference_standings SET points = 8 WHERE league = 'E0'")

    app = create_app(db, refresh_runner=refresh, response_cache=RedisResponseCache(redis))
    api = TestClient(app)
    old = api.get("/api/v1/catalog")
    old_standings = api.get("/api/v1/standings?competition=E0&season=2024")
    assert api.post("/api/v1/refresh", json={"target_step": 1}).status_code == 202
    for _ in range(200):
        if api.get("/api/v1/refresh").json()["status"] == "success":
            break
        time.sleep(0.01)
    else:
        raise AssertionError("refresh did not complete")

    new = api.get("/api/v1/catalog")
    assert new.status_code == 200
    assert new.headers["ETag"] != old.headers["ETag"]
    competition = next(item for item in new.json()["competitions"] if item["code"] == "E0")
    assert competition["badge_url"] == "https://example.test/new.png"
    assert api.get("/api/v1/standings?competition=E0&season=2024").headers["ETag"] != old_standings.headers["ETag"]


def test_redis_outage_falls_back_to_duckdb(tmp_path):
    db = tmp_path / "api.duckdb"
    seed(db)

    class BrokenRedis:
        def get(self, _key):
            raise ConnectionError("Redis down")

        def set(self, _key, _body, ex):
            raise ConnectionError("Redis down")

    api = TestClient(create_app(db, response_cache=RedisResponseCache(BrokenRedis())))
    for url in ("/api/v1/catalog", "/api/v1/overview?season=2024"):
        response = api.get(url)
        assert response.status_code == 200
        assert response.json()
        assert api.get(url, headers={"If-None-Match": response.headers["ETag"]}).status_code == 304
