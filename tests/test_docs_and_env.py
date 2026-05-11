from pathlib import Path


def test_environment_yaml_targets_product_env():
    text = Path("environment.yml").read_text(encoding="utf-8")

    assert "name: chinatravel-product" in text
    assert "- python=3.12" in text
    assert "pytest==8.4.2" in text


def test_readme_covers_run_stack_and_todo():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "## 技术栈" in text
    assert "## 运行项目" in text
    assert "## 还没做的事" in text
