from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.runtime_checks import REQUIRED_DATABASE_PATHS, check_runtime


def test_check_runtime_reports_missing_key_and_database(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    status = check_runtime(project_root=tmp_path)

    assert status["ok"] is False
    assert status["deepseek_key_configured"] is False
    assert status["database_ready"] is False
    assert status["missing_database_paths"] == [
        str(Path("chinatravel/environment/database") / path)
        for path in REQUIRED_DATABASE_PATHS
    ]


def test_check_runtime_accepts_deepseek_key_and_database(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    database_root = tmp_path / "chinatravel" / "environment" / "database"
    for relative_path in REQUIRED_DATABASE_PATHS:
        (database_root / relative_path).mkdir(parents=True)

    status = check_runtime(project_root=tmp_path)

    assert status["ok"] is True
    assert status["deepseek_key_configured"] is True
    assert status["database_ready"] is True
    assert status["sqlite_database_ready"] is False
    assert status["sqlite_database_path"] == str(Path("chinatravel/environment/database/chinatravel.sqlite"))
    assert status["missing_database_paths"] == []


def test_deepseek_key_can_be_loaded_from_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=dotenv-key\n", encoding="utf-8")

    from app.runtime_checks import get_deepseek_api_key

    assert get_deepseek_api_key(env_file=env_file) == "dotenv-key"


def test_health_endpoint_returns_runtime_status():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert "ok" in payload
    assert "deepseek_key_configured" in payload
    assert "database_ready" in payload
    assert "missing_database_paths" in payload
