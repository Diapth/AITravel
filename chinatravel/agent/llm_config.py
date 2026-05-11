from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str | None = None
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    max_tokens: int = 4096
    temperature: float = 0
    top_p: float = 0.00000001
    trust_env_proxy: bool = False

    def request_kwargs(self, one_line: bool, json_mode: bool) -> dict:
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        if one_line:
            kwargs["stop"] = ["\n"]
        elif json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return kwargs


def get_deepseek_config() -> DeepSeekConfig:
    return DeepSeekConfig(
        api_key=os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", DeepSeekConfig.base_url),
        model=os.getenv("DEEPSEEK_MODEL", DeepSeekConfig.model),
        max_tokens=int(os.getenv("DEEPSEEK_MAX_TOKENS", DeepSeekConfig.max_tokens)),
        trust_env_proxy=os.getenv("DEEPSEEK_TRUST_ENV_PROXY", "").lower()
        in {"1", "true", "yes", "on"},
    )
