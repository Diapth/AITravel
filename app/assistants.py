from __future__ import annotations

import json
import copy
import re
from typing import Any

import httpx

from app.schemas import ExtractedFields
from chinatravel.agent.load_model import init_llm


IMAGE_SEARCH_URL = "https://zj.v.api.aa1.cn/api/so-baidu-img/"
PREFERENCE_OPTIONS = ["自然风光", "休闲度假", "美食体验", "文化体验", "户外活动", "拍照打卡", "亲子家庭", "当地生活"]


KNOWN_TRAVEL_CITY_NAMES = (
    "北京",
    "上海",
    "天津",
    "重庆",
    "南京",
    "苏州",
    "杭州",
    "武汉",
    "广州",
    "深圳",
    "成都",
    "西安",
    "厦门",
    "桂林",
    "阳朔",
    "大理",
    "丽江",
    "青岛",
    "长沙",
    "洛阳",
    "开封",
    "哈尔滨",
    "三亚",
)


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


def _json_object_from_llm(raw: str) -> dict[str, Any]:
    payload = _loads_mixed_json(raw)
    if not isinstance(payload, dict):
        raise ValueError("LLM did not return a JSON object")
    return payload


def _normalize_positive_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def heuristic_trip_intent_readiness(
    messages: list[dict[str, Any]],
    latest_message: str,
    current_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fields = dict(current_fields or {})
    text_parts = [
        str(message.get("content") or "")
        for message in messages
        if str(message.get("role") or "") in {"user", "assistant"}
    ]
    text = f"{' '.join(text_parts)} {latest_message}".strip()

    days_match = re.search(r"(\d+)\s*(天|日|晚)", text)
    people_match = re.search(r"(\d+)\s*(个人|人|位|大人)", text)
    budget_match = re.search(r"(?:预算|人均|总预算|控制在|不超过|以内)[^\d]*(\d{3,7})|(\d{3,7})\s*(元|块|预算)", text)
    matched_cities = [city for city in KNOWN_TRAVEL_CITY_NAMES if city in text]

    if matched_cities and not _clean_text(fields.get("target_city")):
        fields["target_cities"] = matched_cities
        fields["target_city"] = "、".join(matched_cities[:3])
    if days_match and not _normalize_positive_int(fields.get("days")):
        fields["days"] = int(days_match.group(1))
    if people_match and not _normalize_positive_int(fields.get("people_number")):
        fields["people_number"] = int(people_match.group(1))
    if budget_match and not _normalize_positive_int(fields.get("budget")):
        fields["budget"] = int(budget_match.group(1) or budget_match.group(2))

    target_city = _clean_text(fields.get("target_city"))
    target_cities = fields.get("target_cities") if isinstance(fields.get("target_cities"), list) else []
    days = _normalize_positive_int(fields.get("days"))
    people = _normalize_positive_int(fields.get("people_number"))
    budget = _normalize_positive_int(fields.get("budget"))
    wants_generate = bool(re.search(r"(生成|做一版|出一版|安排|规划一下|定下来|开始做|给我一份|确认生成|生成攻略|生成行程)", latest_message))

    missing_questions: list[str] = []
    if not (target_city or target_cities):
        missing_questions.append("想去哪个具体城市或区域？")
    if not days:
        missing_questions.append("大概玩几天？")
    if not (people or budget):
        missing_questions.append("同行人数或预算大概是多少？")

    precise_enough = bool(target_city or target_cities) and bool(days) and bool(people or budget)
    should_show = precise_enough or (wants_generate and bool(target_city or target_cities) and bool(days))
    return {
        "should_show_checklist": should_show,
        "reason": "目的地、天数和人数/预算已基本明确。" if should_show else "信息还不足，继续自然澄清。",
        "confidence": 0.72 if should_show else 0.52,
        "missing_questions": [] if should_show else missing_questions[:3],
        "fields": {key: value for key, value in fields.items() if value not in (None, "", [])},
    }


def assess_trip_intent_readiness(
    messages: list[dict[str, Any]],
    latest_message: str,
    current_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    heuristic = heuristic_trip_intent_readiness(messages, latest_message, current_fields)
    prompt = (
        "你是旅行需求就绪度判断器。请只返回 JSON，不要解释。\n"
        "目标：判断是否应该在聊天里弹出“规划清单确认表单”。\n"
        "只有当用户提供的信息足够多，且目的地足够精准后才 should_show_checklist=true。\n"
        "判断标准：至少有明确目的地；最好有天数；并且有人数或预算之一。用户只是问问题、闲聊、表达模糊偏好时必须为 false。\n"
        "JSON 字段：should_show_checklist(boolean), reason(string), confidence(0-1), missing_questions(string[]), fields(object)。\n"
        "fields 可包含 query,start_city,target_city,target_cities,days,people_number,budget。\n\n"
        f"近期对话：{json.dumps(messages[-10:], ensure_ascii=False, default=str)}\n"
        f"用户最新消息：{latest_message}\n"
        f"已知字段：{json.dumps(current_fields or {}, ensure_ascii=False, default=str)}\n"
        f"启发式参考：{json.dumps(heuristic, ensure_ascii=False, default=str)}"
    )
    try:
        llm = init_llm("deepseek", max_model_len=2048)
        data = _json_object_from_llm(llm([{"role": "user", "content": prompt}], one_line=False, json_mode=True))
    except Exception:
        return heuristic

    result = {
        "should_show_checklist": bool(data.get("should_show_checklist")),
        "reason": str(data.get("reason") or heuristic["reason"])[:200],
        "confidence": data.get("confidence") if isinstance(data.get("confidence"), (int, float)) else heuristic["confidence"],
        "missing_questions": data.get("missing_questions") if isinstance(data.get("missing_questions"), list) else heuristic["missing_questions"],
        "fields": data.get("fields") if isinstance(data.get("fields"), dict) else {},
    }
    merged_fields = {**heuristic.get("fields", {}), **result["fields"]}
    result["fields"] = {key: value for key, value in merged_fields.items() if value not in (None, "", [])}
    if result["should_show_checklist"] and not (
        _clean_text(result["fields"].get("target_city")) or result["fields"].get("target_cities")
    ):
        result["should_show_checklist"] = False
        result["reason"] = "目的地仍不够明确，继续澄清。"
    return result


def _activity_label(activity: dict[str, Any]) -> str:
    return str(activity.get("title") or activity.get("position") or activity.get("description") or "活动")


def _renumber_itinerary(plan: dict[str, Any]) -> dict[str, Any]:
    itinerary = plan.get("itinerary")
    if not isinstance(itinerary, list):
        return plan
    for day_index, day in enumerate(itinerary, start=1):
        if not isinstance(day, dict):
            continue
        day["day"] = _normalize_positive_int(day.get("day")) or day_index
        activities = day.get("activities")
        if isinstance(activities, list):
            for activity in activities:
                if isinstance(activity, dict):
                    activity["day"] = day["day"]
    plan["days"] = _normalize_positive_int(plan.get("days")) or len(itinerary)
    return plan


def heuristic_edit_plan(current_plan: dict[str, Any], instruction: str) -> dict[str, Any]:
    plan = copy.deepcopy(current_plan)
    note = f"AI 已根据修改要求更新：{instruction}"
    summary = str(plan.get("llm_summary") or "")
    plan["llm_summary"] = f"{summary}\n{note}".strip() if summary else note
    plan.setdefault("ai_edit_notes", []).append(instruction)

    budget_match = re.search(r"(?:预算|总预算|控制在|不超过|以内)[^\d]*(\d{3,7})", instruction)
    if budget_match:
        plan["budget"] = int(budget_match.group(1))
    people_match = re.search(r"(\d+)\s*(个人|人|位)", instruction)
    if people_match:
        plan["people_number"] = int(people_match.group(1))

    day_match = re.search(r"(?:加|增加|改成|调整为|变成)\s*(\d+)\s*(天|日)", instruction)
    itinerary = plan.get("itinerary")
    if day_match and isinstance(itinerary, list):
        desired_days = int(day_match.group(1))
        grouped_days = [item for item in itinerary if isinstance(item, dict) and isinstance(item.get("activities"), list)]
        if grouped_days and desired_days > len(grouped_days):
            destination = plan.get("target_city") or "目的地"
            for day in range(len(grouped_days) + 1, desired_days + 1):
                grouped_days.append(
                    {
                        "day": day,
                        "title": f"第 {day} 天 · {destination} 自由调整",
                        "summary": f"根据“{instruction}”新增的可编辑日程。",
                        "activities": [
                            {
                                "day": day,
                                "type": "activity",
                                "title": "自由活动与备选体验",
                                "position": destination,
                                "start_time": "10:00",
                                "end_time": "16:00",
                                "description": instruction,
                                "cost": 0,
                            }
                        ],
                    }
                )
            plan["itinerary"] = grouped_days
        plan["days"] = desired_days

    if re.search(r"轻松|少走路|慢一点|宽松", instruction):
        for day in plan.get("itinerary") or []:
            if not isinstance(day, dict):
                continue
            day["summary"] = f"{day.get('summary') or ''} 已调整为更轻松、少折返的节奏。".strip()
            for activity in day.get("activities") or []:
                if isinstance(activity, dict) and activity.get("type") == "attraction":
                    activity["description"] = f"{activity.get('description') or _activity_label(activity)}；建议压缩排队点，保留充足休息。"
    return _renumber_itinerary(plan)


def edit_plan_with_instruction(current_plan: dict[str, Any], instruction: str, messages: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    compact_plan = json.dumps(current_plan, ensure_ascii=False, default=str)
    if len(compact_plan) > 16000:
        compact_plan = compact_plan[:16000]
    prompt = (
        "你是 ChinaTravel Planner 的行程 JSON 编辑器。请只返回完整 JSON 对象，不要解释。\n"
        "必须基于 current_plan 生成新版本，保留未被用户要求修改的字段和活动；不要删除 itinerary。\n"
        "如果用户说加一天、换酒店、压缩预算、少走路、调整餐饮或交通，请直接修改对应字段和说明。\n"
        "返回字段应仍包含 target_city/days/people_number/budget/total_cost/itinerary/llm_summary 等现有结构。\n\n"
        f"近期对话：{json.dumps((messages or [])[-8:], ensure_ascii=False, default=str)}\n"
        f"用户修改要求：{instruction}\n"
        f"current_plan：{compact_plan}"
    )
    try:
        llm = init_llm("deepseek", max_model_len=4096)
        edited = _json_object_from_llm(llm([{"role": "user", "content": prompt}], one_line=False, json_mode=True))
        if not isinstance(edited.get("itinerary"), list) or not edited["itinerary"]:
            raise ValueError("Edited plan omitted itinerary")
        return _renumber_itinerary(edited)
    except Exception:
        return heuristic_edit_plan(current_plan, instruction)


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
