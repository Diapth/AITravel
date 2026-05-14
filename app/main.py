from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.amap_demo import AmapDemoClient, AmapDemoError, amap_demo_error, amap_demo_response
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
from app.train_12306 import Train12306Client, Train12306Error, train_demo_error, train_demo_response


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


@app.get("/api/amap-demo/pois")
def amap_demo_pois(city: str, keywords: str, page_size: int = 10) -> dict:
    try:
        return amap_demo_response(AmapDemoClient().search_pois(city, keywords, page_size=page_size))
    except AmapDemoError as exc:
        return amap_demo_error(exc)


@app.get("/api/amap-demo/hotels")
def amap_demo_hotels(city: str, keywords: str = "酒店", page_size: int = 10) -> dict:
    try:
        return amap_demo_response(AmapDemoClient().search_pois(city, keywords, page_size=page_size))
    except AmapDemoError as exc:
        return amap_demo_error(exc)


@app.get("/api/amap-demo/route")
def amap_demo_route(origin: str, destination: str, mode: str = "driving", city: str | None = None) -> dict:
    try:
        return amap_demo_response(AmapDemoClient().route(origin, destination, mode, city=city))
    except AmapDemoError as exc:
        return amap_demo_error(exc)


@app.get("/api/amap-demo/weather")
def amap_demo_weather(city: str, extensions: str = "base") -> dict:
    try:
        return amap_demo_response(AmapDemoClient().weather(city, extensions=extensions))
    except AmapDemoError as exc:
        return amap_demo_error(exc)


@app.get("/api/train-demo/tickets")
def train_demo_tickets(
    date: str,
    from_station: str,
    to_station: str,
    include_price: bool = True,
    limit: int = 30,
) -> dict:
    try:
        with Train12306Client() as client:
            return train_demo_response(
                client.query_tickets(
                    date,
                    from_station,
                    to_station,
                    include_price=include_price,
                    limit=limit,
                )
            )
    except Train12306Error as exc:
        return train_demo_error(exc)


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
