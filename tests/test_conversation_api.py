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
    assert open_response.status_code == 200
    opened = open_response.json()
    assert opened["success"] is True
    assert opened["conversation"]["title"] == recommendations[0]["title"]
    assert opened["versions"][0]["source"] == "recommended"
    assert opened["messages"][0]["content"] == "已打开推荐行程，可继续告诉我你想怎么调整。"
