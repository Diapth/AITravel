import json
from pathlib import Path

import numpy as np
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


def test_extract_fields_endpoint_uses_deepseek_helper(monkeypatch):
    monkeypatch.setattr(
        "app.main.check_runtime",
        lambda: {
            "ok": True,
            "deepseek_key_configured": True,
            "database_ready": True,
            "missing_database_paths": [],
        },
    )

    def fake_extract(query):
        assert "苏州" in query
        from app.schemas import ExtractedFields

        return ExtractedFields(
            start_city="上海",
            target_city="苏州",
            days=2,
            people_number=2,
            budget=1300,
            preferences=["自然风光", "美食体验"],
        )

    monkeypatch.setattr("app.main.extract_fields_from_query", fake_extract)
    client = TestClient(app)

    response = client.post("/api/extract-fields", json={"query": "从上海去苏州两天，两个人，预算1300"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["fields"]["target_city"] == "苏州"
    assert response.json()["fields"]["preferences"] == ["自然风光", "美食体验"]


def test_images_endpoint_degrades_to_empty_images_when_provider_fails(monkeypatch):
    def fake_search(*args, **kwargs):
        raise ValueError("provider returned warning html")

    monkeypatch.setattr("app.main.search_images", fake_search)
    client = TestClient(app)

    response = client.get("/api/images", params={"q": "苏州 拙政园"})

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["images"] == []
    assert response.json()["error"]["code"] == "IMAGE_SEARCH_UNAVAILABLE"


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


def test_planner_serializes_numpy_plan_and_writes_request_trace(tmp_path, monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(query="当前位置上海，去苏州玩两天。")

    class FakeAgent:
        def run(self, *args, **kwargs):
            return True, {
                "people_number": np.int64(2),
                "score": np.float64(0.95),
                "route": np.array(["上海", "苏州"]),
            }

    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())
    monkeypatch.setattr(planner_module, "make_request_id", lambda: "web-test-trace")
    monkeypatch.setenv("CHINATRAVEL_LLM_TRACE_ENABLED", "true")
    monkeypatch.setenv("CHINATRAVEL_LLM_TRACE_DIR", str(tmp_path))

    result = planner.plan(request)

    assert result["success"] is True
    assert result["plan"] == {
        "people_number": 2,
        "score": 0.95,
        "route": ["上海", "苏州"],
    }

    trace_dir = tmp_path / "web-test-trace"
    request_trace = json.loads((trace_dir / "api_request.json").read_text(encoding="utf-8"))
    response_trace = json.loads((trace_dir / "api_response.json").read_text(encoding="utf-8"))
    assert request_trace["request"]["query"] == "当前位置上海，去苏州玩两天。"
    assert response_trace["plan"]["route"] == ["上海", "苏州"]


def test_structured_request_still_uses_agent_and_writes_trace(tmp_path, monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(
        query="当前位置上海。我和女朋友想去苏州玩两天，预算1300元，请给我一个旅行规划。",
        start_city="上海",
        target_city="苏州",
        days=2,
        people_number=2,
        budget=1300,
    )

    monkeypatch.setattr(planner_module, "make_request_id", lambda: "web-fast-success")
    monkeypatch.setattr(planner_module, "fetch_business_district_context", lambda target_city: [])
    monkeypatch.setenv("CHINATRAVEL_LLM_TRACE_ENABLED", "true")
    monkeypatch.setenv("CHINATRAVEL_LLM_TRACE_DIR", str(tmp_path))

    class FakeAgent:
        def run(self, *args, **kwargs):
            query = kwargs["query"]
            assert query["start_city"] == "上海"
            assert query["target_city"] == "苏州"
            assert query["days"] == 2
            assert query["people_number"] == 2
            return True, {
                "start_city": query["start_city"],
                "target_city": query["target_city"],
                "days": query["days"],
                "people_number": query["people_number"],
                "total_cost": 1200,
                "itinerary": [],
            }

    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())

    result = planner.plan(request)

    assert result["success"] is True
    assert result["plan"]["start_city"] == "上海"
    assert result["plan"]["target_city"] == "苏州"
    assert result["plan"]["total_cost"] <= 1300
    assert result["meta"]["agent"] == "LLMNeSy"
    assert "fallback" not in result["meta"]
    assert not (tmp_path / "web-fast-success" / "fallback_plan.json").exists()
    assert (tmp_path / "web-fast-success" / "api_response.json").exists()


def test_business_districts_enrich_agent_query(monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(
        query="请给我规划一个苏州两日游",
        start_city="上海",
        target_city="苏州",
        days=2,
        people_number=2,
        budget=1300,
    )
    districts = [{"business_area": "观前街", "district": "姑苏区", "name": "观前街", "address": ""}]
    monkeypatch.setattr(planner_module, "fetch_business_district_context", lambda target_city: districts)

    class FakeAgent:
        def run(self, *args, **kwargs):
            query = kwargs["query"]
            assert query["amap_business_districts"] == districts
            assert "高德地图商圈参考" in query["nature_language"]
            return True, {"itinerary": [], "total_cost": 0}

    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())

    result = planner.plan(request)

    assert result["success"] is True
    assert result["meta"]["amap_business_districts"] == districts


def test_request_trace_defaults_to_logs_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(planner_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("CHINATRAVEL_LLM_TRACE_DIR", raising=False)

    trace_dir = planner_module.get_request_trace_dir("web-default-log")

    assert trace_dir.resolve() == tmp_path / "logs" / "web-default-log"
    assert Path(tmp_path / "logs" / "web-default-log").exists()


@pytest.mark.parametrize("payload", [{"query": ""}, {"query": "   "}])
def test_plan_endpoint_rejects_blank_query(payload):
    client = TestClient(app)

    response = client.post("/api/plan", json=payload)

    assert response.status_code == 422
