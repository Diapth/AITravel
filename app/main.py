from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.assistants import extract_fields_from_query, search_images
from app.planner import get_planner
from app.runtime_checks import check_runtime
from app.schemas import (
    ErrorPayload,
    FieldExtractionRequest,
    FieldExtractionResponse,
    ImageSearchResponse,
    PlanRequest,
    PlanResponse,
)


app = FastAPI(title="ChinaTravel Planner", version="1.0.0")


@app.get("/api/health")
def health() -> dict:
    return check_runtime()


@app.post("/api/extract-fields", response_model=FieldExtractionResponse, response_model_exclude_none=True)
def extract_fields(request: FieldExtractionRequest) -> FieldExtractionResponse:
    runtime_status = check_runtime()
    if not runtime_status["deepseek_key_configured"]:
        return FieldExtractionResponse(
            success=False,
            error=ErrorPayload(
                code="RUNTIME_NOT_READY",
                message="DeepSeek key 未配置完成。",
                details=runtime_status,
            ),
        )

    try:
        return FieldExtractionResponse(success=True, fields=extract_fields_from_query(request.query))
    except Exception as exc:
        return FieldExtractionResponse(
            success=False,
            error=ErrorPayload(code="FIELD_EXTRACTION_FAILED", message=str(exc)),
        )


@app.get("/api/images", response_model=ImageSearchResponse, response_model_exclude_none=True)
def images(q: str, page: int = 1) -> ImageSearchResponse:
    keyword = q.strip()
    if not keyword:
        return ImageSearchResponse(
            success=False,
            error=ErrorPayload(code="EMPTY_QUERY", message="图片搜索关键词不能为空。"),
        )

    try:
        return ImageSearchResponse(success=True, images=search_images(keyword, page=page))
    except Exception as exc:
        return ImageSearchResponse(
            success=True,
            images=[],
            error=ErrorPayload(code="IMAGE_SEARCH_UNAVAILABLE", message=str(exc)),
        )


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
