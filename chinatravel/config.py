from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"


def load_project_env(env_file: str | Path | None = None) -> bool:
    """Load product configuration from .env without overriding shell values."""
    path = Path(env_file) if env_file is not None else DEFAULT_ENV_FILE
    if not path.exists():
        return False
    return load_dotenv(dotenv_path=path, override=False)


def get_env_value(*names: str, env_file: str | Path | None = None) -> str | None:
    load_project_env(env_file)
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def get_env_file_value(name: str, env_file: str | Path | None = None) -> str | None:
    path = Path(env_file) if env_file is not None else DEFAULT_ENV_FILE
    if not path.exists():
        return None
    value = dotenv_values(path).get(name)
    if value:
        return str(value)
    return None


def get_bool_env(name: str, default: bool = False, env_file: str | Path | None = None) -> bool:
    value = get_env_value(name, env_file=env_file)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def get_int_env(name: str, default: int, env_file: str | Path | None = None) -> int:
    value = get_env_value(name, env_file=env_file)
    if value is None:
        return default
    return int(value)


def get_float_env(name: str, default: float, env_file: str | Path | None = None) -> float:
    value = get_env_value(name, env_file=env_file)
    if value is None:
        return default
    return float(value)
