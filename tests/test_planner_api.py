import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import planner as planner_module
from app.planner import ChinaTravelPlanner, build_query
from app.schemas import PlanRequest


def test_build_query_merges_optional_structured_fields():
    request = PlanRequest(
        query="请给我一个旅行规划。",
        start_city="上海",
        target_city="苏州",
        days=2,
        people_number=2,
        budget=1300,
    )

    query = build_query(request)

    assert query["uid"] == "web-request"
    assert query["nature_language"] == (
        "请给我一个旅行规划。\n"
        "补充结构化需求：出发城市上海；目标城市苏州；行程天数2天；出行人数2人；预算1300元。"
    )
    assert query["start_city"] == "上海"
    assert query["target_city"] == "苏州"
    assert query["days"] == 2
    assert query["people_number"] == 2


def test_build_query_can_use_request_id():
    request = PlanRequest(query="请给我一个旅行规划。")

    query = build_query(request, request_id="web-20260511-test")

    assert query["uid"] == "web-20260511-test"


def test_planner_timeouts_can_be_loaded_from_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.delenv("CHINATRAVEL_PLANNER_TIMEOUT_SEC", raising=False)
    monkeypatch.delenv("CHINATRAVEL_AGENT_SEARCH_TIMEOUT_SEC", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "CHINATRAVEL_PLANNER_TIMEOUT_SEC=901",
                "CHINATRAVEL_AGENT_SEARCH_TIMEOUT_SEC=902",
            ]
        ),
        encoding="utf-8",
    )

    assert planner_module.get_planner_timeout_sec(env_file=env_file) == 901
    assert planner_module.get_agent_search_timeout_sec(env_file=env_file) == 902


def test_plan_endpoint_returns_business_error_when_runtime_is_not_ready(monkeypatch):
    monkeypatch.setattr(
        "app.main.check_runtime",
        lambda: {
            "ok": False,
            "deepseek_key_configured": False,
            "database_ready": False,
            "missing_database_paths": ["chinatravel/environment/database/poi"],
        },
    )
    client = TestClient(app)

    response = client.post("/api/plan", json={"query": "当前位置上海，去苏州玩两天。"})

    assert response.status_code == 200
    assert response.json() == {
        "success": False,
        "error": {
            "code": "RUNTIME_NOT_READY",
            "message": "DeepSeek key 或旅行数据库未配置完成。",
            "details": {
                "ok": False,
                "deepseek_key_configured": False,
                "database_ready": False,
                "missing_database_paths": ["chinatravel/environment/database/poi"],
            },
        },
    }


def test_plan_endpoint_uses_planner_and_returns_json(monkeypatch):
    monkeypatch.setattr(
        "app.main.check_runtime",
        lambda: {
            "ok": True,
            "deepseek_key_configured": True,
            "database_ready": True,
            "missing_database_paths": [],
        },
    )

    class FakePlanner:
        def plan(self, request):
            assert request.query == "当前位置上海，去苏州玩两天。"
            return {
                "success": True,
                "plan": {
                    "people_number": 1,
                    "start_city": "上海",
                    "target_city": "苏州",
                    "itinerary": [],
                },
                "meta": {"agent": "LLMNeSy", "llm": "deepseek", "elapsed_sec": 0.1},
            }

    monkeypatch.setattr("app.main.get_planner", lambda: FakePlanner())
    client = TestClient(app)

    response = client.post("/api/plan", json={"query": "当前位置上海，去苏州玩两天。"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["plan"]["itinerary"] == []


def test_planner_returns_business_error_when_agent_times_out(monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(query="当前位置上海，去苏州玩两天。")

    class SlowAgent:
        def run(self, *args, **kwargs):
            raise AssertionError("func_timeout should wrap this call")

    def fake_func_timeout(timeout_sec, func, args=(), kwargs=None):
        raise planner_module.FunctionTimedOut(
            "planner timed out",
            timedOutAfter=timeout_sec,
        )

    monkeypatch.setattr(planner, "_load_agent", lambda: SlowAgent())
    monkeypatch.setattr(planner_module, "get_planner_timeout_sec", lambda: 7)
    monkeypatch.setattr(planner_module, "func_timeout", fake_func_timeout)

    result = planner.plan(request)

    assert result["success"] is False
    assert result["error"]["code"] == "PLANNER_TIMEOUT"
    assert result["meta"]["timeout_sec"] == 7


@pytest.mark.parametrize("payload", [{"query": ""}, {"query": "   "}])
def test_plan_endpoint_rejects_blank_query(payload):
    client = TestClient(app)

    response = client.post("/api/plan", json=payload)

    assert response.status_code == 422
