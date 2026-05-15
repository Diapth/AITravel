import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app import planner as planner_module
from app.planner import ChinaTravelPlanner, build_query, resolve_target_cities, resolve_trip_dates
from app.schemas import PlanRequest


def test_build_query_merges_optional_structured_fields():
    request = PlanRequest(
        query="请给我一个旅行规划。",
        start_city="上海",
        target_city="苏州",
        departure_date="2026-06-06",
        return_date="2026-06-07",
        days=2,
        people_number=2,
        budget=1300,
    )

    query = build_query(request)

    assert query["uid"] == "web-request"
    assert query["nature_language"] == (
        "请给我一个旅行规划。\n"
        "补充结构化需求：出发城市上海；目标城市苏州；行程天数2天；出发日期2026-06-06；回程日期2026-06-07；出行人数2人；预算1300元。"
    )
    assert query["start_city"] == "上海"
    assert query["target_city"] == "苏州"
    assert query["departure_date"] == "2026-06-06"
    assert query["return_date"] == "2026-06-07"
    assert query["date_source"] == "user"
    assert query["days"] == 2
    assert query["people_number"] == 2


def test_build_query_accepts_target_cities_and_auto_recommends_dates(monkeypatch):
    request = PlanRequest(
        query="请规划桂林和阳朔四天三晚。",
        start_city="上海",
        target_cities=["桂林", "阳朔"],
        days=4,
        people_number=2,
    )

    monkeypatch.setattr(
        planner_module,
        "date",
        type("FakeDate", (date,), {"today": classmethod(lambda cls: date(2026, 5, 14))}),
    )
    query = build_query(request)

    assert query["target_city"] == "桂林、阳朔"
    assert query["target_cities"] == ["桂林", "阳朔"]
    assert query["departure_date"] == "2026-05-16"
    assert query["return_date"] == "2026-05-19"
    assert query["date_source"] == "auto_recommended"


def test_build_query_splits_joined_target_cities_even_when_target_cities_present(monkeypatch):
    request = PlanRequest(
        query="我想去桂林阳朔玩 4 天 3 晚。",
        start_city="上海",
        target_city="桂林阳朔",
        target_cities=["桂林阳朔"],
        days=4,
        people_number=2,
    )

    monkeypatch.setattr(
        planner_module,
        "date",
        type("FakeDate", (date,), {"today": classmethod(lambda cls: date(2026, 5, 14))}),
    )
    query = build_query(request)

    assert resolve_target_cities(request) == ["桂林", "阳朔"]
    assert query["target_city"] == "桂林、阳朔"
    assert query["target_cities"] == ["桂林", "阳朔"]
    assert "目标城市桂林、阳朔" in query["nature_language"]


def test_resolve_trip_dates_infers_missing_return_date():
    request = PlanRequest(
        query="南京三天两晚",
        target_city="南京",
        days=3,
        departure_date="2026-06-01",
    )

    dates = resolve_trip_dates(request)

    assert dates["departure_date"].isoformat() == "2026-06-01"
    assert dates["return_date"].isoformat() == "2026-06-03"
    assert dates["source"] == "user_departure_auto_return"


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
    assert result["plan"]["people_number"] == 2
    assert result["plan"]["score"] == 0.95
    assert result["plan"]["route"] == ["上海", "苏州"]
    assert result["plan"]["departure_date"]
    assert result["plan"]["return_date"]
    assert result["plan"]["date_source"] == "auto_recommended"

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
    monkeypatch.setenv("CHINATRAVEL_TRIP_MEMORY_DB", str(tmp_path / "travel_memory.sqlite"))
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
    assert result["meta"]["realtime"]["enabled"] is False
    assert result["meta"]["history_reuse"] == {"enabled": False}
    assert result["meta"]["memory_write"]["success"] is True
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


def test_planner_does_not_call_tavily_when_realtime_disabled(tmp_path, monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(query="请给我规划一个苏州两日游", target_city="苏州")
    monkeypatch.setenv("TAVILY_REAL_TIME_ENABLED", "false")
    monkeypatch.setenv("CHINATRAVEL_TRIP_MEMORY_DB", str(tmp_path / "travel_memory.sqlite"))
    monkeypatch.setattr(planner_module, "fetch_business_district_context", lambda target_city: [])

    def forbidden_realtime(request):
        raise AssertionError("Tavily should not be called when realtime is disabled")

    monkeypatch.setattr(planner_module, "TavilySearchClient", forbidden_realtime)

    class FakeAgent:
        def run(self, *args, **kwargs):
            assert "realtime_context" not in kwargs["query"]
            return True, {"itinerary": [], "total_cost": 0}

    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())

    result = planner.plan(request)

    assert result["success"] is True
    assert result["meta"]["realtime"]["enabled"] is False
    assert result["meta"]["memory_write"]["success"] is True


def test_planner_records_tavily_failure_without_blocking_plan(tmp_path, monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(query="请给我规划一个苏州两日游", target_city="苏州")
    monkeypatch.setenv("TAVILY_REAL_TIME_ENABLED", "true")
    monkeypatch.setenv("CHINATRAVEL_TRIP_MEMORY_DB", str(tmp_path / "travel_memory.sqlite"))
    monkeypatch.setattr(planner_module, "fetch_business_district_context", lambda target_city: [])

    class BrokenTavilyClient:
        def search(self, *args, **kwargs):
            from app.realtime.tavily_client import TavilySearchResult

            return TavilySearchResult(
                success=False,
                evidence=[],
                error={"code": "TAVILY_REQUEST_FAILED", "message": "network down"},
            )

    class FakeAgent:
        def run(self, *args, **kwargs):
            assert "realtime_context" not in kwargs["query"]
            return True, {"itinerary": [], "total_cost": 0}

    monkeypatch.setattr(planner_module, "TavilySearchClient", lambda: BrokenTavilyClient())
    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())

    result = planner.plan(request)

    assert result["success"] is True
    assert result["meta"]["realtime"]["enabled"] is True
    assert result["meta"]["realtime"]["success"] is False
    assert result["meta"]["realtime"]["error"]["code"] == "TAVILY_REQUEST_FAILED"
    assert result["meta"]["memory_write"]["success"] is True


def test_realtime_search_query_uses_travel_guide_terms():
    request = PlanRequest(query="请给我规划一个苏州两日游", target_city="苏州")

    query = planner_module._realtime_search_query(request)

    assert "苏州" in query
    assert "\u65c5\u884c\u653b\u7565" in query
    assert "\u7f8e\u98df" in query
    assert "\u4f4f\u5bbf" in query


def test_fetch_realtime_context_retries_when_first_query_is_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_REAL_TIME_ENABLED", "true")
    monkeypatch.setenv("CHINATRAVEL_TRIP_MEMORY_DB", str(tmp_path / "memory.sqlite"))
    calls = []

    class FakeTavilyClient:
        def search(self, query, *args, **kwargs):
            calls.append(query)
            from app.realtime.evidence import normalize_evidence
            from app.realtime.tavily_client import TavilySearchResult

            if len(calls) == 1:
                return TavilySearchResult(success=True, evidence=[], usage={"credits": 1})
            return TavilySearchResult(
                success=True,
                evidence=normalize_evidence(
                    [
                        {
                            "title": "Suzhou guide",
                            "url": "https://example.com/guide",
                            "content": "Updated attraction and food tips.",
                            "score": 0.8,
                        }
                    ]
                ),
                usage={"credits": 2},
            )

    monkeypatch.setattr(planner_module, "TavilySearchClient", lambda: FakeTavilyClient())

    evidence, meta = planner_module.fetch_realtime_context(
        PlanRequest(query="\u82cf\u5dde\u4e24\u65e5\u6e38", target_city="\u82cf\u5dde")
    )

    assert len(evidence) == 1
    assert len(calls) == 2
    assert meta["searched_queries"] == calls
    assert "\u5b98\u65b9\u516c\u544a" in calls[1]


def test_fetch_realtime_context_reports_empty_evidence_reason(tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_REAL_TIME_ENABLED", "true")
    monkeypatch.setenv("CHINATRAVEL_MEMORY_DB_PATH", str(tmp_path / "memory.sqlite"))

    class EmptyTavilyClient:
        def search(self, *args, **kwargs):
            from app.realtime.tavily_client import TavilySearchResult

            return TavilySearchResult(success=True, evidence=[], usage={"credits": 1})

    monkeypatch.setattr(planner_module, "TavilySearchClient", lambda: EmptyTavilyClient())

    evidence, meta = planner_module.fetch_realtime_context(PlanRequest(query="苏州两日游", target_city="苏州"))

    assert evidence == []
    assert meta["success"] is True
    assert meta["evidence_count"] == 0
    assert meta["empty_reason"] == "NO_RELIABLE_EVIDENCE"
    assert meta["error"] is None


def test_fetch_realtime_context_exposes_evidence_in_meta(tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_REAL_TIME_ENABLED", "true")
    monkeypatch.setenv("CHINATRAVEL_TRIP_MEMORY_DB", str(tmp_path / "memory.sqlite"))

    class FakeTavilyClient:
        def search(self, *args, **kwargs):
            from app.realtime.evidence import normalize_evidence
            from app.realtime.tavily_client import TavilySearchResult

            return TavilySearchResult(
                success=True,
                evidence=normalize_evidence(
                    [
                        {
                            "title": "Suzhou travel notice",
                            "url": "https://example.com/suzhou",
                            "content": "Reservation and opening hour notice.",
                            "score": 0.8,
                        }
                    ]
                ),
                usage={"credits": 1},
            )

    monkeypatch.setattr(planner_module, "TavilySearchClient", lambda: FakeTavilyClient())

    evidence, meta = planner_module.fetch_realtime_context(PlanRequest(query="苏州两日游", target_city="苏州"))

    assert len(evidence) == 1
    assert meta["evidence"] == evidence
    assert meta["evidence_count"] == 1


def test_fetch_realtime_context_can_be_enabled_per_request(tmp_path, monkeypatch):
    monkeypatch.setenv("TAVILY_REAL_TIME_ENABLED", "false")
    monkeypatch.setenv("CHINATRAVEL_TRIP_MEMORY_DB", str(tmp_path / "memory.sqlite"))

    class FakeTavilyClient:
        def search(self, *args, **kwargs):
            from app.realtime.evidence import normalize_evidence
            from app.realtime.tavily_client import TavilySearchResult

            return TavilySearchResult(
                success=True,
                evidence=normalize_evidence(
                    [
                        {
                            "title": "Realtime guide",
                            "url": "https://example.com/guide",
                            "content": "Current visitor notice.",
                            "score": 0.8,
                        }
                    ]
                ),
                usage={"credits": 1},
            )

    monkeypatch.setattr(planner_module, "TavilySearchClient", lambda: FakeTavilyClient())

    evidence, meta = planner_module.fetch_realtime_context(
        PlanRequest(query="苏州两日游", target_city="苏州", use_realtime=True)
    )

    assert len(evidence) == 1
    assert meta["enabled"] is True
    assert meta["success"] is True


def test_estimated_hotel_cost_uses_city_and_budget():
    assert planner_module._estimated_hotel_cost("苏州", 1300, 2) == 260
    assert planner_module._estimated_hotel_cost("桂林", 600, 2) == 168
    assert planner_module._estimated_hotel_cost("北京", 600, 4) == 193.2


def test_planner_uses_amap_fallback_when_local_database_fallback_cannot_cover_city(monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(
        query="请规划天津到南京三天两夜游",
        start_city="天津",
        target_city="南京",
        days=3,
        people_number=1,
        budget=3000,
    )

    class FakeAgent:
        def run(self, *args, **kwargs):
            return False, {"error_info": "Unsupported cities 天津 -> 南京."}

    class FakeAmapClient:
        def search_pois(self, city, keywords, page_size=10):
            if keywords == "景点":
                return [
                    {"name": "中山陵园风景区", "business": {"cost": "0"}},
                    {"name": "夫子庙秦淮风光带", "business": {"cost": "0"}},
                    {"name": "南京博物院", "business": {"cost": "0"}},
                ]
            if keywords == "餐厅":
                return [{"name": "南京大牌档", "business": {"cost": "90"}}]
            if keywords == "酒店":
                return [{"name": "南京新街口酒店", "business": {"cost": "360"}}]
            if keywords in ("南京酒店", "住宿"):
                return []
            return []

        def weather(self, city):
            return {"lives": [{"city": city, "weather": "晴"}]}

    class FakeTrainClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def query_tickets(self, date, from_station, to_station, limit=5):
            return {
                "items": [
                    {
                        "train_code": "G100",
                        "from_station": from_station,
                        "to_station": to_station,
                        "depart_time": "08:00",
                        "arrive_time": "12:00",
                        "duration": "04:00",
                        "prices": {"second": "¥320.0"},
                        "seats": {"second": {"left": "有"}},
                    }
                ]
            }

    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())
    monkeypatch.setattr(planner_module, "AmapDemoClient", lambda: FakeAmapClient())
    monkeypatch.setattr(planner_module, "Train12306Client", FakeTrainClient)
    monkeypatch.setattr(planner_module, "fetch_business_district_context", lambda target_city: [])

    result = planner.plan(request)

    assert result["success"] is True
    assert result["meta"]["agent"] == "LLMNeSy+amap_fallback"
    assert result["plan"]["fallback"]["source"] == "amap"
    assert result["plan"]["start_city"] == "天津"
    assert result["plan"]["target_city"] == "南京"
    assert result["plan"]["weather"]["lives"][0]["weather"] == "晴"
    accommodation = next(activity for activity in result["plan"]["itinerary"] if activity["type"] == "accommodation")
    assert accommodation["position"] == "南京新街口酒店"
    assert accommodation["price"] == 360
    assert accommodation["price_source"] == "amap"
    trains = [activity for activity in result["plan"]["itinerary"] if activity["type"] == "train"]
    assert trains[0]["TrainID"] == "G100"
    assert trains[0]["start_time"] == "08:00"
    assert trains[0]["price"] == 320
    assert trains[0]["seat_label"] == "二等座"
    assert trains[0]["ticket_left"] == "有"


def test_planner_uses_available_12306_seat_price_when_second_class_missing(monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(
        query="请规划上海到桂林四天三晚",
        start_city="上海",
        target_city="桂林",
        days=4,
        people_number=2,
        budget=4000,
    )

    class FakeAgent:
        def run(self, *args, **kwargs):
            return False, {"error_info": "Unsupported cities 上海 -> 桂林."}

    class FakeAmapClient:
        def search_pois(self, city, keywords, page_size=10):
            if keywords == "景点":
                return [
                    {"name": f"{city}景点A", "address": city, "business": {"cost": "0"}},
                    {"name": f"{city}景点B", "address": city, "business": {"cost": "0"}},
                ]
            if keywords in ("餐厅", "美食", "当地美食"):
                return [{"name": f"{city}餐厅", "address": city, "business": {"cost": "80"}}]
            if keywords in ("酒店", f"{city}酒店", "住宿"):
                return [{"name": f"{city}真实酒店", "address": city, "business": {"cost": "360"}}]
            return []

        def weather(self, city):
            return {"lives": [{"city": city, "weather": "晴"}]}

    class FakeTrainClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def query_tickets(self, date, from_station, to_station, limit=5):
            return {
                "items": [
                    {
                        "train_code": "K1558",
                        "from_station": from_station,
                        "to_station": to_station,
                        "depart_time": "04:00",
                        "arrive_time": "05:12",
                        "duration": "25:12",
                        "prices": {"hard_seat": "¥217.0", "hard_sleeper": "¥397.0"},
                        "seats": {
                            "hard_seat": {"label": "硬座", "left": "有"},
                            "hard_sleeper": {"label": "硬卧", "left": "有"},
                        },
                    }
                ]
            }

    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())
    monkeypatch.setattr(planner_module, "AmapDemoClient", lambda: FakeAmapClient())
    monkeypatch.setattr(planner_module, "Train12306Client", FakeTrainClient)
    monkeypatch.setattr(planner_module, "fetch_business_district_context", lambda target_city: [])

    result = planner.plan(request)

    trains = [activity for activity in result["plan"]["itinerary"] if activity["type"] == "train"]
    assert trains[0]["TrainID"] == "K1558"
    assert trains[0]["price"] == 217
    assert trains[0]["seat_label"] == "硬座"
    assert trains[0]["ticket_left"] == "有"
    assert trains[0]["cost"] == 434


def test_amap_fallback_respects_late_train_arrival_and_city_bounds(monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(
        query="请规划上海到桂林两天一晚，晚上到达也要轻松一点。",
        start_city="上海",
        target_city="桂林",
        days=2,
        people_number=2,
        budget=3000,
    )

    class FakeAgent:
        def run(self, *args, **kwargs):
            return False, {"error_info": "Unsupported cities 上海 -> 桂林."}

    class FakeAmapClient:
        def search_pois(self, city, keywords, page_size=10):
            if keywords == "景点":
                return [
                    {"name": "外地同名景点", "cityname": "重庆市", "location": "106.5516,29.5630", "business": {"cost": "0"}},
                    {"name": "桂林象鼻山", "cityname": "桂林市", "location": "110.2942,25.2677", "business": {"cost": "0"}},
                    {"name": "桂林两江四湖", "cityname": "桂林市", "location": "110.2991,25.2747", "business": {"cost": "0"}},
                ]
            if keywords == "餐厅":
                return [{"name": "桂林米粉店", "cityname": "桂林市", "location": "110.29,25.27", "business": {"cost": "35"}}]
            if keywords == "酒店":
                return [{"name": "桂林中心酒店", "cityname": "桂林市", "location": "110.28,25.28", "business": {"cost": "320"}}]
            return []

        def weather(self, city):
            return {"lives": [{"city": city, "weather": "晴"}]}

    class LateTrainClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def query_tickets(self, date, from_station, to_station, limit=5):
            return {
                "items": [
                    {
                        "train_code": "G1505",
                        "from_station": from_station,
                        "to_station": to_station,
                        "depart_time": "07:50",
                        "arrive_time": "17:23",
                        "duration": "09:33",
                        "prices": {"second": "¥705.0"},
                        "seats": {"second": {"left": "8"}},
                    }
                ]
            }

    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())
    monkeypatch.setattr(planner_module, "AmapDemoClient", lambda: FakeAmapClient())
    monkeypatch.setattr(planner_module, "Train12306Client", LateTrainClient)
    monkeypatch.setattr(planner_module, "fetch_business_district_context", lambda target_city: [])

    result = planner.plan(request)

    assert result["success"] is True
    day1 = [activity for activity in result["plan"]["itinerary"] if activity["day"] == 1]
    assert day1[0]["type"] == "train"
    assert day1[1]["type"] == "restaurant"
    assert day1[1]["start_time"] >= "18:23"
    assert day1[-1]["type"] == "accommodation"
    assert all(activity.get("position") != "外地同名景点" for activity in result["plan"]["itinerary"])
    assert any(
        activity.get("position") == "桂林象鼻山"
        for activity in result["plan"]["itinerary"]
        if activity["type"] == "attraction"
    )


def test_planner_reports_no_train_inventory_when_12306_has_no_available_ticket(monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(
        query="\u8bf7\u89c4\u5212\u4e0a\u6d77\u5230\u6842\u6797\u4e24\u5929\u4e00\u665a",
        start_city="\u4e0a\u6d77",
        target_city="\u6842\u6797",
        days=2,
        people_number=2,
        budget=3000,
    )

    class FakeAgent:
        def run(self, *args, **kwargs):
            return False, {"error_info": "Unsupported cities"}

    class FakeAmapClient:
        def search_pois(self, city, keywords, page_size=10):
            if keywords == "\u666f\u70b9":
                return [
                    {"name": f"{city}\u666f\u70b9A", "address": city, "business": {"cost": "0"}},
                    {"name": f"{city}\u666f\u70b9B", "address": city, "business": {"cost": "0"}},
                ]
            if keywords in ("\u9910\u5385", "\u7f8e\u98df", "\u5f53\u5730\u7f8e\u98df"):
                return [{"name": f"{city}\u9910\u5385", "address": city, "business": {"cost": "80"}}]
            if keywords in ("\u9152\u5e97", f"{city}\u9152\u5e97", "\u4f4f\u5bbf"):
                return [{"name": f"{city}\u9152\u5e97", "address": city, "business": {"cost": "300"}}]
            return []

        def weather(self, city):
            return {"lives": [{"city": city, "weather": "\u6674"}]}

    class EmptyTrainClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def query_tickets(self, *args, **kwargs):
            return {"items": []}

    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())
    monkeypatch.setattr(planner_module, "AmapDemoClient", lambda: FakeAmapClient())
    monkeypatch.setattr(planner_module, "Train12306Client", EmptyTrainClient)
    monkeypatch.setattr(planner_module, "fetch_business_district_context", lambda target_city: [])

    result = planner.plan(request)

    assert result["success"] is False
    assert result["error"]["code"] == "TRAIN_TICKETS_UNAVAILABLE"
    assert "\u706b\u8f66\u4f59\u7968" in result["error"]["message"]


def test_planner_uses_amap_fallback_for_joined_multi_destination(monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(
        query="我想去桂林阳朔玩 4 天 3 晚，想体验漓江竹筏、遇龙河骑行和当地美食。",
        start_city="上海",
        target_city="桂林阳朔",
        days=4,
        people_number=2,
        budget=3400,
    )
    searched: list[tuple[str, str]] = []

    class FakeAgent:
        def run(self, *args, **kwargs):
            return False, {"error_info": "Unsupported cities 上海 -> 桂林阳朔."}

    class FakeAmapClient:
        def search_pois(self, city, keywords, page_size=10):
            searched.append((city, keywords))
            if keywords in ("景点", "漓江竹筏", "遇龙河", "骑行", "竹筏"):
                return [{"name": f"{city}{keywords}", "location": f"{city}-{keywords}", "business": {"cost": "0"}}]
            if keywords in ("餐厅", "美食", "当地美食"):
                return [{"name": f"{city}本地餐厅", "location": f"{city}-餐厅", "business": {"cost": "80"}}]
            if keywords == "酒店":
                return [{"name": f"{city}市区酒店", "location": f"{city}-酒店", "business": {"rating": "4.8"}}]
            if keywords == f"{city}酒店":
                return [{"name": f"{city}山水度假酒店", "location": f"{city}-真实酒店", "business": {"rating": "4.7"}}]
            if keywords == "住宿":
                return []
            return []

        def weather(self, city):
            return {"lives": [{"city": city, "weather": "晴"}]}

    class FakeTrainClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def query_tickets(self, date, from_station, to_station, *args, **kwargs):
            return {
                "items": [
                    {
                        "train_code": "G100",
                        "from_station": from_station,
                        "to_station": to_station,
                        "depart_time": "08:00",
                        "arrive_time": "12:00",
                        "duration": "04:00",
                        "prices": {"second": "楼320.0"},
                        "seats": {"second": {"left": "有"}},
                    }
                ]
            }

    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())
    monkeypatch.setattr(planner_module, "AmapDemoClient", lambda: FakeAmapClient())
    monkeypatch.setattr(planner_module, "Train12306Client", FakeTrainClient)
    monkeypatch.setattr(planner_module, "fetch_business_district_context", lambda target_city: [])

    result = planner.plan(request)

    assert result["success"] is True
    assert result["meta"]["agent"] == "LLMNeSy+amap_fallback"
    assert result["plan"]["target_cities"] == ["桂林", "阳朔"]
    assert result["plan"]["target_city"] == "桂林、阳朔"
    assert ("桂林", "景点") in searched
    assert ("阳朔", "遇龙河") in searched
    assert any(activity["city"] == "阳朔" for activity in result["plan"]["itinerary"] if activity.get("city"))
    accommodation = next(activity for activity in result["plan"]["itinerary"] if activity["type"] == "accommodation")
    assert accommodation["position"] == "桂林山水度假酒店"
    assert accommodation["price_source"] == "estimate"


def test_planner_uses_amap_fallback_for_joined_target_cities_payload(monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(
        query="我想去桂林阳朔玩 4 天 3 晚，想体验漓江竹筏、遇龙河骑行和当地美食。",
        start_city="上海",
        target_city="桂林阳朔",
        target_cities=["桂林阳朔"],
        days=4,
        people_number=2,
        budget=3400,
    )
    searched: list[tuple[str, str]] = []

    class FakeAgent:
        def run(self, *args, **kwargs):
            return False, {"error_info": "Unsupported cities 上海 -> 桂林阳朔."}

    class FakeAmapClient:
        def search_pois(self, city, keywords, page_size=10):
            searched.append((city, keywords))
            if keywords in ("景点", "漓江竹筏", "遇龙河", "骑行", "竹筏"):
                return [{"name": f"{city}{keywords}", "location": f"{city}-{keywords}", "business": {"cost": "0"}}]
            if keywords in ("餐厅", "美食", "当地美食"):
                return [{"name": f"{city}本地餐厅", "location": f"{city}-餐厅", "business": {"cost": "80"}}]
            if keywords == "酒店":
                return [{"name": f"{city}市区酒店", "location": f"{city}-酒店", "business": {"rating": "4.8"}}]
            if keywords == f"{city}酒店":
                return [{"name": f"{city}山水度假酒店", "location": f"{city}-真实酒店", "business": {"rating": "4.7"}}]
            if keywords == "住宿":
                return []
            return []

        def weather(self, city):
            return {"lives": [{"city": city, "weather": "晴"}]}

    class FakeTrainClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def query_tickets(self, date, from_station, to_station, *args, **kwargs):
            return {
                "items": [
                    {
                        "train_code": "G100",
                        "from_station": from_station,
                        "to_station": to_station,
                        "depart_time": "08:00",
                        "arrive_time": "12:00",
                        "duration": "04:00",
                        "prices": {"second": "楼320.0"},
                        "seats": {"second": {"left": "有"}},
                    }
                ]
            }

    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())
    monkeypatch.setattr(planner_module, "AmapDemoClient", lambda: FakeAmapClient())
    monkeypatch.setattr(planner_module, "Train12306Client", FakeTrainClient)
    monkeypatch.setattr(planner_module, "fetch_business_district_context", lambda target_city: [])

    result = planner.plan(request)

    assert result["success"] is True
    assert result["plan"]["target_cities"] == ["桂林", "阳朔"]
    assert ("桂林", "景点") in searched
    assert ("阳朔", "遇龙河") in searched
    assert not any(city == "桂林阳朔" for city, _keyword in searched)


def test_planner_uses_normalized_target_for_business_district_lookup(monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(
        query="我想去桂林阳朔玩 4 天 3 晚。",
        start_city="上海",
        target_city="桂林阳朔",
        target_cities=["桂林阳朔"],
        days=4,
        people_number=2,
    )
    looked_up: list[str | None] = []

    class FakeAgent:
        def run(self, query, *args, **kwargs):
            assert query["target_city"] == "桂林、阳朔"
            return True, {"itinerary": []}

    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())
    monkeypatch.setattr(planner_module, "fetch_realtime_context", lambda request: ([], {"enabled": False}))

    def fake_business_district_context(target_city, limit=5):
        looked_up.append(target_city)
        return []

    monkeypatch.setattr(planner_module, "fetch_business_district_context", fake_business_district_context)

    result = planner.plan(request)

    assert result["success"] is True
    assert looked_up == ["桂林、阳朔"]


def test_planner_reports_fallback_error_when_amap_key_cannot_be_used(monkeypatch):
    planner = ChinaTravelPlanner()
    request = PlanRequest(
        query="请规划天津到南京三天两夜游",
        start_city="天津",
        target_city="南京",
        days=3,
        people_number=1,
        budget=3000,
    )

    class FakeAgent:
        def run(self, *args, **kwargs):
            return False, {"error_info": "Unsupported cities 天津 -> 南京."}

    class BrokenAmapClient:
        def search_pois(self, *args, **kwargs):
            raise RuntimeError("USERKEY_PLAT_NOMATCH")

    monkeypatch.setattr(planner, "_load_agent", lambda: FakeAgent())
    monkeypatch.setattr(planner_module, "AmapDemoClient", lambda: BrokenAmapClient())
    monkeypatch.setattr(planner_module, "fetch_business_district_context", lambda target_city: [])

    result = planner.plan(request)

    assert result["success"] is False
    assert "fallback_error" in result["meta"]
    assert "USERKEY_PLAT_NOMATCH" in result["meta"]["fallback_error"]


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
