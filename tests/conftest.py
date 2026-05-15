from pathlib import Path

import pytest


PRODUCT_ENV_VARS = (
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_MAX_TOKENS",
    "DEEPSEEK_TEMPERATURE",
    "DEEPSEEK_TOP_P",
    "DEEPSEEK_TRUST_ENV_PROXY",
    "DEEPSEEK_DISABLE_THINKING",
    "CHINATRAVEL_LLM_TRACE_ENABLED",
    "CHINATRAVEL_LLM_TRACE_CONSOLE",
    "CHINATRAVEL_LLM_TRACE_CONSOLE_PROMPTS",
    "CHINATRAVEL_LLM_TRACE_DIR",
    "TAVILY_API_KEY",
    "TAVILY_SEARCH_KEY",
    "TAVILY_REAL_TIME_ENABLED",
    "CHINATRAVEL_TAVILY_SEARCH_DEPTH",
    "CHINATRAVEL_TAVILY_MAX_RESULTS",
    "CHINATRAVEL_TAVILY_TIMEOUT_SEC",
    "CHINATRAVEL_MEMORY_DB_PATH",
    "CHINATRAVEL_TRIP_MEMORY_DB",
)


@pytest.fixture(autouse=True)
def isolate_product_env(monkeypatch, tmp_path):
    for name in PRODUCT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("CHINATRAVEL_LLM_TRACE_ENABLED", "false")

    monkeypatch.setattr(
        "chinatravel.config.DEFAULT_ENV_FILE",
        Path(tmp_path) / ".env.missing",
    )
