from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_SQLITE_PATH = Path(__file__).resolve().parent / "database" / "chinatravel.sqlite"


def get_database_path() -> Path:
    configured = os.environ.get("CHINATRAVEL_SQLITE_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_SQLITE_PATH


def sqlite_available() -> bool:
    return get_database_path().exists()


def connect() -> sqlite3.Connection:
    return sqlite3.connect(get_database_path())


def read_city_table(table: str, city: str) -> pd.DataFrame:
    with connect() as connection:
        return pd.read_sql_query(
            f"SELECT * FROM {table} WHERE city = ? ORDER BY id",
            connection,
            params=(city,),
        ).drop(columns=["city"], errors="ignore")


def read_dataframe(query: str, params: tuple[Any, ...] = ()) -> pd.DataFrame:
    with connect() as connection:
        return pd.read_sql_query(query, connection, params=params)


def read_json_blob(key: str) -> Any:
    with connect() as connection:
        row = connection.execute(
            "SELECT value FROM json_blobs WHERE key = ?",
            (key,),
        ).fetchone()
    if row is None:
        raise KeyError(key)
    return json.loads(row[0])
