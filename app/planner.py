from __future__ import annotations

import os
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.runtime_checks import PROJECT_ROOT, get_deepseek_api_key
from app.schemas import PlanRequest
from chinatravel.config import get_bool_env, get_int_env

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
            "cache_dir": str(self.project_root / "cache"),
            "log_dir": str(self.project_root / "cache" / "LLMNeSy_DeepSeek-V3"),
            "debug": get_bool_env("CHINATRAVEL_AGENT_DEBUG_CONSOLE", False),
            "refine_steps": 10,
            "time_cut": get_agent_search_timeout_sec(),
        }
        self._agent = init_agent(kwargs)
        return self._agent

    def plan(self, request: PlanRequest) -> dict[str, Any]:
        request_id = make_request_id()
        query = build_query(request, request_id=request_id)
        started = time.time()
        previous_request_id = os.environ.get("CHINATRAVEL_REQUEST_ID")
        os.environ["CHINATRAVEL_REQUEST_ID"] = request_id

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
            return {
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
        except Exception as exc:
            return {
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

        elapsed = time.time() - started
        if not success:
            return {
                "success": False,
                "plan": plan,
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

        return {
            "success": True,
            "plan": plan,
            "meta": {
                "request_id": request_id,
                "agent": "LLMNeSy",
                "llm": "deepseek",
                "elapsed_sec": elapsed,
            },
        }


@lru_cache(maxsize=1)
def get_planner() -> ChinaTravelPlanner:
    return ChinaTravelPlanner()
