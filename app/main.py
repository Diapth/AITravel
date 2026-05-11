from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.planner import get_planner
from app.runtime_checks import check_runtime
from app.schemas import ErrorPayload, PlanRequest, PlanResponse


app = FastAPI(title="ChinaTravel Planner", version="1.0.0")


@app.get("/api/health")
def health() -> dict:
    return check_runtime()


@app.post("/api/plan", response_model=PlanResponse, response_model_exclude_none=True)
def plan(request: PlanRequest) -> PlanResponse:
    runtime_status = check_runtime()
    if not runtime_status["ok"]:
        return PlanResponse(
            success=False,
            error=ErrorPayload(
                code="RUNTIME_NOT_READY",
                message="DeepSeek key 或旅行数据库未配置完成。",
                details=runtime_status,
            ),
        )

    return PlanResponse.model_validate(get_planner().plan(request))


frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
