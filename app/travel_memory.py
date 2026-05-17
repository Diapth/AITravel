from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas import PlanRequest
from chinatravel.config import get_env_value, get_int_env


DEFAULT_MEMORY_DB = "travel_memory.sqlite"
BUDGET_BUCKETS = (500, 1000, 1500, 3000)
STATIC_RECOMMENDED_PLANS: tuple[dict[str, Any], ...] = (
    {
        "id": "sample-guilin-yangshuo",
        "title": "桂林阳朔 4 天 3 晚",
        "summary": "漓江竹筏、遇龙河骑行和当地美食，适合轻松自然风光游。",
        "source": "sample",
        "plan": {
            "start_city": "上海",
            "target_city": "桂林、阳朔",
            "target_cities": ["桂林", "阳朔"],
            "days": 4,
            "people_number": 2,
            "budget": 3400,
            "total_cost": 3200,
            "llm_summary": "桂林阳朔四天三晚，兼顾山水、骑行和美食。",
            "itinerary": [
                {
                    "day": 1,
                    "title": "抵达桂林与两江四湖",
                    "summary": "轻松抵达后入住市区，傍晚散步到两江四湖。",
                    "location": "桂林",
                    "accommodation": "桂林中心广场附近",
                    "activities": [
                        {"day": 1, "type": "train", "title": "抵达桂林", "start": "上海", "end": "桂林", "start_time": "08:30", "end_time": "15:30", "transportation": "高铁参考", "cost": 620},
                        {"day": 1, "type": "accommodation", "title": "桂林中心酒店", "position": "中心广场商圈", "start_time": "16:00", "end_time": "17:00", "rooms": 1, "cost": 360},
                        {"day": 1, "type": "attraction", "title": "两江四湖", "position": "两江四湖景区", "start_time": "19:00", "end_time": "21:00", "description": "夜景散步或游船，节奏轻松。", "cost": 180},
                    ],
                },
                {
                    "day": 2,
                    "title": "漓江精华与阳朔西街",
                    "summary": "上午看漓江山水，下午转到阳朔，晚间逛西街。",
                    "location": "阳朔",
                    "accommodation": "阳朔西街附近",
                    "activities": [
                        {"day": 2, "type": "attraction", "title": "漓江竹筏", "position": "杨堤-兴坪段", "start_time": "09:00", "end_time": "12:00", "description": "选择精华段，减少车程折返。", "cost": 320},
                        {"day": 2, "type": "restaurant", "title": "阳朔啤酒鱼", "position": "西街附近餐厅", "start_time": "12:30", "end_time": "13:30", "recommended_food": "啤酒鱼、田螺酿", "cost": 180},
                        {"day": 2, "type": "activity", "title": "阳朔西街", "position": "阳朔西街", "start_time": "19:00", "end_time": "21:00", "description": "夜间散步和小吃。", "cost": 80},
                    ],
                },
                {
                    "day": 3,
                    "title": "遇龙河与十里画廊",
                    "summary": "上午竹筏，下午骑行十里画廊，保留午休。",
                    "location": "阳朔",
                    "accommodation": "阳朔西街附近",
                    "activities": [
                        {"day": 3, "type": "attraction", "title": "遇龙河竹筏", "position": "遇龙河景区", "start_time": "09:30", "end_time": "11:30", "description": "建议提前预约热门码头。", "cost": 260},
                        {"day": 3, "type": "restaurant", "title": "桂林米粉", "position": "阳朔县城", "start_time": "12:00", "end_time": "13:00", "recommended_food": "卤菜粉、油茶", "cost": 60},
                        {"day": 3, "type": "attraction", "title": "十里画廊骑行", "position": "十里画廊", "start_time": "15:00", "end_time": "17:30", "description": "按体力选择电动车或轻骑行。", "cost": 120},
                    ],
                },
                {
                    "day": 4,
                    "title": "返程前慢逛",
                    "summary": "上午补一个轻量景点或咖啡店，下午返程。",
                    "location": "桂林",
                    "activities": [
                        {"day": 4, "type": "attraction", "title": "象鼻山", "position": "象鼻山景区", "start_time": "09:30", "end_time": "11:00", "description": "经典地标，适合返程前短停留。", "cost": 110},
                        {"day": 4, "type": "restaurant", "title": "本地简餐", "position": "桂林站附近", "start_time": "11:30", "end_time": "12:30", "recommended_food": "桂林米粉", "cost": 70},
                        {"day": 4, "type": "train", "title": "桂林返程", "start": "桂林", "end": "上海", "start_time": "14:00", "end_time": "21:00", "transportation": "高铁参考", "cost": 620},
                    ],
                },
            ],
        },
    },
    {
        "id": "sample-chengdu-food",
        "title": "成都美食 3 天 2 晚",
        "summary": "茶馆、川菜、街区漫游和宽松节奏，适合中等预算。",
        "source": "sample",
        "plan": {
            "start_city": "上海",
            "target_city": "成都",
            "target_cities": ["成都"],
            "days": 3,
            "people_number": 2,
            "budget": 2800,
            "total_cost": 2500,
            "llm_summary": "成都三天两晚美食体验路线。",
            "itinerary": [
                {
                    "day": 1,
                    "title": "抵达成都与宽窄巷子",
                    "summary": "入住市中心，晚间轻松吃川菜。",
                    "location": "成都",
                    "accommodation": "春熙路附近",
                    "activities": [
                        {"day": 1, "type": "train", "title": "抵达成都", "start": "上海", "end": "成都", "start_time": "09:00", "end_time": "16:30", "transportation": "高铁/航班参考", "cost": 760},
                        {"day": 1, "type": "accommodation", "title": "春熙路酒店", "position": "春熙路商圈", "start_time": "17:00", "end_time": "18:00", "rooms": 1, "cost": 420},
                        {"day": 1, "type": "restaurant", "title": "宽窄巷子川菜", "position": "宽窄巷子", "start_time": "19:00", "end_time": "20:30", "recommended_food": "钵钵鸡、担担面", "cost": 180},
                    ],
                },
                {
                    "day": 2,
                    "title": "茶馆与街区漫游",
                    "summary": "上午人民公园，下午太古里和玉林路。",
                    "location": "成都",
                    "accommodation": "春熙路附近",
                    "activities": [
                        {"day": 2, "type": "attraction", "title": "人民公园茶馆", "position": "人民公园", "start_time": "10:00", "end_time": "12:00", "description": "喝盖碗茶，体验本地生活。", "cost": 80},
                        {"day": 2, "type": "restaurant", "title": "火锅晚餐", "position": "玉林路", "start_time": "18:00", "end_time": "20:00", "recommended_food": "鸳鸯锅、酥肉", "cost": 260},
                        {"day": 2, "type": "activity", "title": "玉林路散步", "position": "玉林路", "start_time": "20:00", "end_time": "21:30", "description": "饭后慢走，备选小酒馆。", "cost": 80},
                    ],
                },
                {
                    "day": 3,
                    "title": "文殊院与返程",
                    "summary": "上午文殊院周边小吃，下午返程。",
                    "location": "成都",
                    "activities": [
                        {"day": 3, "type": "attraction", "title": "文殊院", "position": "文殊院", "start_time": "09:30", "end_time": "11:00", "description": "安静街区，适合慢逛。", "cost": 0},
                        {"day": 3, "type": "restaurant", "title": "文殊院小吃", "position": "文殊院周边", "start_time": "11:30", "end_time": "12:30", "recommended_food": "甜水面、钟水饺", "cost": 90},
                        {"day": 3, "type": "train", "title": "成都返程", "start": "成都", "end": "上海", "start_time": "14:30", "end_time": "22:00", "transportation": "高铁/航班参考", "cost": 760},
                    ],
                },
            ],
        },
    },
    {
        "id": "sample-suzhou-weekend",
        "title": "苏州周末 2 天 1 晚",
        "summary": "园林、评弹、平江路和轻量交通，适合周末短途。",
        "source": "sample",
        "plan": {
            "start_city": "上海",
            "target_city": "苏州",
            "target_cities": ["苏州"],
            "days": 2,
            "people_number": 2,
            "budget": 1300,
            "total_cost": 1100,
            "llm_summary": "苏州周末两天一晚轻松路线。",
            "itinerary": [
                {
                    "day": 1,
                    "title": "园林与平江路",
                    "summary": "上午从上海出发，白天园林，夜晚平江路。",
                    "location": "苏州",
                    "accommodation": "观前街附近",
                    "activities": [
                        {"day": 1, "type": "train", "title": "上海到苏州", "start": "上海", "end": "苏州", "start_time": "08:30", "end_time": "09:10", "transportation": "高铁参考", "cost": 80},
                        {"day": 1, "type": "attraction", "title": "拙政园", "position": "拙政园", "start_time": "10:00", "end_time": "12:00", "description": "提前预约，避开正午高峰。", "cost": 160},
                        {"day": 1, "type": "restaurant", "title": "苏帮菜午餐", "position": "观前街", "start_time": "12:30", "end_time": "13:30", "recommended_food": "松鼠桂鱼、响油鳝糊", "cost": 180},
                        {"day": 1, "type": "activity", "title": "平江路夜游", "position": "平江路", "start_time": "19:00", "end_time": "21:00", "description": "评弹、茶馆和夜景。", "cost": 100},
                    ],
                },
                {
                    "day": 2,
                    "title": "博物馆与返程",
                    "summary": "上午苏博或留园，下午返沪。",
                    "location": "苏州",
                    "activities": [
                        {"day": 2, "type": "attraction", "title": "苏州博物馆", "position": "苏州博物馆", "start_time": "09:30", "end_time": "11:30", "description": "需提前预约，和拙政园距离近。", "cost": 0},
                        {"day": 2, "type": "restaurant", "title": "面馆午餐", "position": "十全街", "start_time": "12:00", "end_time": "13:00", "recommended_food": "焖肉面、三虾面", "cost": 80},
                        {"day": 2, "type": "train", "title": "苏州到上海", "start": "苏州", "end": "上海", "start_time": "16:00", "end_time": "16:40", "transportation": "高铁参考", "cost": 80},
                    ],
                },
            ],
        },
    },
)
PII_PATTERNS = (
    re.compile(r"1[3-9]\d{9}"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"\d{17}[\dXx]"),
)


def get_memory_db_path() -> Path:
    value = (
        get_env_value("CHINATRAVEL_MEMORY_DB_PATH")
        or get_env_value("CHINATRAVEL_TRIP_MEMORY_DB")
        or DEFAULT_MEMORY_DB
    )
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return (Path(__file__).resolve().parent.parent / path).resolve()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_query(query: str) -> str:
    redacted = query
    for pattern in PII_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _plan_card_title(plan: dict[str, Any]) -> str:
    target = plan.get("target_city") or "推荐行程"
    days = plan.get("days")
    if days:
        return f"{target} {days} 天"
    return str(target)


def _plan_card_summary(plan: dict[str, Any]) -> str:
    summary = plan.get("llm_summary") or plan.get("summary")
    if summary:
        return str(summary)[:160]
    target = plan.get("target_city") or "目的地"
    days = plan.get("days") or "多"
    return f"{target}{days}天行程，可继续聊天修改。"


def _plan_has_visible_itinerary(plan: dict[str, Any]) -> bool:
    itinerary = plan.get("itinerary")
    if not isinstance(itinerary, list) or not itinerary:
        return False
    for item in itinerary:
        if not isinstance(item, dict):
            continue
        activities = item.get("activities")
        if isinstance(activities, list) and activities:
            return True
        if item.get("title") or item.get("position") or item.get("description"):
            return True
    return False


def _bucket_budget(value: int | None) -> str:
    if value is None:
        return "unknown"
    previous = 0
    for upper in BUDGET_BUCKETS:
        if value <= upper:
            return f"{previous}-{upper}"
        previous = upper
    return "3000+"


def _bucket_people(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value <= 2:
        return "1-2p"
    if value <= 5:
        return "3-5p"
    return "6p+"


def _target_cities(request: PlanRequest) -> list[str]:
    if request.target_cities:
        return request.target_cities
    if request.target_city:
        return [request.target_city]
    return []


def request_fingerprint(request: PlanRequest) -> str:
    parts = [
        request.start_city or "",
        "|".join(sorted(_target_cities(request))),
        f"{request.days or 'unknown'}d",
        _bucket_people(request.people_number),
        _bucket_budget(request.budget),
    ]
    return sha256_text("|".join(parts))


def route_key_for_request(request: PlanRequest) -> str:
    parts = [request.start_city or "", *sorted(_target_cities(request)), f"{request.days or 'unknown'}d"]
    return sha256_text("|".join(parts))


class TravelMemoryStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else get_memory_db_path()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trip_requests (
                  id TEXT PRIMARY KEY,
                  user_id_hash TEXT,
                  query_hash TEXT NOT NULL,
                  query_text_redacted TEXT,
                  start_city TEXT,
                  target_cities_json TEXT NOT NULL,
                  departure_date TEXT,
                  return_date TEXT,
                  days INTEGER,
                  people_number INTEGER,
                  budget INTEGER,
                  preferences_json TEXT NOT NULL,
                  request_fingerprint TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trip_plans (
                  id TEXT PRIMARY KEY,
                  request_id TEXT NOT NULL,
                  plan_json TEXT NOT NULL,
                  plan_summary TEXT,
                  total_cost REAL,
                  route_key TEXT NOT NULL,
                  quality_score REAL,
                  source_agent TEXT,
                  used_realtime INTEGER NOT NULL DEFAULT 0,
                  used_history INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(request_id) REFERENCES trip_requests(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS trip_feedback (
                  id TEXT PRIMARY KEY,
                  plan_id TEXT NOT NULL,
                  user_id_hash TEXT,
                  rating INTEGER,
                  action TEXT,
                  feedback_text_redacted TEXT,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(plan_id) REFERENCES trip_plans(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS route_stats (
                  route_key TEXT PRIMARY KEY,
                  request_count INTEGER NOT NULL DEFAULT 0,
                  avg_budget REAL,
                  avg_total_cost REAL,
                  avg_rating REAL,
                  top_preferences_json TEXT NOT NULL,
                  top_pois_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_requests_fingerprint ON trip_requests(request_fingerprint)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_requests_route ON trip_requests(start_city, days, budget)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_plans_route_key ON trip_plans(route_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_trip_plans_quality ON trip_plans(quality_score)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                  id TEXT PRIMARY KEY,
                  title TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'active',
                  current_version_id TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                  id TEXT PRIMARY KEY,
                  conversation_id TEXT NOT NULL,
                  sequence INTEGER NOT NULL,
                  role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                  content TEXT NOT NULL,
                  plan_version_id TEXT,
                  request_id TEXT,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(conversation_id) REFERENCES conversations(id),
                  FOREIGN KEY(plan_version_id) REFERENCES plan_versions(id),
                  UNIQUE(conversation_id, sequence)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plan_versions (
                  id TEXT PRIMARY KEY,
                  conversation_id TEXT NOT NULL,
                  version_number INTEGER NOT NULL,
                  parent_version_id TEXT,
                  source TEXT NOT NULL CHECK(source IN ('ai_generated', 'ai_edit', 'manual_edit', 'rollback', 'recommended')),
                  plan_json TEXT NOT NULL,
                  summary TEXT,
                  total_cost REAL,
                  request_id TEXT,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(conversation_id) REFERENCES conversations(id),
                  FOREIGN KEY(parent_version_id) REFERENCES plan_versions(id),
                  UNIQUE(conversation_id, version_number)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_messages_thread ON conversation_messages(conversation_id, sequence)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_plan_versions_thread ON plan_versions(conversation_id, version_number DESC)"
            )
            try:
                conn.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS conversation_messages_fts
                    USING fts5(content, conversation_id UNINDEXED, message_id UNINDEXED)
                    """
                )
            except sqlite3.OperationalError:
                pass

    @staticmethod
    def _row_to_dict(cursor: sqlite3.Cursor, row: sqlite3.Row | tuple[Any, ...]) -> dict[str, Any]:
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row))

    def create_conversation(self, title: str | None = None) -> dict[str, Any]:
        self.initialize()
        now = utc_now_iso()
        conversation_id = f"conv_{uuid4().hex}"
        conversation_title = (title or "未命名行程").strip() or "未命名行程"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, title, status, current_version_id, created_at, updated_at)
                VALUES (?, ?, 'active', NULL, ?, ?)
                """,
                (conversation_id, conversation_title, now, now),
            )
        return {
            "id": conversation_id,
            "title": conversation_title,
            "status": "active",
            "current_version_id": None,
            "created_at": now,
            "updated_at": now,
        }

    def list_conversations(self, limit: int = 30, include_archived: bool = False) -> list[dict[str, Any]]:
        self.initialize()
        where = "" if include_archived else "WHERE status = 'active'"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"""
                SELECT id, title, status, current_version_id, created_at, updated_at
                FROM conversations
                {where}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [self._row_to_dict(cursor, row) for row in cursor.fetchall()]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conversation_cursor = conn.execute(
                """
                SELECT id, title, status, current_version_id, created_at, updated_at
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,),
            )
            conversation_row = conversation_cursor.fetchone()
            if conversation_row is None:
                return None
            conversation = self._row_to_dict(conversation_cursor, conversation_row)

            messages_cursor = conn.execute(
                """
                SELECT id, conversation_id, sequence, role, content, plan_version_id, request_id, created_at
                FROM conversation_messages
                WHERE conversation_id = ?
                ORDER BY sequence ASC
                """,
                (conversation_id,),
            )
            messages = [self._row_to_dict(messages_cursor, row) for row in messages_cursor.fetchall()]

            versions_cursor = conn.execute(
                """
                SELECT id, conversation_id, version_number, parent_version_id, source, summary, total_cost, request_id, created_at, plan_json
                FROM plan_versions
                WHERE conversation_id = ?
                ORDER BY version_number DESC
                """,
                (conversation_id,),
            )
            versions = []
            for row in versions_cursor.fetchall():
                version = self._row_to_dict(versions_cursor, row)
                plan_json = version.pop("plan_json", "{}")
                try:
                    plan = json.loads(plan_json)
                except json.JSONDecodeError:
                    plan = {}
                warnings = plan.get("validation_warnings") if isinstance(plan, dict) else []
                version["validation_warnings"] = warnings if isinstance(warnings, list) else []
                versions.append(version)

            current_plan = None
            if conversation["current_version_id"]:
                plan_row = conn.execute(
                    "SELECT plan_json FROM plan_versions WHERE id = ?",
                    (conversation["current_version_id"],),
                ).fetchone()
                if plan_row:
                    current_plan = json.loads(plan_row[0])

        return {
            "conversation": conversation,
            "messages": messages,
            "versions": versions,
            "current_plan": current_plan,
        }

    def append_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        plan_version_id: str | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        self.initialize()
        now = utc_now_iso()
        message_id = f"msg_{uuid4().hex}"
        with sqlite3.connect(self.db_path) as conn:
            sequence = (
                conn.execute(
                    "SELECT COALESCE(MAX(sequence), 0) + 1 FROM conversation_messages WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()[0]
            )
            conn.execute(
                """
                INSERT INTO conversation_messages (
                  id, conversation_id, sequence, role, content, plan_version_id, request_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, conversation_id, sequence, role, content, plan_version_id, request_id, now),
            )
            conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
            try:
                conn.execute(
                    """
                    INSERT INTO conversation_messages_fts (content, conversation_id, message_id)
                    VALUES (?, ?, ?)
                    """,
                    (content, conversation_id, message_id),
                )
            except sqlite3.OperationalError:
                pass
        return {
            "id": message_id,
            "conversation_id": conversation_id,
            "sequence": sequence,
            "role": role,
            "content": content,
            "plan_version_id": plan_version_id,
            "request_id": request_id,
            "created_at": now,
        }

    def create_plan_version(
        self,
        conversation_id: str,
        plan: dict[str, Any],
        source: str,
        parent_version_id: str | None = None,
        request_id: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        self.initialize()
        now = utc_now_iso()
        version_id = f"ver_{uuid4().hex}"
        total_cost = None
        if plan.get("total_cost") is not None:
            try:
                total_cost = float(plan["total_cost"])
            except (TypeError, ValueError):
                total_cost = None
        with sqlite3.connect(self.db_path) as conn:
            version_number = (
                conn.execute(
                    "SELECT COALESCE(MAX(version_number), 0) + 1 FROM plan_versions WHERE conversation_id = ?",
                    (conversation_id,),
                ).fetchone()[0]
            )
            conn.execute(
                """
                INSERT INTO plan_versions (
                  id, conversation_id, version_number, parent_version_id, source,
                  plan_json, summary, total_cost, request_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    conversation_id,
                    version_number,
                    parent_version_id,
                    source,
                    json.dumps(plan, ensure_ascii=False, sort_keys=True, default=str),
                    summary,
                    total_cost,
                    request_id,
                    now,
                ),
            )
            conn.execute(
                "UPDATE conversations SET current_version_id = ?, updated_at = ? WHERE id = ?",
                (version_id, now, conversation_id),
            )
        return {
            "id": version_id,
            "conversation_id": conversation_id,
            "version_number": version_number,
            "parent_version_id": parent_version_id,
            "source": source,
            "summary": summary,
            "total_cost": total_cost,
            "validation_warnings": plan.get("validation_warnings") if isinstance(plan, dict) and isinstance(plan.get("validation_warnings"), list) else [],
            "request_id": request_id,
            "created_at": now,
        }

    def archive_conversation(self, conversation_id: str) -> dict[str, Any]:
        return self._set_conversation_status(conversation_id, "archived")

    def restore_conversation(self, conversation_id: str) -> dict[str, Any]:
        return self._set_conversation_status(conversation_id, "active")

    def _set_conversation_status(self, conversation_id: str, status: str) -> dict[str, Any]:
        self.initialize()
        now = utc_now_iso()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE conversations SET status = ?, updated_at = ? WHERE id = ?",
                (status, now, conversation_id),
            )
            cursor = conn.execute(
                """
                SELECT id, title, status, current_version_id, created_at, updated_at
                FROM conversations
                WHERE id = ?
                """,
                (conversation_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Conversation not found")
            return self._row_to_dict(cursor, row)

    def restore_version(self, conversation_id: str, version_id: str) -> dict[str, Any]:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            current_row = conn.execute(
                "SELECT current_version_id FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            if current_row is None:
                raise ValueError("Conversation not found")
            source_row = conn.execute(
                """
                SELECT plan_json, summary
                FROM plan_versions
                WHERE id = ? AND conversation_id = ?
                """,
                (version_id, conversation_id),
            ).fetchone()
            if source_row is None:
                raise ValueError("Plan version not found")
            plan = json.loads(source_row[0])
            restored_summary = f"回退到：{source_row[1]}" if source_row[1] else "回退版本"
        return self.create_plan_version(
            conversation_id,
            plan,
            source="rollback",
            parent_version_id=current_row[0],
            summary=restored_summary,
        )

    def recommended_plans(self, limit: int = 6) -> list[dict[str, Any]]:
        self.initialize()
        recommendations: list[dict[str, Any]] = []
        with sqlite3.connect(self.db_path) as conn:
            version_rows = conn.execute(
                """
                SELECT pv.id, pv.conversation_id, pv.summary, pv.plan_json, pv.source, pv.created_at, c.title
                FROM plan_versions pv
                JOIN conversations c ON c.id = pv.conversation_id
                WHERE c.status = 'active'
                ORDER BY pv.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            for version_id, conversation_id, summary, plan_json, source, _created_at, title in version_rows:
                plan = json.loads(plan_json)
                if not _plan_has_visible_itinerary(plan):
                    continue
                recommendations.append(
                    {
                        "id": f"version-{version_id}",
                        "title": title,
                        "summary": summary or _plan_card_summary(plan),
                        "source": source,
                        "plan": plan,
                        "conversation_id": conversation_id,
                        "version_id": version_id,
                    }
                )
            if len(recommendations) < limit:
                trip_rows = conn.execute(
                    """
                    SELECT id, plan_summary, plan_json, source_agent
                    FROM trip_plans
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit - len(recommendations),),
                ).fetchall()
                for plan_id, summary, plan_json, source_agent in trip_rows:
                    plan = json.loads(plan_json)
                    if not _plan_has_visible_itinerary(plan):
                        continue
                    recommendations.append(
                        {
                            "id": f"trip-{plan_id}",
                            "title": _plan_card_title(plan),
                            "summary": summary or _plan_card_summary(plan),
                            "source": source_agent or "trip_memory",
                            "plan": plan,
                        }
                    )
        if len(recommendations) < limit:
            for item in STATIC_RECOMMENDED_PLANS:
                if len(recommendations) >= limit:
                    break
                recommendations.append(dict(item))
        return recommendations

    def open_recommended_plan(self, recommendation_id: str) -> dict[str, Any]:
        recommendation = next(
            (item for item in self.recommended_plans(limit=30) if item["id"] == recommendation_id),
            None,
        )
        if recommendation is None:
            raise ValueError("Recommendation not found")
        conversation = self.create_conversation(title=recommendation["title"])
        version = self.create_plan_version(
            conversation["id"],
            recommendation["plan"],
            source="recommended",
            summary=recommendation["summary"],
        )
        self.append_message(
            conversation["id"],
            "assistant",
            "已打开推荐行程，可继续告诉我你想怎么调整。",
            plan_version_id=version["id"],
        )
        detail = self.get_conversation(conversation["id"])
        if detail is None:
            raise ValueError("Conversation not found after opening recommendation")
        return detail

    def write_trip(
        self,
        request: PlanRequest,
        plan: dict[str, Any] | None,
        *,
        meta: dict[str, Any] | None = None,
        used_realtime: bool = False,
        used_history: bool = False,
    ) -> dict[str, Any]:
        self.initialize()
        now = utc_now_iso()
        request_id = f"req_{uuid4().hex}"
        plan_id = f"plan_{uuid4().hex}"
        fingerprint = request_fingerprint(request)
        route_key = route_key_for_request(request)
        redacted_query = redact_query(request.query)
        target_cities = _target_cities(request)
        source_agent = str((meta or {}).get("agent") or "")
        total_cost = None
        if isinstance(plan, dict) and plan.get("total_cost") is not None:
            try:
                total_cost = float(plan["total_cost"])
            except (TypeError, ValueError):
                total_cost = None

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO trip_requests (
                  id, user_id_hash, query_hash, query_text_redacted, start_city,
                  target_cities_json, departure_date, return_date, days, people_number,
                  budget, preferences_json, request_fingerprint, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    None,
                    sha256_text(request.query),
                    redacted_query,
                    request.start_city,
                    json.dumps(target_cities, ensure_ascii=False),
                    request.departure_date.isoformat() if request.departure_date else None,
                    request.return_date.isoformat() if request.return_date else None,
                    request.days,
                    request.people_number,
                    request.budget,
                    "[]",
                    fingerprint,
                    now,
                ),
            )
            if plan is not None:
                conn.execute(
                    """
                    INSERT INTO trip_plans (
                      id, request_id, plan_json, plan_summary, total_cost, route_key,
                      quality_score, source_agent, used_realtime, used_history, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        plan_id,
                        request_id,
                        json.dumps(plan, ensure_ascii=False, sort_keys=True, default=str),
                        str(plan.get("llm_summary") or "")[:500] if isinstance(plan, dict) else None,
                        total_cost,
                        route_key,
                        1.0 if plan else None,
                        source_agent,
                        int(used_realtime),
                        int(used_history),
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO route_stats (
                      route_key, request_count, avg_budget, avg_total_cost, avg_rating,
                      top_preferences_json, top_pois_json, updated_at
                    ) VALUES (?, 1, ?, ?, NULL, '[]', '[]', ?)
                    ON CONFLICT(route_key) DO UPDATE SET
                      request_count = request_count + 1,
                      avg_budget = COALESCE((avg_budget * request_count + excluded.avg_budget) / (request_count + 1), avg_budget),
                      avg_total_cost = COALESCE((avg_total_cost * request_count + excluded.avg_total_cost) / (request_count + 1), avg_total_cost),
                      updated_at = excluded.updated_at
                    """,
                    (route_key, request.budget, total_cost, now),
                )
        return {
            "success": True,
            "request_id": request_id,
            "plan_id": plan_id if plan is not None else None,
            "request_fingerprint": fingerprint,
            "route_key": route_key,
            "db_path": str(self.db_path),
        }


def write_trip_best_effort(
    request: PlanRequest,
    plan: dict[str, Any] | None,
    *,
    meta: dict[str, Any] | None = None,
    used_realtime: bool = False,
    used_history: bool = False,
) -> dict[str, Any]:
    try:
        return TravelMemoryStore().write_trip(
            request,
            plan,
            meta=meta,
            used_realtime=used_realtime,
            used_history=used_history,
        )
    except Exception as exc:
        return {"success": False, "error": str(exc)}
