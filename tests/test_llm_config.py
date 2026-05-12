from pathlib import Path

from chinatravel.agent import llms as llms_module
from chinatravel.agent.llms import trace_llm_call
from chinatravel.agent.utils import Logger
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
    assert config.disable_thinking is False


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


def test_deepseek_config_can_disable_thinking():
    config = DeepSeekConfig(api_key="key", disable_thinking=True)

    assert config.request_kwargs(one_line=False, json_mode=False)["extra_body"] == {
        "thinking": {"type": "disabled"}
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
                "DEEPSEEK_DISABLE_THINKING=true",
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
    assert config.disable_thinking is True


def test_logger_flush_writes_messages_immediately(tmp_path):
    log_file = tmp_path / "planner.log"
    logger = Logger(str(log_file))

    logger.write("search started\n")
    logger.flush()

    assert log_file.read_text(encoding="utf-8") == "search started\n"


def test_llm_trace_writes_raw_response_to_file_and_console(tmp_path, monkeypatch, capfd):
    monkeypatch.setenv("CHINATRAVEL_LLM_TRACE_ENABLED", "true")
    monkeypatch.setenv("CHINATRAVEL_LLM_TRACE_CONSOLE", "true")
    monkeypatch.setenv("CHINATRAVEL_LLM_TRACE_DIR", str(tmp_path))
    monkeypatch.setenv("CHINATRAVEL_REQUEST_ID", "web-test-request")

    trace_llm_call(
        call_id="call-test",
        model="deepseek-chat",
        messages=[{"role": "user", "content": "请规划上海到苏州两日游"}],
        response="AI 原始返回：推荐先坐高铁到苏州。",
        duration_sec=1.25,
        input_tokens=12,
        output_tokens=18,
        error=None,
    )

    console_output = capfd.readouterr().out
    trace_file = tmp_path / "web-test-request" / "llm_calls.jsonl"

    assert "web-test-request" in console_output
    assert "AI 原始返回：推荐先坐高铁到苏州。" in console_output
    assert trace_file.exists()
    assert "请规划上海到苏州两日游" in trace_file.read_text(encoding="utf-8")
    assert "AI 原始返回：推荐先坐高铁到苏州。" in trace_file.read_text(encoding="utf-8")


def test_llm_trace_defaults_to_logs_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(llms_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("CHINATRAVEL_LLM_TRACE_ENABLED", "true")
    monkeypatch.setenv("CHINATRAVEL_LLM_TRACE_CONSOLE", "false")
    monkeypatch.delenv("CHINATRAVEL_LLM_TRACE_DIR", raising=False)
    monkeypatch.setenv("CHINATRAVEL_REQUEST_ID", "web-default-log")

    trace_llm_call(
        call_id="call-default",
        model="deepseek-chat",
        messages=[{"role": "user", "content": "test"}],
        response="ok",
        duration_sec=0.1,
        input_tokens=1,
        output_tokens=1,
        error=None,
    )

    trace_file = tmp_path / "logs" / "web-default-log" / "llm_calls.jsonl"
    assert trace_file.exists()
