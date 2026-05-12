from pathlib import Path


def test_environment_yaml_targets_product_env():
    text = Path("environment.yml").read_text(encoding="utf-8")

    assert "name: chinatravel-product" in text
    assert "- python=3.12" in text
    assert "pytest==8.4.2" in text


def test_runtime_http_dependencies_are_pinned():
    text = Path("requirements.txt").read_text(encoding="utf-8")

    assert "requests==" in text
    assert "urllib3==" in text


def test_yaml_runtime_dependency_uses_pyyaml_package_name():
    lines = Path("requirements.txt").read_text(encoding="utf-8").splitlines()

    assert "PyYAML==6.0.3" in lines
    assert "yaml" not in lines


def test_readme_covers_run_stack_and_todo():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 技术栈" in text
    assert "## 运行项目" in text
    assert "## 还没做的事" in text


def test_dotenv_example_documents_deepseek_configuration():
    example = Path(".env.example")
    text = example.read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "DEEPSEEK_API_KEY=" in text
    assert "DEEPSEEK_BASE_URL=https://api.deepseek.com" in text
    assert "DEEPSEEK_DISABLE_THINKING=false" in text
    assert "CHINATRAVEL_LLM_TRACE_DIR=logs" in text
    assert "api_request.json" in readme
    assert "api_response.json" in readme
    assert "llm_calls.jsonl" in readme
    assert "cp .env.example .env" in readme
