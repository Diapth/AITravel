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


def test_conversation_schema_and_indexes_are_initialized(tmp_path):
    db_path = tmp_path / "memory.sqlite"
    store = TravelMemoryStore(db_path)

    store.initialize()

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
            )
        }
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}

    assert {"conversations", "conversation_messages", "plan_versions"}.issubset(tables)
    assert "idx_conversations_updated_at" in indexes
    assert "idx_conversation_messages_thread" in indexes
    assert "idx_plan_versions_thread" in indexes


def test_create_conversation_and_get_detail(tmp_path):
    store = TravelMemoryStore(tmp_path / "memory.sqlite")

    conversation = store.create_conversation(title="桂林阳朔 4 天")
    detail = store.get_conversation(conversation["id"])

    assert conversation["title"] == "桂林阳朔 4 天"
    assert conversation["status"] == "active"
    assert conversation["current_version_id"] is None
    assert detail is not None
    assert detail["conversation"]["id"] == conversation["id"]
    assert detail["messages"] == []
    assert detail["versions"] == []
    assert detail["current_plan"] is None


def test_append_message_increments_sequence_per_conversation(tmp_path):
    store = TravelMemoryStore(tmp_path / "memory.sqlite")
    first = store.create_conversation(title="第一条")
    second = store.create_conversation(title="第二条")

    first_user = store.append_message(first["id"], "user", "我想去桂林")
    first_assistant = store.append_message(first["id"], "assistant", "已收到")
    second_user = store.append_message(second["id"], "user", "我想去苏州")

    assert first_user["sequence"] == 1
    assert first_assistant["sequence"] == 2
    assert second_user["sequence"] == 1


def test_create_plan_version_updates_current_version(tmp_path):
    store = TravelMemoryStore(tmp_path / "memory.sqlite")
    conversation = store.create_conversation(title="桂林阳朔")

    version_1 = store.create_plan_version(
        conversation["id"],
        {"target_city": "桂林", "itinerary": []},
        source="ai_generated",
        summary="第一版",
    )
    version_2 = store.create_plan_version(
        conversation["id"],
        {"target_city": "阳朔", "itinerary": []},
        source="ai_edit",
        parent_version_id=version_1["id"],
        summary="第二版",
    )
    detail = store.get_conversation(conversation["id"])

    assert version_1["version_number"] == 1
    assert version_2["version_number"] == 2
    assert version_2["parent_version_id"] == version_1["id"]
    assert detail["conversation"]["current_version_id"] == version_2["id"]
    assert detail["current_plan"]["target_city"] == "阳朔"
    assert [version["version_number"] for version in detail["versions"]] == [2, 1]


def test_list_conversations_orders_by_updated_time(tmp_path):
    store = TravelMemoryStore(tmp_path / "memory.sqlite")
    first = store.create_conversation(title="第一条")
    second = store.create_conversation(title="第二条")
    store.append_message(first["id"], "user", "更新第一条")

    conversations = store.list_conversations()

    assert [item["id"] for item in conversations] == [first["id"], second["id"]]


def test_archive_and_restore_conversation(tmp_path):
    store = TravelMemoryStore(tmp_path / "memory.sqlite")
    conversation = store.create_conversation(title="待归档")

    archived = store.archive_conversation(conversation["id"])
    restored = store.restore_conversation(conversation["id"])

    assert archived["status"] == "archived"
    assert restored["status"] == "active"


def test_restore_version_creates_rollback_copy(tmp_path):
    store = TravelMemoryStore(tmp_path / "memory.sqlite")
    conversation = store.create_conversation(title="回退")
    version_1 = store.create_plan_version(
        conversation["id"],
        {"target_city": "苏州", "itinerary": []},
        source="ai_generated",
        summary="第一版",
    )
    version_2 = store.create_plan_version(
        conversation["id"],
        {"target_city": "杭州", "itinerary": []},
        source="ai_edit",
        parent_version_id=version_1["id"],
        summary="第二版",
    )

    rollback = store.restore_version(conversation["id"], version_1["id"])
    detail = store.get_conversation(conversation["id"])

    assert rollback["source"] == "rollback"
    assert rollback["parent_version_id"] == version_2["id"]
    assert rollback["version_number"] == 3
    assert detail["conversation"]["current_version_id"] == rollback["id"]
    assert detail["current_plan"]["target_city"] == "苏州"
