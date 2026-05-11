from pathlib import Path


def test_frontend_files_exist():
    for relative_path in [
        Path("frontend/index.html"),
        Path("frontend/styles.css"),
        Path("frontend/app.js"),
    ]:
        assert relative_path.exists(), relative_path


def test_frontend_html_mentions_plan_form():
    html = Path("frontend/index.html").read_text(encoding="utf-8")

    assert "ChinaTravel" in html
    assert "旅行需求" in html
    assert "生成行程" in html
