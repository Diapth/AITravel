from pathlib import Path
import builtins
import importlib
import sys


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


def test_data_helpers_import_without_huggingface_datasets(monkeypatch):
    sys.modules.pop("chinatravel.data.load_datasets", None)
    original_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name == "datasets":
            raise ImportError("datasets is optional for product runtime")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    module = importlib.import_module("chinatravel.data.load_datasets")

    assert callable(module.load_json_file)
    assert callable(module.save_json_file)


def test_product_constraint_modules_do_not_depend_on_removed_evaluation_package():
    for relative_path in [
        Path("chinatravel/symbol_verification/commonsense_constraint.py"),
        Path("chinatravel/symbol_verification/hard_constraint.py"),
        Path("chinatravel/symbol_verification/preference.py"),
    ]:
        source = relative_path.read_text(encoding="utf-8")

        assert "chinatravel.evaluation" not in source
