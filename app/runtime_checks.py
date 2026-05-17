from __future__ import annotations

from pathlib import Path
from typing import Any

from chinatravel.config import get_bool_env, get_env_value


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_ROOT = Path("chinatravel/environment/database")
SQLITE_DATABASE_PATH = DATABASE_ROOT / "chinatravel.sqlite"
REQUIRED_DATABASE_PATHS = (
    Path("attractions"),
    Path("restaurants"),
    Path("accommodations"),
    Path("intercity_transport"),
    Path("transportation"),
    Path("poi"),
)


def get_deepseek_api_key(env_file: str | Path | None = None) -> str | None:
    return get_env_value("DEEPSEEK_API_KEY", "OPENAI_API_KEY", env_file=env_file)


def get_tavily_api_key(env_file: str | Path | None = None) -> str | None:
    return get_env_value("TAVILY_API_KEY", "TAVILY_SEARCH_KEY", env_file=env_file)


def check_runtime(project_root: Path | None = None) -> dict[str, Any]:
    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    missing_database_paths = []
    sqlite_database_path = root / SQLITE_DATABASE_PATH

    for relative_path in REQUIRED_DATABASE_PATHS:
        database_path = root / DATABASE_ROOT / relative_path
        if not database_path.exists():
            missing_database_paths.append(str(DATABASE_ROOT / relative_path))

    deepseek_key_configured = bool(get_deepseek_api_key())
    tavily_key_configured = bool(get_tavily_api_key())
    tavily_real_time_enabled = get_bool_env("TAVILY_REAL_TIME_ENABLED", False)
    sqlite_database_ready = sqlite_database_path.exists()
    legacy_database_ready = not missing_database_paths
    database_ready = sqlite_database_ready or legacy_database_ready

    return {
        "ok": deepseek_key_configured and database_ready,
        "deepseek_key_configured": deepseek_key_configured,
        "tavily_key_configured": tavily_key_configured,
        "tavily_real_time_enabled": tavily_real_time_enabled,
        "database_ready": database_ready,
        "sqlite_database_ready": sqlite_database_ready,
        "sqlite_database_path": str(SQLITE_DATABASE_PATH),
        "missing_database_paths": missing_database_paths,
    }
