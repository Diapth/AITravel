from fastapi.testclient import TestClient

from app.main import app


def _runtime_ready():
    return {
        "ok": True,
        "deepseek_key_configured": True,
        "database_ready": True,
        "missing_database_paths": [],
    }


def test_conversation_api_creates_conversation_without_first_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr("app.main.chat_about_trip_intent", lambda messages, user_message: "你好，我在。先告诉我你想去哪里、玩几天和预算范围吧。")
    client = TestClient(app)

    response = client.post("/api/conversations", json={"message": "我想去桂林阳朔玩 4 天"})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["current_plan"] is None
    assert data["versions"] == []
    assert data["conversation"]["current_version_id"] is None
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"
    assert "你好，我在" in data["messages"][1]["content"]


def test_conversation_generate_creates_first_plan_after_confirmation(tmp_path, monkeypatch):
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr("app.main.check_runtime", _runtime_ready)
    monkeypatch.setattr("app.main.chat_about_trip_intent", lambda messages, user_message: "我先整理需求，稍后给你确认清单。")

    class FakePlanner:
        def plan(self, request):
            assert request.query == "桂林阳朔轻松 4 天 3 晚"
            assert request.target_cities == ["桂林", "阳朔"]
            assert request.days == 4
            return {
                "success": True,
                "plan": {
                    "target_city": "桂林、阳朔",
                    "target_cities": ["桂林", "阳朔"],
                    "days": 4,
                    "itinerary": [],
                    "total_cost": 3200,
                    "llm_summary": "桂林阳朔四天轻松游",
                },
                "meta": {"request_id": "web-test"},
            }

    monkeypatch.setattr("app.main.get_planner", lambda: FakePlanner())
    client = TestClient(app)
    created = client.post("/api/conversations", json={"message": "想找一个山水目的地，四天轻松一点"}).json()

    response = client.post(
        f"/api/conversations/{created['conversation']['id']}/generate",
        json={
            "query": "桂林阳朔轻松 4 天 3 晚",
            "target_cities": ["桂林", "阳朔"],
            "days": 4,
            "people_number": 2,
            "budget": 3400,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["current_plan"]["target_city"] == "桂林、阳朔"
    assert data["conversation"]["current_version_id"] == data["version"]["id"]
    assert data["version"]["source"] == "ai_generated"
    assert data["version"]["version_number"] == 1


def test_conversation_generate_creates_editable_draft_when_planner_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr("app.main.check_runtime", _runtime_ready)
    monkeypatch.setattr("app.main.chat_about_trip_intent", lambda messages, user_message: "我会先整理规划清单。")

    class FailingPlanner:
        def plan(self, request):
            return {
                "success": False,
                "meta": {"request_id": "failed-plan", "fallback_error": "amap quota exceeded"},
                "error": {"code": "NO_PLAN_FOUND", "message": "未能生成满足条件的行程规划。"},
            }

    monkeypatch.setattr("app.main.get_planner", lambda: FailingPlanner())
    client = TestClient(app)
    created = client.post("/api/conversations", json={"message": "想去桂林阳朔"}).json()

    response = client.post(
        f"/api/conversations/{created['conversation']['id']}/generate",
        json={"query": "桂林阳朔四日游", "target_city": "桂林阳朔", "days": 4, "people_number": 2, "budget": 3400},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["version"]["source"] == "ai_generated"
    assert data["current_plan"]["fallback"]["source"] == "conversation_draft"
    assert data["current_plan"]["fallback"]["reason"] == "NO_PLAN_FOUND"
    assert "可编辑草案" in data["assistant_message"]["content"]


def test_manual_plan_edit_creates_new_version_without_overwriting(tmp_path, monkeypatch):
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr("app.main.check_runtime", _runtime_ready)
    monkeypatch.setattr("app.main.chat_about_trip_intent", lambda messages, user_message: "我会先整理规划清单。")

    class FakePlanner:
        def plan(self, request):
            return {
                "success": True,
                "plan": {
                    "target_city": "苏州",
                    "days": 2,
                    "people_number": 2,
                    "budget": 1600,
                    "total_cost": 900,
                    "itinerary": [
                        {
                            "day": 1,
                            "title": "园林",
                            "activities": [{"day": 1, "type": "attraction", "title": "拙政园", "cost": 160}],
                        }
                    ],
                    "llm_summary": "苏州两日游",
                },
                "meta": {"request_id": "manual-base"},
            }

    monkeypatch.setattr("app.main.get_planner", lambda: FakePlanner())
    client = TestClient(app)
    created = client.post("/api/conversations", json={"message": "苏州两日游"}).json()
    generated = client.post(
        f"/api/conversations/{created['conversation']['id']}/generate",
        json={"query": "苏州两日游", "target_city": "苏州", "days": 2, "people_number": 2, "budget": 1600},
    ).json()
    edited_plan = dict(generated["current_plan"])
    edited_plan["llm_summary"] = "已手动加入夜游安排"
    edited_plan["itinerary"][0]["activities"].append(
        {"day": 1, "type": "activity", "title": "平江路夜游", "start_time": "19:00", "end_time": "21:00", "cost": 0}
    )

    response = client.post(
        f"/api/conversations/{created['conversation']['id']}/manual-edit",
        json={"plan": edited_plan, "base_version_id": generated["version"]["id"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["version"]["source"] == "manual_edit"
    assert data["version"]["version_number"] == 2
    assert data["version"]["parent_version_id"] == generated["version"]["id"]
    assert data["current_plan"]["llm_summary"] == "已手动加入夜游安排"
    assert data["current_plan"]["itinerary"][0]["activities"][-1]["title"] == "平江路夜游"


def test_manual_plan_edit_reports_version_conflict(tmp_path, monkeypatch):
    from app.travel_memory import TravelMemoryStore

    monkeypatch_db = tmp_path / "memory.sqlite"
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(monkeypatch_db))
    store = TravelMemoryStore(monkeypatch_db)
    conversation = store.create_conversation(title="冲突测试")
    first = store.create_plan_version(
        conversation["id"],
        {"target_city": "苏州", "itinerary": [{"day": 1, "activities": [{"type": "attraction", "title": "拙政园"}]}]},
        source="ai_generated",
    )
    store.create_plan_version(
        conversation["id"],
        {"target_city": "苏州", "itinerary": [{"day": 1, "activities": [{"type": "activity", "title": "新版本"}]}]},
        source="manual_edit",
    )
    client = TestClient(app)

    response = client.post(
        f"/api/conversations/{conversation['id']}/manual-edit",
        json={
            "plan": {"target_city": "苏州", "itinerary": [{"day": 1, "activities": [{"type": "attraction", "title": "旧编辑"}]}]},
            "base_version_id": first["id"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VERSION_CONFLICT"


def test_manual_plan_edit_can_save_validation_warnings_with_override(tmp_path, monkeypatch):
    from app.travel_memory import TravelMemoryStore

    monkeypatch_db = tmp_path / "memory.sqlite"
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(monkeypatch_db))
    store = TravelMemoryStore(monkeypatch_db)
    conversation = store.create_conversation(title="风险保存测试")
    base = store.create_plan_version(
        conversation["id"],
        {"target_city": "苏州", "itinerary": [{"day": 1, "activities": [{"type": "attraction", "title": "拙政园"}]}]},
        source="ai_generated",
    )
    client = TestClient(app)
    invalid_plan = {"target_city": "苏州", "itinerary": [{"day": 1, "activities": [{"title": ""}]}]}

    blocked_response = client.post(
        f"/api/conversations/{conversation['id']}/manual-edit",
        json={"plan": invalid_plan, "base_version_id": base["id"]},
    )
    blocked_data = blocked_response.json()
    assert blocked_data["success"] is False
    assert blocked_data["error"]["code"] == "PLAN_VALIDATION_FAILED"
    assert blocked_data["error"]["details"]["warnings"]

    saved_response = client.post(
        f"/api/conversations/{conversation['id']}/manual-edit",
        json={"plan": invalid_plan, "base_version_id": base["id"], "validation_override": True},
    )

    assert saved_response.status_code == 200
    saved_data = saved_response.json()
    assert saved_data["success"] is True
    assert saved_data["version"]["source"] == "manual_edit"
    assert saved_data["version"]["validation_warnings"]
    detail = client.get(f"/api/conversations/{conversation['id']}").json()
    assert detail["versions"][0]["validation_warnings"]


def test_conversation_api_lists_and_reads_detail(tmp_path, monkeypatch):
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr("app.main.check_runtime", _runtime_ready)
    monkeypatch.setattr("app.main.chat_about_trip_intent", lambda messages, user_message: "收到，我会继续确认细节。")

    class FakePlanner:
        def plan(self, request):
            return {
                "success": True,
                "plan": {"target_city": "苏州", "itinerary": [], "total_cost": 900},
                "meta": {"request_id": "web-list"},
            }

    monkeypatch.setattr("app.main.get_planner", lambda: FakePlanner())
    client = TestClient(app)
    created = client.post("/api/conversations", json={"message": "苏州两日游"}).json()
    client.post(
        f"/api/conversations/{created['conversation']['id']}/generate",
        json={"query": "苏州两日游", "target_city": "苏州", "days": 2},
    )

    list_response = client.get("/api/conversations")
    detail_response = client.get(f"/api/conversations/{created['conversation']['id']}")

    assert list_response.status_code == 200
    assert list_response.json()["success"] is True
    assert list_response.json()["conversations"][0]["id"] == created["conversation"]["id"]
    assert detail_response.status_code == 200
    assert detail_response.json()["current_plan"]["target_city"] == "苏州"


def test_conversation_api_archive_restore_and_rollback(tmp_path, monkeypatch):
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr("app.main.check_runtime", _runtime_ready)
    monkeypatch.setattr("app.main.chat_about_trip_intent", lambda messages, user_message: "收到，我会继续确认细节。")

    class FakePlanner:
        def plan(self, request):
            return {
                "success": True,
                "plan": {"target_city": "桂林", "itinerary": [], "total_cost": 1800},
                "meta": {"request_id": "web-rollback"},
            }

    monkeypatch.setattr("app.main.get_planner", lambda: FakePlanner())
    client = TestClient(app)
    created = client.post("/api/conversations", json={"message": "桂林三日游"}).json()
    generated = client.post(
        f"/api/conversations/{created['conversation']['id']}/generate",
        json={"query": "桂林三日游", "target_city": "桂林", "days": 3},
    ).json()

    conversation_id = created["conversation"]["id"]
    version_id = generated["version"]["id"]

    archive_response = client.post(f"/api/conversations/{conversation_id}/archive")
    restore_response = client.post(f"/api/conversations/{conversation_id}/restore")
    rollback_response = client.post(f"/api/conversations/{conversation_id}/versions/{version_id}/restore")

    assert archive_response.status_code == 200
    assert archive_response.json()["conversation"]["status"] == "archived"
    assert restore_response.status_code == 200
    assert restore_response.json()["conversation"]["status"] == "active"
    assert rollback_response.status_code == 200
    assert rollback_response.json()["version"]["source"] == "rollback"
    assert rollback_response.json()["version"]["version_number"] == 2


def test_conversation_message_keeps_clarifying_when_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr("app.main.check_runtime", _runtime_ready)
    monkeypatch.setattr("app.main.chat_about_trip_intent", lambda messages, user_message: "成都三日游可以，我还想确认预算和同行人数。")
    client = TestClient(app)
    from app.travel_memory import TravelMemoryStore

    conversation = TravelMemoryStore(tmp_path / "memory.sqlite").create_conversation(title="空会话")
    response = client.post(f"/api/conversations/{conversation['id']}/messages", json={"message": "成都三日游"})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["current_plan"] is None
    assert data.get("version") is None
    assert data["message"]["role"] == "user"
    assert data["assistant_message"]["role"] == "assistant"
    assert "预算" in data["assistant_message"]["content"]


def test_trip_intent_readiness_waits_until_destination_is_precise(tmp_path, monkeypatch):
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr(
        "app.main.check_runtime",
        lambda: {
            "ok": False,
            "deepseek_key_configured": False,
            "database_ready": True,
            "missing_database_paths": [],
        },
    )
    client = TestClient(app)

    vague = client.post(
        "/api/trip-intent/readiness",
        json={
            "latest_message": "有什么适合放松的地方吗？",
            "messages": [{"role": "user", "content": "我想找个地方放松"}],
            "current_fields": {"query": "我想找个地方放松"},
        },
    ).json()
    precise = client.post(
        "/api/trip-intent/readiness",
        json={
            "latest_message": "从上海出发去桂林阳朔 4 天，2 个人，预算 3400",
            "messages": [{"role": "user", "content": "想看山水"}],
            "current_fields": {"query": "想看山水"},
        },
    ).json()

    assert vague["success"] is True
    assert vague["readiness"]["should_show_checklist"] is False
    assert precise["success"] is True
    assert precise["readiness"]["should_show_checklist"] is True
    assert precise["readiness"]["fields"]["target_city"] == "上海、桂林、阳朔"
    assert precise["readiness"]["fields"]["days"] == 4


def test_conversation_message_with_existing_plan_creates_ai_edit_version(tmp_path, monkeypatch):
    from app.travel_memory import TravelMemoryStore

    monkeypatch_db = tmp_path / "memory.sqlite"
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(monkeypatch_db))
    store = TravelMemoryStore(monkeypatch_db)
    conversation = store.create_conversation(title="AI 修改测试")
    base = store.create_plan_version(
        conversation["id"],
        {
            "target_city": "苏州",
            "days": 2,
            "itinerary": [{"day": 1, "activities": [{"day": 1, "type": "attraction", "title": "拙政园"}]}],
            "llm_summary": "苏州两日游",
        },
        source="ai_generated",
    )

    def fake_edit(plan, instruction, messages=None):
        edited = dict(plan)
        edited["llm_summary"] = "已改成更轻松"
        edited["itinerary"] = [
            {
                "day": 1,
                "activities": [
                    {"day": 1, "type": "attraction", "title": "拙政园", "description": instruction},
                ],
            }
        ]
        return edited

    monkeypatch.setattr("app.main.edit_plan_with_instruction", fake_edit)
    client = TestClient(app)
    response = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"message": "帮我改得轻松一点，少走路", "base_version_id": base["id"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["version"]["source"] == "ai_edit"
    assert data["version"]["parent_version_id"] == base["id"]
    assert data["current_plan"]["llm_summary"] == "已改成更轻松"
    assert "第 2 版" in data["assistant_message"]["content"]


def test_conversation_ai_edit_reports_version_conflict(tmp_path):
    from app.travel_memory import TravelMemoryStore

    monkeypatch_db = tmp_path / "memory.sqlite"
    store = TravelMemoryStore(monkeypatch_db)
    import os

    os.environ["CHINATRAVEL_MEMORY_DB_PATH"] = str(monkeypatch_db)
    conversation = store.create_conversation(title="AI 冲突测试")
    first = store.create_plan_version(
        conversation["id"],
        {"target_city": "苏州", "itinerary": [{"day": 1, "activities": [{"type": "attraction", "title": "拙政园"}]}]},
        source="ai_generated",
    )
    store.create_plan_version(
        conversation["id"],
        {"target_city": "苏州", "itinerary": [{"day": 1, "activities": [{"type": "activity", "title": "新版"}]}]},
        source="manual_edit",
    )
    client = TestClient(app)

    response = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"message": "帮我加一个夜游", "base_version_id": first["id"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VERSION_CONFLICT"


def test_recommended_plans_return_static_fallback_and_open(tmp_path, monkeypatch):
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    client = TestClient(app)

    response = client.get("/api/recommended-plans")
    recommendations = response.json()["recommendations"]
    open_response = client.post(f"/api/recommended-plans/{recommendations[0]['id']}/open")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert recommendations[0]["id"] == "sample-guilin-yangshuo"
    assert recommendations[0]["plan"]["target_city"] == "桂林、阳朔"
    assert recommendations[0]["plan"]["itinerary"]
    assert open_response.status_code == 200
    opened = open_response.json()
    assert opened["success"] is True
    assert opened["conversation"]["title"] == recommendations[0]["title"]
    assert opened["versions"][0]["source"] == "recommended"
    assert opened["current_plan"]["itinerary"]
    assert opened["messages"][0]["content"] == "已打开推荐行程，可继续告诉我你想怎么调整。"
