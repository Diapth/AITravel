from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.amap_demo import AmapDemoClient, AmapDemoError, amap_demo_error, amap_demo_response
from app.assistants import extract_fields_from_query, search_images
from app.planner import get_planner
from app.runtime_checks import check_runtime
from app.schemas import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationGenerateRequest,
    ConversationListResponse,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ErrorPayload,
    FieldExtractionRequest,
    FieldExtractionResponse,
    ImageSearchResponse,
    PlanRequest,
    PlanResponse,
    RecommendedPlansResponse,
)
from app.train_12306 import Train12306Client, Train12306Error, train_demo_error, train_demo_response
from app.travel_memory import TravelMemoryStore


app = FastAPI(title="ChinaTravel Planner", version="1.0.0")


def _conversation_title(message: str) -> str:
    title = message.strip().replace("\n", " ")
    return title[:24] or "未命名行程"


def _conversation_detail_response(store: TravelMemoryStore, conversation_id: str) -> ConversationDetailResponse:
    detail = store.get_conversation(conversation_id)
    if detail is None:
        return ConversationDetailResponse(
            success=False,
            error=ErrorPayload(code="CONVERSATION_NOT_FOUND", message="未找到对应会话。"),
        )
    return ConversationDetailResponse(success=True, **detail)


def _plan_summary(plan: dict | None) -> str | None:
    if not isinstance(plan, dict):
        return None
    summary = plan.get("llm_summary") or plan.get("summary") or plan.get("target_city")
    return str(summary)[:160] if summary else None


def _request_id_from_meta(meta: dict | None) -> str | None:
    if not isinstance(meta, dict):
        return None
    request_id = meta.get("request_id")
    if request_id:
        return str(request_id)
    memory_write = meta.get("memory_write")
    if isinstance(memory_write, dict) and memory_write.get("request_id"):
        return str(memory_write["request_id"])
    return None


def _generate_first_version(
    store: TravelMemoryStore,
    conversation_id: str,
    request: PlanRequest,
    *,
    user_message_row: dict | None = None,
) -> ConversationMessageResponse:
    planner_result = get_planner().plan(request)
    if not planner_result.get("success") or not isinstance(planner_result.get("plan"), dict):
        detail = store.get_conversation(conversation_id)
        return ConversationMessageResponse(
            success=False,
            conversation=detail["conversation"] if detail else None,
            message=user_message_row,
            error=ErrorPayload(
                code=str((planner_result.get("error") or {}).get("code") or "PLANNER_FAILED"),
                message=str((planner_result.get("error") or {}).get("message") or "行程生成失败。"),
                details=planner_result,
            ),
        )

    plan = planner_result["plan"]
    request_id = _request_id_from_meta(planner_result.get("meta"))
    version = store.create_plan_version(
        conversation_id,
        plan,
        source="ai_generated",
        request_id=request_id,
        summary=_plan_summary(plan),
    )
    assistant_message = store.append_message(
        conversation_id,
        "assistant",
        f"已生成第 {version['version_number']} 版行程。",
        plan_version_id=version["id"],
        request_id=request_id,
    )
    detail = store.get_conversation(conversation_id)
    return ConversationMessageResponse(
        success=True,
        conversation=detail["conversation"],
        message=user_message_row,
        assistant_message=assistant_message,
        version=version,
        current_plan=detail["current_plan"],
    )


@app.get("/api/health")
def health() -> dict:
    return check_runtime()


@app.get("/api/conversations", response_model=ConversationListResponse, response_model_exclude_none=True)
def list_conversations() -> ConversationListResponse:
    return ConversationListResponse(success=True, conversations=TravelMemoryStore().list_conversations())


@app.get("/api/recommended-plans", response_model=RecommendedPlansResponse, response_model_exclude_none=True)
def recommended_plans() -> RecommendedPlansResponse:
    return RecommendedPlansResponse(success=True, recommendations=TravelMemoryStore().recommended_plans())


@app.post(
    "/api/recommended-plans/{recommendation_id}/open",
    response_model=ConversationDetailResponse,
    response_model_exclude_none=True,
)
def open_recommended_plan(recommendation_id: str) -> ConversationDetailResponse:
    store = TravelMemoryStore()
    try:
        detail = store.open_recommended_plan(recommendation_id)
    except ValueError:
        return ConversationDetailResponse(
            success=False,
            error=ErrorPayload(code="RECOMMENDATION_NOT_FOUND", message="未找到对应推荐行程。"),
        )
    return ConversationDetailResponse(success=True, **detail)


@app.post("/api/conversations", response_model=ConversationDetailResponse)
def create_conversation(request: ConversationCreateRequest) -> ConversationDetailResponse:
    store = TravelMemoryStore()
    conversation = store.create_conversation(title=_conversation_title(request.message))
    store.append_message(conversation["id"], "user", request.message)
    store.append_message(
        conversation["id"],
        "assistant",
        "我先帮你梳理旅行需求。可以继续告诉我出发地、天数、预算、同行人和想要的节奏；信息够了以后，我会给你一张规划清单确认卡。",
    )
    return _conversation_detail_response(store, conversation["id"])


@app.get("/api/conversations/{conversation_id}", response_model=ConversationDetailResponse, response_model_exclude_none=True)
def get_conversation(conversation_id: str) -> ConversationDetailResponse:
    return _conversation_detail_response(TravelMemoryStore(), conversation_id)


@app.post(
    "/api/conversations/{conversation_id}/archive",
    response_model=ConversationDetailResponse,
    response_model_exclude_none=True,
)
def archive_conversation(conversation_id: str) -> ConversationDetailResponse:
    store = TravelMemoryStore()
    try:
        store.archive_conversation(conversation_id)
    except ValueError:
        return ConversationDetailResponse(
            success=False,
            error=ErrorPayload(code="CONVERSATION_NOT_FOUND", message="未找到对应会话。"),
        )
    return _conversation_detail_response(store, conversation_id)


@app.post(
    "/api/conversations/{conversation_id}/restore",
    response_model=ConversationDetailResponse,
    response_model_exclude_none=True,
)
def restore_conversation(conversation_id: str) -> ConversationDetailResponse:
    store = TravelMemoryStore()
    try:
        store.restore_conversation(conversation_id)
    except ValueError:
        return ConversationDetailResponse(
            success=False,
            error=ErrorPayload(code="CONVERSATION_NOT_FOUND", message="未找到对应会话。"),
        )
    return _conversation_detail_response(store, conversation_id)


@app.post(
    "/api/conversations/{conversation_id}/versions/{version_id}/restore",
    response_model=ConversationMessageResponse,
    response_model_exclude_none=True,
)
def restore_plan_version(conversation_id: str, version_id: str) -> ConversationMessageResponse:
    store = TravelMemoryStore()
    try:
        version = store.restore_version(conversation_id, version_id)
    except ValueError as exc:
        return ConversationMessageResponse(
            success=False,
            error=ErrorPayload(code="VERSION_RESTORE_FAILED", message=str(exc)),
        )
    assistant_message = store.append_message(
        conversation_id,
        "assistant",
        f"已回退并生成第 {version['version_number']} 版行程。",
        plan_version_id=version["id"],
    )
    detail = store.get_conversation(conversation_id)
    return ConversationMessageResponse(
        success=True,
        conversation=detail["conversation"] if detail else None,
        assistant_message=assistant_message,
        version=version,
        current_plan=detail["current_plan"] if detail else None,
    )


@app.post(
    "/api/conversations/{conversation_id}/messages",
    response_model=ConversationMessageResponse,
)
def append_conversation_message(conversation_id: str, request: ConversationMessageRequest) -> ConversationMessageResponse:
    store = TravelMemoryStore()
    detail = store.get_conversation(conversation_id)
    if detail is None:
        return ConversationMessageResponse(
            success=False,
            error=ErrorPayload(code="CONVERSATION_NOT_FOUND", message="未找到对应会话。"),
        )
    user_message = store.append_message(conversation_id, "user", request.message)
    if detail["conversation"]["current_version_id"]:
        updated = store.get_conversation(conversation_id)
        return ConversationMessageResponse(
            success=False,
            conversation=updated["conversation"] if updated else None,
            message=user_message,
            error=ErrorPayload(code="AI_EDIT_NOT_IMPLEMENTED", message="已有行程的继续修改将在后续版本开放。"),
        )
    assistant_message = store.append_message(
        conversation_id,
        "assistant",
        "收到。我会先把这些信息放进规划清单；如果还不确定，可以继续补充目的地、日期、预算或旅行节奏。",
    )
    updated = store.get_conversation(conversation_id)
    return ConversationMessageResponse(
        success=True,
        conversation=updated["conversation"] if updated else None,
        message=user_message,
        assistant_message=assistant_message,
        current_plan=None,
    )


@app.post(
    "/api/conversations/{conversation_id}/generate",
    response_model=ConversationMessageResponse,
    response_model_exclude_none=True,
)
def generate_conversation_plan(conversation_id: str, request: ConversationGenerateRequest) -> ConversationMessageResponse:
    runtime_status = check_runtime()
    if not runtime_status["ok"]:
        return ConversationMessageResponse(
            success=False,
            error=ErrorPayload(
                code="RUNTIME_NOT_READY",
                message="DeepSeek key 或旅行数据库未配置完成。",
                details=runtime_status,
            ),
        )
    store = TravelMemoryStore()
    detail = store.get_conversation(conversation_id)
    if detail is None:
        return ConversationMessageResponse(
            success=False,
            error=ErrorPayload(code="CONVERSATION_NOT_FOUND", message="未找到对应会话。"),
        )
    if detail["conversation"]["current_version_id"]:
        return ConversationMessageResponse(
            success=False,
            conversation=detail["conversation"],
            current_plan=detail["current_plan"],
            error=ErrorPayload(code="PLAN_ALREADY_GENERATED", message="当前会话已经生成行程，可进入工作区继续修改。"),
        )
    return _generate_first_version(store, conversation_id, request.to_plan_request())


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
