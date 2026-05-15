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
    value = get_env_value("CHINATRAVEL_TRIP_MEMORY_DB") or DEFAULT_MEMORY_DB
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parent.parent / path


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
