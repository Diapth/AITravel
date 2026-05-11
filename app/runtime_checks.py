from __future__ import annotations

import os
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_ROOT = Path("chinatravel/environment/database")
REQUIRED_DATABASE_PATHS = (
    Path("attractions"),
    Path("restaurants"),
    Path("accommodations"),
    Path("intercity_transport"),
    Path("transportation"),
    Path("poi"),
)


def get_deepseek_api_key() -> str | None:
    return os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")


def check_runtime(project_root: Path | None = None) -> dict[str, Any]:
    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    missing_database_paths = []

    for relative_path in REQUIRED_DATABASE_PATHS:
        database_path = root / DATABASE_ROOT / relative_path
        if not database_path.exists():
            missing_database_paths.append(str(DATABASE_ROOT / relative_path))

    deepseek_key_configured = bool(get_deepseek_api_key())
    database_ready = not missing_database_paths

    return {
        "ok": deepseek_key_configured and database_ready,
        "deepseek_key_configured": deepseek_key_configured,
        "database_ready": database_ready,
        "missing_database_paths": missing_database_paths,
    }
