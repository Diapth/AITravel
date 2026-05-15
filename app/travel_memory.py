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
                SELECT id, conversation_id, version_number, parent_version_id, source, summary, total_cost, request_id, created_at
                FROM plan_versions
                WHERE conversation_id = ?
                ORDER BY version_number DESC
                """,
                (conversation_id,),
            )
            versions = [self._row_to_dict(versions_cursor, row) for row in versions_cursor.fetchall()]

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
            "request_id": request_id,
            "created_at": now,
        }

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
