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
)


@pytest.fixture(autouse=True)
def isolate_product_env(monkeypatch, tmp_path):
    for name in PRODUCT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setattr(
        "chinatravel.config.DEFAULT_ENV_FILE",
        Path(tmp_path) / ".env.missing",
    )
