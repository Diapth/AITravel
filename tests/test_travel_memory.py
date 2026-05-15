import sqlite3

from app.schemas import PlanRequest
from app.travel_memory import TravelMemoryStore, get_memory_db_path, redact_query, request_fingerprint


def test_redact_query_masks_common_pii():
    redacted = redact_query("手机13800138000，邮箱 test@example.com，身份证11010519491231002X")

    assert "13800138000" not in redacted
    assert "test@example.com" not in redacted
    assert "11010519491231002X" not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_request_fingerprint_is_stable_for_target_city_order():
    first = PlanRequest(query="旅行", start_city="上海", target_cities=["苏州", "杭州"], days=3, people_number=2, budget=1200)
    second = PlanRequest(query="旅行", start_city="上海", target_cities=["杭州", "苏州"], days=3, people_number=2, budget=1300)

    assert request_fingerprint(first) == request_fingerprint(second)


def test_travel_memory_writes_request_plan_and_route_stats(tmp_path):
    db_path = tmp_path / "travel_memory.sqlite"
    store = TravelMemoryStore(db_path)
    request = PlanRequest(
        query="手机号13800138000，请规划上海到苏州两天。",
        start_city="上海",
        target_city="苏州",
        days=2,
        people_number=2,
        budget=1300,
    )

    result = store.write_trip(
        request,
        {"target_city": "苏州", "total_cost": 900, "itinerary": []},
        meta={"agent": "test-agent"},
        used_realtime=True,
    )

    assert result["success"] is True
    with sqlite3.connect(db_path) as conn:
        request_row = conn.execute("SELECT query_text_redacted FROM trip_requests").fetchone()
        plan_row = conn.execute("SELECT total_cost, used_realtime, source_agent FROM trip_plans").fetchone()
        stats_row = conn.execute("SELECT request_count FROM route_stats").fetchone()

    assert "13800138000" not in request_row[0]
    assert plan_row == (900.0, 1, "test-agent")
    assert stats_row == (1,)


def test_memory_db_path_prefers_new_env_var(tmp_path, monkeypatch):
    new_path = tmp_path / "new-memory.sqlite"
    old_path = tmp_path / "old-memory.sqlite"
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(new_path))
    monkeypatch.setenv("CHINATRAVEL_TRIP_MEMORY_DB", str(old_path))

    assert get_memory_db_path() == new_path.resolve()


def test_memory_db_path_keeps_legacy_env_fallback(tmp_path, monkeypatch):
    old_path = tmp_path / "legacy-memory.sqlite"
    monkeypatch.delenv("CHINATRAVEL_MEMORY_DB_PATH", raising=False)
    monkeypatch.setenv("CHINATRAVEL_TRIP_MEMORY_DB", str(old_path))

    assert get_memory_db_path() == old_path.resolve()
