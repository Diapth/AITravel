from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.schemas import ExtractedFields
from chinatravel.agent.load_model import init_llm


IMAGE_SEARCH_URL = "https://zj.v.api.aa1.cn/api/so-baidu-img/"
PREFERENCE_OPTIONS = ["自然风光", "休闲度假", "美食体验", "文化体验", "户外活动", "拍照打卡", "亲子家庭", "当地生活"]


def chat_about_trip_intent(messages: list[dict[str, Any]], user_message: str) -> str:
    llm = init_llm("deepseek", max_model_len=2048)
    recent_messages = messages[-8:]
    prompt = (
        "你是 ChinaTravel Planner 的旅行需求澄清助手，正在和用户进行生成行程前的自然对话。\n"
        "要求：\n"
        "1. 必须用简洁中文回复，2 到 5 句话。\n"
        "2. 如果用户只是问候或闲聊，要正常回应，并自然引导他描述想去哪里、天数、预算、同行人和旅行节奏。\n"
        "3. 如果信息不足，只追问最关键的 1 到 3 个问题，不要假装已经生成行程。\n"
        "4. 如果用户明确要求生成，或目的地、天数、人数/预算等信息基本足够，先说明会整理规划清单让用户确认。\n"
        "5. 不要输出 JSON，不要输出 Markdown 表格，不要说自己无法联网。\n\n"
        f"最近对话：{json.dumps(recent_messages, ensure_ascii=False, default=str)}\n"
        f"用户最新消息：{user_message}"
    )
    raw = llm([{"role": "user", "content": prompt}], one_line=False, json_mode=False)
    text = str(raw).strip()
    if not text or "Request failed" in text:
        return "你好，我在。你可以先告诉我想去哪里、准备玩几天、预算大概多少，以及希望轻松还是紧凑；信息够了以后我会给你一张规划清单确认卡。"
    return text[:600]


def _loads_mixed_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for match in reversed(list(re.finditer(r"\{", text))):
        try:
            payload, _ = decoder.raw_decode(text[match.start() :])
            return payload
        except json.JSONDecodeError:
            continue
    raise json.JSONDecodeError("No JSON object found", text, 0)


def extract_fields_from_query(query: str) -> ExtractedFields:
    llm = init_llm("deepseek", max_model_len=2048)
    prompt = (
        "你是旅行需求信息抽取器。请只返回 JSON，不要解释。"
        "字段：start_city, target_city, days, people_number, budget, preferences。"
        "preferences 只能从以下中文标签里选择："
        f"{'、'.join(PREFERENCE_OPTIONS)}。"
        "budget 返回数字，表示总预算或人均预算中用户明确给出的金额；无法确定则为 null。"
        f"\n用户需求：{query}"
    )
    raw = llm([{"role": "user", "content": prompt}], one_line=False, json_mode=True)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("DeepSeek did not return a JSON object")

    preferences = data.get("preferences") or []
    if not isinstance(preferences, list):
        preferences = []
    data["preferences"] = [item for item in preferences if item in PREFERENCE_OPTIONS]
    return ExtractedFields.model_validate(data)


def _image_item(raw: dict[str, Any]) -> dict[str, Any] | None:
    url = raw.get("hoverUrl") or raw.get("objURL") or raw.get("thumbnailUrl")
    if not url:
        return None
    return {
        "title": raw.get("oriTitle") or raw.get("title"),
        "url": url,
        "thumbnail_url": raw.get("thumbnailUrl") or url,
        "width": raw.get("width"),
        "height": raw.get("height"),
    }


def search_images(keyword: str, page: int = 1, limit: int = 6) -> list[dict[str, Any]]:
    params = {"msg": keyword, "page": max(page, 1)}
    with httpx.Client(timeout=8, follow_redirects=True) as client:
        response = client.get(IMAGE_SEARCH_URL, params=params)
        response.raise_for_status()
        payload = _loads_mixed_json(response.text)

    if isinstance(payload, dict):
        source = payload.get("data") or payload.get("result") or payload.get("list")
    elif isinstance(payload, list):
        source = payload
    else:
        source = []
    if source is None:
        source = []

    images = []
    for item in source:
        if not isinstance(item, dict):
            continue
        normalized = _image_item(item)
        if normalized is not None:
            images.append(normalized)
        if len(images) >= limit:
            break
    return images
