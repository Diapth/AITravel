from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chinatravel.config import get_bool_env, get_env_value, get_float_env, get_int_env


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


def get_deepseek_config(env_file: str | Path | None = None) -> DeepSeekConfig:
    return DeepSeekConfig(
        api_key=get_env_value("DEEPSEEK_API_KEY", "OPENAI_API_KEY", env_file=env_file),
        base_url=get_env_value("DEEPSEEK_BASE_URL", env_file=env_file) or DeepSeekConfig.base_url,
        model=get_env_value("DEEPSEEK_MODEL", env_file=env_file) or DeepSeekConfig.model,
        max_tokens=get_int_env("DEEPSEEK_MAX_TOKENS", DeepSeekConfig.max_tokens, env_file=env_file),
        temperature=get_float_env(
            "DEEPSEEK_TEMPERATURE",
            DeepSeekConfig.temperature,
            env_file=env_file,
        ),
        top_p=get_float_env("DEEPSEEK_TOP_P", DeepSeekConfig.top_p, env_file=env_file),
        trust_env_proxy=get_bool_env(
            "DEEPSEEK_TRUST_ENV_PROXY",
            DeepSeekConfig.trust_env_proxy,
            env_file=env_file,
        ),
    )
