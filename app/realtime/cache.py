from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_CACHE_TTL_HOURS = 24


def stable_params_hash(params: dict[str, Any]) -> str:
    payload = json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_cache_key(provider: str, query: str, params: dict[str, Any]) -> str:
    normalized_query = " ".join(query.strip().lower().split())
    key_payload = {
        "provider": provider,
        "query": normalized_query,
        "params": stable_params_hash(params),
    }
    return stable_params_hash(key_payload)


class SearchCache:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS search_cache (
                  cache_key TEXT PRIMARY KEY,
                  provider TEXT NOT NULL,
                  query TEXT NOT NULL,
                  params_json TEXT NOT NULL,
                  response_json TEXT NOT NULL,
                  evidence_json TEXT NOT NULL,
                  usage_json TEXT,
                  fetched_at TEXT NOT NULL,
                  expires_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_search_cache_expires_at ON search_cache(expires_at)")

    def get(self, cache_key: str, *, now: datetime | None = None) -> dict[str, Any] | None:
        current = now or datetime.now(timezone.utc)
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT response_json, expires_at FROM search_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if row is None:
            return None
        expires_at = datetime.fromisoformat(str(row["expires_at"]))
        if expires_at <= current:
            return None
        return json.loads(str(row["response_json"]))

    def set(
        self,
        cache_key: str,
        *,
        provider: str,
        query: str,
        params: dict[str, Any],
        response: dict[str, Any],
        ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(timezone.utc)
        expires_at = current + timedelta(hours=ttl_hours)
        evidence = response.get("evidence", [])
        usage = response.get("usage", {})
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO search_cache (
                  cache_key, provider, query, params_json, response_json,
                  evidence_json, usage_json, fetched_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cache_key,
                    provider,
                    query,
                    json.dumps(params, ensure_ascii=False, sort_keys=True),
                    json.dumps(response, ensure_ascii=False, sort_keys=True),
                    json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                    json.dumps(usage, ensure_ascii=False, sort_keys=True),
                    current.isoformat(),
                    expires_at.isoformat(),
                ),
            )
