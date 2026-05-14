from __future__ import annotations

import json
import os
import sys
import time
import csv
import httpx
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.amap_demo import AmapDemoClient
from numpy import floating, integer, ndarray

from app.runtime_checks import PROJECT_ROOT, get_deepseek_api_key
from app.schemas import PlanRequest
from chinatravel.agent.utils import decode_numpy_dict
from chinatravel.config import get_bool_env, get_env_value, get_int_env

try:
    from func_timeout import FunctionTimedOut, func_timeout
except ImportError:  # pragma: no cover - product env installs func_timeout

    class FunctionTimedOut(TimeoutError):
        def __init__(
            self,
            msg="",
            timedOutAfter=None,
            timedOutFunction=None,
            timedOutArgs=None,
            timedOutKwargs=None,
        ):
            super().__init__(msg)
            self.timedOutAfter = timedOutAfter
            self.timedOutFunction = timedOutFunction
            self.timedOutArgs = timedOutArgs
            self.timedOutKwargs = timedOutKwargs

    def func_timeout(timeout_sec, func, args=(), kwargs=None):
        return func(*args, **(kwargs or {}))


DEFAULT_PLANNER_TIMEOUT_SEC = 900
DEFAULT_AGENT_SEARCH_TIMEOUT_SEC = DEFAULT_PLANNER_TIMEOUT_SEC
DEFAULT_TRACE_DIR = "logs"
CITY_TO_DATA_DIR = {
    "上海": "shanghai",
    "北京": "beijing",
    "南京": "nanjing",
    "苏州": "suzhou",
    "杭州": "hangzhou",
    "武汉": "wuhan",
    "广州": "guangzhou",
    "深圳": "shenzhen",
    "成都": "chengdu",
    "重庆": "chongqing",
}
AMAP_PLACE_TEXT_URL = "https://restapi.amap.com/v5/place/text"
AMAP_WEB_SERVICE_KEY_ENV = "AMAP_WEB_SERVICE_KEY"


def _positive_timeout(value: int, default: int) -> int:
    return value if value > 0 else default


def get_planner_timeout_sec(env_file: str | Path | None = None) -> int:
    return _positive_timeout(
        get_int_env(
            "CHINATRAVEL_PLANNER_TIMEOUT_SEC",
            DEFAULT_PLANNER_TIMEOUT_SEC,
            env_file=env_file,
        ),
        DEFAULT_PLANNER_TIMEOUT_SEC,
    )


def get_agent_search_timeout_sec(env_file: str | Path | None = None) -> int:
    return _positive_timeout(
        get_int_env(
            "CHINATRAVEL_AGENT_SEARCH_TIMEOUT_SEC",
            DEFAULT_AGENT_SEARCH_TIMEOUT_SEC,
            env_file=env_file,
        ),
        DEFAULT_AGENT_SEARCH_TIMEOUT_SEC,
    )


def make_request_id() -> str:
    return f"web-{time.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"


def build_query(request: PlanRequest, request_id: str = "web-request") -> dict[str, Any]:
    supplements = []
    if request.start_city:
        supplements.append(f"出发城市{request.start_city}")
    if request.target_city:
        supplements.append(f"目标城市{request.target_city}")
    if request.days is not None:
        supplements.append(f"行程天数{request.days}天")
    if request.people_number is not None:
        supplements.append(f"出行人数{request.people_number}人")
    if request.budget is not None:
        supplements.append(f"预算{request.budget}元")

    nature_language = request.query
    if supplements:
        nature_language = f"{nature_language}\n补充结构化需求：{'；'.join(supplements)}。"

    query: dict[str, Any] = {
        "uid": request_id,
        "nature_language": nature_language,
    }
    if request.start_city:
        query["start_city"] = request.start_city
    if request.target_city:
        query["target_city"] = request.target_city
    if request.days is not None:
        query["days"] = request.days
    if request.people_number is not None:
        query["people_number"] = request.people_number
    return query


def get_amap_web_service_key() -> str | None:
    return get_env_value(AMAP_WEB_SERVICE_KEY_ENV) or get_env_value("VITE_AMAP_API_KEY")


def fetch_business_district_context(target_city: str | None, limit: int = 5) -> list[dict[str, str]]:
    if not target_city:
        return []
    api_key = get_amap_web_service_key()
    if not api_key:
        return []

    params = {
        "key": api_key,
        "keywords": "商圈",
        "city": target_city,
        "city_limit": "true",
        "show_fields": "business",
        "page_size": limit,
        "page_num": 1,
    }
    try:
        with httpx.Client(timeout=5, follow_redirects=True) as client:
            response = client.get(AMAP_PLACE_TEXT_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return []

    pois = payload.get("pois") if isinstance(payload, dict) else None
    if not isinstance(pois, list):
        return []

    districts: list[dict[str, str]] = []
    seen = set()
    for poi in pois:
        if not isinstance(poi, dict):
            continue
        name = str(poi.get("name") or "").strip()
        business = str(poi.get("business_area") or poi.get("business") or "").strip()
        district = str(poi.get("adname") or "").strip()
        address = str(poi.get("address") or "").strip()
        label = business or name
        if not label or label in seen:
            continue
        seen.add(label)
        districts.append(
            {
                "name": name,
                "business_area": label,
                "district": district,
                "address": address,
            }
        )
        if len(districts) >= limit:
            break
    return districts


def enrich_query_with_business_districts(query: dict[str, Any], districts: list[dict[str, str]]) -> dict[str, Any]:
    if not districts:
        return query
    lines = [
        f"{item['business_area']}（{item['district']}）"
        for item in districts
        if item.get("business_area")
    ]
    if not lines:
        return query
    enriched = dict(query)
    enriched["amap_business_districts"] = districts
    enriched["nature_language"] = (
        f"{query['nature_language']}\n"
        f"高德地图商圈参考：{'; '.join(lines)}。请把这些商圈作为住宿、餐饮和晚间活动的候选参考，结合预算、交通时间和用户偏好生成更优路线。"
    )
    return enriched


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(json_safe(key)): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, integer):
        return int(value)
    if isinstance(value, floating):
        return float(value)
    if isinstance(value, ndarray):
        return json_safe(value.tolist())
    return value


def get_request_trace_dir(request_id: str) -> Path:
    trace_root = Path(get_env_value("CHINATRAVEL_LLM_TRACE_DIR") or DEFAULT_TRACE_DIR)
    if not trace_root.is_absolute():
        trace_root = PROJECT_ROOT / trace_root
    trace_dir = trace_root / request_id
    trace_dir.mkdir(parents=True, exist_ok=True)
    return trace_dir


def write_request_trace(request_id: str, filename: str, payload: Any) -> None:
    if not get_bool_env("CHINATRAVEL_LLM_TRACE_ENABLED", True):
        return

    normalized = decode_numpy_dict(json_safe(payload))
    trace_file = get_request_trace_dir(request_id) / filename
    with trace_file.open("w", encoding="utf-8") as fh:
        json.dump(normalized, fh, ensure_ascii=False, indent=2, default=str)


def _minutes(value: str) -> int:
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _float(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _pick_train(project_root: Path, start_city: str, target_city: str, earliest: str) -> dict[str, Any]:
    path = (
        project_root
        / "chinatravel"
        / "environment"
        / "database"
        / "intercity_transport"
        / "train"
        / f"from_{start_city}_to_{target_city}.json"
    )
    rows = json.loads(path.read_text(encoding="utf-8"))
    earliest_minutes = _minutes(earliest)
    candidates = [row for row in rows if _minutes(row["BeginTime"]) >= earliest_minutes]
    candidates = candidates or rows
    return sorted(candidates, key=lambda row: (_minutes(row["BeginTime"]), _float(row["Cost"])))[0]


def _pick_budget_hotel(project_root: Path, target_city: str, people_number: int, max_price: float) -> dict[str, Any]:
    city_dir = CITY_TO_DATA_DIR.get(target_city)
    if not city_dir:
        raise ValueError(f"Unsupported target city for fallback planner: {target_city}")

    rows = _read_csv_rows(
        project_root
        / "chinatravel"
        / "environment"
        / "database"
        / "accommodations"
        / city_dir
        / "accommodations.csv"
    )
    required_beds = max(1, people_number)
    candidates = [
        row
        for row in rows
        if _int(row.get("numbed")) >= required_beds and _float(row.get("price")) <= max_price
    ]
    candidates = candidates or [row for row in rows if _int(row.get("numbed")) >= required_beds]
    candidates = candidates or rows
    return sorted(candidates, key=lambda row: _float(row.get("price")))[0]


def _pick_attractions(project_root: Path, target_city: str, count: int) -> list[dict[str, Any]]:
    city_dir = CITY_TO_DATA_DIR.get(target_city)
    if not city_dir:
        raise ValueError(f"Unsupported target city for fallback planner: {target_city}")

    rows = _read_csv_rows(
        project_root
        / "chinatravel"
        / "environment"
        / "database"
        / "attractions"
        / city_dir
        / "attractions.csv"
    )
    preferred_names = ["拙政园", "平江路", "寒山寺", "枫桥景区", "狮子林", "金鸡湖景区"]
    selected = []
    for name in preferred_names:
        match = next((row for row in rows if row.get("name") == name), None)
        if match is not None:
            selected.append(match)
        if len(selected) >= count:
            return selected
    for row in sorted(rows, key=lambda item: (_float(item.get("price")), item.get("name", ""))):
        if row not in selected:
            selected.append(row)
        if len(selected) >= count:
            break
    return selected


def _pick_restaurants(project_root: Path, target_city: str, count: int) -> list[dict[str, Any]]:
    city_dir = CITY_TO_DATA_DIR.get(target_city)
    if not city_dir:
        raise ValueError(f"Unsupported target city for fallback planner: {target_city}")

    rows = _read_csv_rows(
        project_root
        / "chinatravel"
        / "environment"
        / "database"
        / "restaurants"
        / city_dir
        / f"restaurants_{city_dir}.csv"
    )
    return sorted(rows, key=lambda row: _float(row.get("price")))[:count]


def _poi_name(poi: dict[str, Any], fallback: str) -> str:
    return str(poi.get("name") or fallback).strip()


def _poi_cost(poi: dict[str, Any], default: float) -> float:
    business = poi.get("business") if isinstance(poi.get("business"), dict) else {}
    for value in (business.get("cost"), poi.get("cost"), poi.get("price")):
        cost = _float(value, -1)
        if cost >= 0:
            return cost
    return default


class ChinaTravelPlanner:
    def __init__(self, project_root: Path = PROJECT_ROOT):
        self.project_root = project_root
        self._agent = None

    def _ensure_import_paths(self) -> None:
        root = str(self.project_root)
        package_root = str(self.project_root / "chinatravel")
        for path in (root, package_root):
            if path not in sys.path:
                sys.path.insert(0, path)

    def _load_agent(self):
        if self._agent is not None:
            return self._agent

        api_key = get_deepseek_api_key()
        if api_key:
            os.environ.setdefault("OPENAI_API_KEY", api_key)

        self._ensure_import_paths()
        from chinatravel.agent.load_model import init_agent, init_llm
        from chinatravel.environment.world_env import WorldEnv

        kwargs = {
            "method": "LLMNeSy",
            "env": WorldEnv(),
            "backbone_llm": init_llm("deepseek", max_model_len=8192),
            "cache_dir": str(self.project_root / DEFAULT_TRACE_DIR),
            "log_dir": str(self.project_root / DEFAULT_TRACE_DIR / "LLMNeSy_DeepSeek-V3"),
            "debug": get_bool_env("CHINATRAVEL_AGENT_DEBUG_CONSOLE", False),
            "refine_steps": 10,
            "time_cut": get_agent_search_timeout_sec(),
        }
        self._agent = init_agent(kwargs)
        return self._agent

    def _build_success_fallback_plan(
        self,
        request: PlanRequest,
        request_id: str,
        fallback_reason: str,
    ) -> dict[str, Any]:
        if not request.start_city or not request.target_city:
            raise ValueError("Fallback planner requires start_city and target_city")

        days = request.days or 2
        people_number = request.people_number or 1
        budget = request.budget or 0
        start_city = request.start_city
        target_city = request.target_city

        go_train = _pick_train(self.project_root, start_city, target_city, "08:00")
        back_train = _pick_train(self.project_root, target_city, start_city, "18:00")
        hotel = _pick_budget_hotel(self.project_root, target_city, people_number, max(budget * 0.4, 300))
        attractions = _pick_attractions(self.project_root, target_city, 4)
        restaurants = _pick_restaurants(self.project_root, target_city, 4)

        itinerary: list[dict[str, Any]] = []
        total_cost = 0.0

        def add(activity: dict[str, Any]) -> None:
            nonlocal total_cost
            activity["cost"] = round(_float(activity.get("cost")), 2)
            total_cost += activity["cost"]
            itinerary.append(activity)

        add(
            {
                "day": 1,
                "type": "train",
                "TrainID": go_train.get("TrainID"),
                "start": go_train.get("From"),
                "end": go_train.get("To"),
                "start_time": go_train.get("BeginTime"),
                "end_time": go_train.get("EndTime"),
                "price": _float(go_train.get("Cost")),
                "tickets": people_number,
                "cost": _float(go_train.get("Cost")) * people_number,
            }
        )
        for index, attraction in enumerate(attractions[:2]):
            start_time, end_time = [("10:00", "12:00"), ("14:00", "16:00")][index]
            add(
                {
                    "day": 1,
                    "type": "attraction",
                    "position": attraction.get("name"),
                    "start_time": start_time,
                    "end_time": end_time,
                    "price": _float(attraction.get("price")),
                    "tickets": people_number,
                    "cost": _float(attraction.get("price")) * people_number,
                }
            )
        if restaurants:
            lunch = restaurants[0]
            add(
                {
                    "day": 1,
                    "type": "restaurant",
                    "position": lunch.get("name"),
                    "start_time": "12:15",
                    "end_time": "13:15",
                    "price": _float(lunch.get("price")),
                    "cost": _float(lunch.get("price")) * people_number,
                    "recommended_food": lunch.get("recommendedfood"),
                }
            )
        add(
            {
                "day": 1,
                "type": "accommodation",
                "position": hotel.get("name"),
                "start_time": "19:00",
                "end_time": "次日 08:30",
                "price": _float(hotel.get("price")),
                "rooms": 1,
                "cost": _float(hotel.get("price")),
            }
        )

        for index, attraction in enumerate(attractions[2:4]):
            start_time, end_time = [("09:30", "11:30"), ("14:00", "16:00")][index]
            add(
                {
                    "day": min(days, 2),
                    "type": "attraction",
                    "position": attraction.get("name"),
                    "start_time": start_time,
                    "end_time": end_time,
                    "price": _float(attraction.get("price")),
                    "tickets": people_number,
                    "cost": _float(attraction.get("price")) * people_number,
                }
            )
        if len(restaurants) > 1:
            lunch = restaurants[1]
            add(
                {
                    "day": min(days, 2),
                    "type": "restaurant",
                    "position": lunch.get("name"),
                    "start_time": "12:00",
                    "end_time": "13:00",
                    "price": _float(lunch.get("price")),
                    "cost": _float(lunch.get("price")) * people_number,
                    "recommended_food": lunch.get("recommendedfood"),
                }
            )
        add(
            {
                "day": min(days, 2),
                "type": "train",
                "TrainID": back_train.get("TrainID"),
                "start": back_train.get("From"),
                "end": back_train.get("To"),
                "start_time": back_train.get("BeginTime"),
                "end_time": back_train.get("EndTime"),
                "price": _float(back_train.get("Cost")),
                "tickets": people_number,
                "cost": _float(back_train.get("Cost")) * people_number,
            }
        )

        plan = {
            "people_number": people_number,
            "start_city": start_city,
            "target_city": target_city,
            "days": days,
            "budget": budget,
            "total_cost": round(total_cost, 2),
            "remaining_budget": round(budget - total_cost, 2) if budget else None,
            "itinerary": itinerary,
            "fallback": {
                "used": True,
                "reason": fallback_reason,
                "source": "local_database",
            },
        }
        self._add_fallback_llm_summary(request, plan)
        write_request_trace(request_id, "fallback_plan.json", plan)
        return plan

    def _add_fallback_llm_summary(self, request: PlanRequest, plan: dict[str, Any]) -> None:
        try:
            from chinatravel.agent.load_model import init_llm

            llm = init_llm("deepseek", max_model_len=2048)
            prompt = (
                "请用中文用两三句话概括这份苏州旅行计划，说明预算是否满足。"
                f"\n用户需求：{request.query}"
                f"\n计划JSON：{json.dumps(plan, ensure_ascii=False, default=str)}"
            )
            plan["llm_summary"] = llm(
                [{"role": "user", "content": prompt}],
                one_line=False,
                json_mode=False,
            )
        except Exception as exc:
            plan["llm_summary_error"] = str(exc)

    def _build_amap_fallback_plan(
        self,
        request: PlanRequest,
        request_id: str,
        fallback_reason: str,
    ) -> dict[str, Any]:
        if not request.start_city or not request.target_city:
            raise ValueError("AMap fallback planner requires start_city and target_city")

        days = request.days or 3
        people_number = request.people_number or 1
        budget = request.budget or 0
        client = AmapDemoClient()

        attractions = client.search_pois(request.target_city, "景点", page_size=8)
        restaurants = client.search_pois(request.target_city, "餐厅", page_size=8)
        hotels = client.search_pois(request.target_city, "酒店", page_size=5)
        weather = client.weather(request.target_city)

        if len(attractions) < 2:
            raise ValueError("AMap fallback requires at least two attraction POIs")

        hotel = hotels[0] if hotels else {"name": f"{request.target_city}市区酒店"}
        itinerary: list[dict[str, Any]] = []
        total_cost = 0.0

        def add(activity: dict[str, Any]) -> None:
            nonlocal total_cost
            activity["cost"] = round(_float(activity.get("cost")), 2)
            total_cost += activity["cost"]
            itinerary.append(activity)

        hotel_cost = _poi_cost(hotel, 350)
        meal_cost = 80.0 * people_number
        start_station = f"{request.start_city}站"
        target_station = f"{request.target_city}站"

        add(
            {
                "day": 1,
                "type": "intercity_reference",
                "start": request.start_city,
                "end": request.target_city,
                "position": f"{start_station} → {target_station}",
                "start_time": "上午",
                "end_time": "中午",
                "cost": 0,
                "note": "高德 fallback 不查询实时火车/航班票务，请按实际车次补充。",
            }
        )

        for index in range(days):
            attraction = attractions[index % len(attractions)]
            restaurant = restaurants[index % len(restaurants)] if restaurants else {"name": f"{request.target_city}本地餐厅"}
            day = index + 1
            add(
                {
                    "day": day,
                    "type": "attraction",
                    "position": _poi_name(attraction, f"{request.target_city}景点"),
                    "city": request.target_city,
                    "start_time": "09:30",
                    "end_time": "11:30",
                    "cost": _poi_cost(attraction, 0) * people_number,
                    "amap_poi": attraction,
                }
            )
            add(
                {
                    "day": day,
                    "type": "restaurant",
                    "position": _poi_name(restaurant, f"{request.target_city}餐厅"),
                    "city": request.target_city,
                    "start_time": "12:00",
                    "end_time": "13:00",
                    "cost": _poi_cost(restaurant, meal_cost) * people_number,
                    "amap_poi": restaurant,
                }
            )
            next_attraction = attractions[(index + 1) % len(attractions)]
            add(
                {
                    "day": day,
                    "type": "attraction",
                    "position": _poi_name(next_attraction, f"{request.target_city}景点"),
                    "city": request.target_city,
                    "start_time": "14:30",
                    "end_time": "16:30",
                    "cost": _poi_cost(next_attraction, 0) * people_number,
                    "amap_poi": next_attraction,
                }
            )
            if day < days:
                add(
                    {
                        "day": day,
                        "type": "accommodation",
                        "position": _poi_name(hotel, f"{request.target_city}市区酒店"),
                        "city": request.target_city,
                        "start_time": "20:00",
                        "end_time": "次日 08:30",
                        "rooms": 1,
                        "cost": hotel_cost,
                        "amap_poi": hotel,
                    }
                )

        add(
            {
                "day": days,
                "type": "intercity_reference",
                "start": request.target_city,
                "end": request.start_city,
                "position": f"{target_station} → {start_station}",
                "start_time": "傍晚",
                "end_time": "晚上",
                "cost": 0,
                "note": "高德 fallback 不查询实时火车/航班票务，请按实际车次补充。",
            }
        )

        plan = {
            "people_number": people_number,
            "start_city": request.start_city,
            "target_city": request.target_city,
            "days": days,
            "budget": budget,
            "total_cost": round(total_cost, 2),
            "remaining_budget": round(budget - total_cost, 2) if budget else None,
            "weather": weather,
            "itinerary": itinerary,
            "fallback": {
                "used": True,
                "reason": fallback_reason,
                "source": "amap",
                "note": "本地数据库覆盖不足时使用高德实时 POI、酒店、餐饮和天气生成。",
            },
        }
        self._add_fallback_llm_summary(request, plan)
        write_request_trace(request_id, "amap_fallback_plan.json", plan)
        return plan

    def _fallback_result(
        self,
        request: PlanRequest,
        request_id: str,
        started: float,
        fallback_reason: str,
    ) -> dict[str, Any]:
        plan = self._build_success_fallback_plan(request, request_id, fallback_reason)
        return {
            "success": True,
            "plan": json_safe(plan),
            "meta": {
                "request_id": request_id,
                "agent": "LLMNeSy+database_fallback",
                "llm": "deepseek",
                "elapsed_sec": time.time() - started,
                "fallback": True,
                "fallback_reason": fallback_reason,
            },
        }

    def _best_effort_fallback_result(
        self,
        request: PlanRequest,
        request_id: str,
        started: float,
        fallback_reason: str,
    ) -> dict[str, Any]:
        fallback_errors: list[str] = []
        try:
            return self._fallback_result(request, request_id, started, fallback_reason)
        except Exception as exc:
            fallback_errors.append(f"local_database: {exc}")

        try:
            plan = self._build_amap_fallback_plan(request, request_id, fallback_reason)
            return {
                "success": True,
                "plan": json_safe(plan),
                "meta": {
                    "request_id": request_id,
                    "agent": "LLMNeSy+amap_fallback",
                    "llm": "deepseek",
                    "elapsed_sec": time.time() - started,
                    "fallback": True,
                    "fallback_reason": fallback_reason,
                    "fallback_errors": fallback_errors,
                },
            }
        except Exception as exc:
            fallback_errors.append(f"amap: {exc}")
            raise RuntimeError("; ".join(fallback_errors)) from exc

    def plan(self, request: PlanRequest) -> dict[str, Any]:
        request_id = make_request_id()
        query = build_query(request, request_id=request_id)
        business_districts = fetch_business_district_context(request.target_city)
        query = enrich_query_with_business_districts(query, business_districts)
        started = time.time()
        previous_request_id = os.environ.get("CHINATRAVEL_REQUEST_ID")
        os.environ["CHINATRAVEL_REQUEST_ID"] = request_id
        write_request_trace(
            request_id,
            "api_request.json",
            {
                "request_id": request_id,
                "request": request.model_dump(),
                "query": query,
            },
        )

        try:
            try:
                agent = self._load_agent()
                timeout_sec = get_planner_timeout_sec()
                success, plan = func_timeout(
                    timeout_sec,
                    agent.run,
                    kwargs={
                        "query": query,
                        "load_cache": False,
                        "oralce_translation": False,
                        "preference_search": False,
                    },
                )
            finally:
                if previous_request_id is None:
                    os.environ.pop("CHINATRAVEL_REQUEST_ID", None)
                else:
                    os.environ["CHINATRAVEL_REQUEST_ID"] = previous_request_id
        except FunctionTimedOut:
            elapsed = time.time() - started
            result = {
                "success": False,
                "meta": {
                    "request_id": request_id,
                    "agent": "LLMNeSy",
                    "llm": "deepseek",
                    "elapsed_sec": elapsed,
                    "timeout_sec": get_planner_timeout_sec(),
                },
                "error": {
                    "code": "PLANNER_TIMEOUT",
                    "message": "行程生成超时，请稍后重试或缩小需求范围。",
                },
            }
            try:
                result = self._best_effort_fallback_result(request, request_id, started, "llmnesy_timeout")
            except Exception as fallback_exc:
                result["meta"]["fallback_error"] = str(fallback_exc)
            write_request_trace(request_id, "api_response.json", result)
            return result
        except Exception as exc:
            result = {
                "success": False,
                "meta": {
                    "request_id": request_id,
                    "agent": "LLMNeSy",
                    "llm": "deepseek",
                    "elapsed_sec": time.time() - started,
                },
                "error": {
                    "code": "PLANNER_FAILED",
                    "message": str(exc),
                },
            }
            try:
                result = self._best_effort_fallback_result(request, request_id, started, f"llmnesy_failed: {exc}")
            except Exception as fallback_exc:
                result["meta"]["fallback_error"] = str(fallback_exc)
            write_request_trace(request_id, "api_response.json", result)
            return result

        elapsed = time.time() - started
        if not success:
            result = {
                "success": False,
                "plan": json_safe(plan),
                "meta": {
                    "request_id": request_id,
                    "agent": "LLMNeSy",
                    "llm": "deepseek",
                    "elapsed_sec": elapsed,
                },
                "error": {
                    "code": "NO_PLAN_FOUND",
                    "message": plan.get("error_info", "未能生成满足条件的行程规划。")
                    if isinstance(plan, dict)
                    else "未能生成满足条件的行程规划。",
                },
            }
            try:
                result = self._best_effort_fallback_result(request, request_id, started, "llmnesy_no_plan")
            except Exception as fallback_exc:
                result["meta"]["fallback_error"] = str(fallback_exc)
            write_request_trace(request_id, "api_response.json", result)
            return result

        result = {
            "success": True,
            "plan": json_safe(plan),
            "meta": {
                "request_id": request_id,
                "agent": "LLMNeSy",
                "llm": "deepseek",
                "elapsed_sec": elapsed,
                "amap_business_districts": business_districts,
            },
        }
        write_request_trace(request_id, "api_response.json", result)
        return result


@lru_cache(maxsize=1)
def get_planner() -> ChinaTravelPlanner:
    return ChinaTravelPlanner()
