from pathlib import Path

from chinatravel.agent.llm_config import DeepSeekConfig, get_deepseek_config


def test_deepseek_config_reads_environment(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")

    config = get_deepseek_config()

    assert config.api_key == "deepseek-key"
    assert config.base_url == "https://api.deepseek.com"
    assert config.model == "deepseek-chat"
    assert config.max_tokens == 4096
    assert config.trust_env_proxy is False


def test_llms_module_no_longer_imports_vllm():
    text = Path("chinatravel/agent/llms.py").read_text(encoding="utf-8")

    assert "vllm" not in text.lower()
    assert "SamplingParams" not in text
    assert "tiktoken" not in text
    assert "GPT4o" not in text


def test_deepseek_config_builds_request_kwargs():
    config = DeepSeekConfig(api_key="key", model="model-x", max_tokens=123)

    assert config.request_kwargs(one_line=True, json_mode=False) == {
        "model": "model-x",
        "max_tokens": 123,
        "temperature": 0,
        "top_p": 0.00000001,
        "stop": ["\n"],
    }
    assert config.request_kwargs(one_line=False, json_mode=True)["response_format"] == {
        "type": "json_object"
    }


def test_deepseek_config_can_enable_system_proxy(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_TRUST_ENV_PROXY", "true")

    assert get_deepseek_config().trust_env_proxy is True


def test_deepseek_config_can_read_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DEEPSEEK_API_KEY=dotenv-key",
                "DEEPSEEK_BASE_URL=https://example.deepseek.local",
                "DEEPSEEK_MODEL=deepseek-pro",
                "DEEPSEEK_MAX_TOKENS=2048",
                "DEEPSEEK_TEMPERATURE=0.3",
                "DEEPSEEK_TOP_P=0.9",
                "DEEPSEEK_TRUST_ENV_PROXY=true",
            ]
        ),
        encoding="utf-8",
    )

    config = get_deepseek_config(env_file=env_file)

    assert config.api_key == "dotenv-key"
    assert config.base_url == "https://example.deepseek.local"
    assert config.model == "deepseek-pro"
    assert config.max_tokens == 2048
    assert config.temperature == 0.3
    assert config.top_p == 0.9
    assert config.trust_env_proxy is True
