from __future__ import annotations

import os
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.runtime_checks import PROJECT_ROOT, get_deepseek_api_key
from app.schemas import PlanRequest


def build_query(request: PlanRequest) -> dict[str, Any]:
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
        "uid": "web-request",
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
            "debug": False,
            "refine_steps": 10,
        }
        self._agent = init_agent(kwargs)
        return self._agent

    def plan(self, request: PlanRequest) -> dict[str, Any]:
        query = build_query(request)
        started = time.time()

        try:
            agent = self._load_agent()
            success, plan = agent.run(
                query,
                load_cache=False,
                oralce_translation=False,
                preference_search=False,
            )
        except Exception as exc:
            return {
                "success": False,
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
                "agent": "LLMNeSy",
                "llm": "deepseek",
                "elapsed_sec": elapsed,
            },
        }


@lru_cache(maxsize=1)
def get_planner() -> ChinaTravelPlanner:
    return ChinaTravelPlanner()
