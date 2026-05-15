from fastapi.testclient import TestClient

from app.main import app


def _runtime_ready():
    return {
        "ok": True,
        "deepseek_key_configured": True,
        "database_ready": True,
        "missing_database_paths": [],
    }


def test_conversation_api_creates_conversation_with_first_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr("app.main.check_runtime", _runtime_ready)

    class FakePlanner:
        def plan(self, request):
            assert request.query == "我想去桂林阳朔玩 4 天"
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

    response = client.post("/api/conversations", json={"message": "我想去桂林阳朔玩 4 天"})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["current_plan"]["target_city"] == "桂林、阳朔"
    assert data["conversation"]["current_version_id"] == data["versions"][0]["id"]
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"
    assert data["versions"][0]["source"] == "ai_generated"


def test_conversation_api_lists_and_reads_detail(tmp_path, monkeypatch):
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr("app.main.check_runtime", _runtime_ready)

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

    list_response = client.get("/api/conversations")
    detail_response = client.get(f"/api/conversations/{created['conversation']['id']}")

    assert list_response.status_code == 200
    assert list_response.json()["success"] is True
    assert list_response.json()["conversations"][0]["id"] == created["conversation"]["id"]
    assert detail_response.status_code == 200
    assert detail_response.json()["current_plan"]["target_city"] == "苏州"


def test_conversation_message_generates_first_plan_when_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))
    monkeypatch.setattr("app.main.check_runtime", _runtime_ready)

    class FakePlanner:
        def plan(self, request):
            return {
                "success": True,
                "plan": {"target_city": "成都", "itinerary": [], "total_cost": 1200},
                "meta": {"request_id": "web-message"},
            }

    monkeypatch.setattr("app.main.get_planner", lambda: FakePlanner())
    client = TestClient(app)
    from app.travel_memory import TravelMemoryStore

    conversation = TravelMemoryStore(tmp_path / "memory.sqlite").create_conversation(title="空会话")
    response = client.post(f"/api/conversations/{conversation['id']}/messages", json={"message": "成都三日游"})

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["current_plan"]["target_city"] == "成都"
    assert data["version"]["version_number"] == 1
