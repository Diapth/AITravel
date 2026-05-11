from pathlib import Path


def test_product_readme_mentions_fastapi_and_plan_api():
    text = Path("README.md").read_text(encoding="utf-8")

    assert "FastAPI" in text
    assert "/api/plan" in text
    assert "LLMNeSy" in text


def test_experiment_entrypoints_removed():
    for relative_path in [
        Path("run_exp.py"),
        Path("eval_exp.py"),
        Path("run_tpc.py"),
        Path("eval_tpc.py"),
        Path("download_llm.sh"),
    ]:
        assert not relative_path.exists(), relative_path
