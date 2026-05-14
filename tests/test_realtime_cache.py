from datetime import datetime, timezone

from app.realtime.cache import SearchCache, build_cache_key


def test_search_cache_hits_before_expiry(tmp_path):
    db_path = tmp_path / "memory.sqlite"
    cache = SearchCache(db_path)
    key = build_cache_key("tavily", "苏州 博物馆", {"max_results": 3})
    now = datetime(2026, 5, 14, tzinfo=timezone.utc)
    response = {"success": True, "evidence": [{"title": "公告"}], "usage": {"credits": 1}}

    cache.set(
        key,
        provider="tavily",
        query="苏州 博物馆",
        params={"max_results": 3},
        response=response,
        now=now,
        ttl_hours=1,
    )

    assert cache.get(key, now=now) == response


def test_search_cache_missing_table_is_cache_miss(tmp_path):
    cache = SearchCache(tmp_path / "memory.sqlite")

    assert cache.get("missing") is None


def test_search_cache_misses_after_expiry(tmp_path):
    db_path = tmp_path / "memory.sqlite"
    cache = SearchCache(db_path)
    key = build_cache_key("tavily", "苏州 博物馆", {"max_results": 3})
    now = datetime(2026, 5, 14, tzinfo=timezone.utc)
    cache.set(
        key,
        provider="tavily",
        query="苏州 博物馆",
        params={"max_results": 3},
        response={"success": True, "evidence": [], "usage": {}},
        now=now,
        ttl_hours=1,
    )

    later = datetime(2026, 5, 14, 1, 0, 1, tzinfo=timezone.utc)

    assert cache.get(key, now=later) is None
