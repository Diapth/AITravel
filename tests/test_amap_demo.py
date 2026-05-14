from fastapi.testclient import TestClient

from app import amap_demo
from app.main import app


def test_amap_demo_pois_uses_amap_client(monkeypatch):
    captured = {}

    def fake_get(self, url, params):
        captured["url"] = url
        captured["params"] = params
        return {"status": "1", "infocode": "10000", "pois": [{"name": "观前街餐厅"}]}

    monkeypatch.setattr(amap_demo.AmapDemoClient, "_get", fake_get)
    client = TestClient(app)

    response = client.get("/api/amap-demo/pois", params={"city": "苏州", "keywords": "餐厅"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["source"] == "amap"
    assert payload["data"] == [{"name": "观前街餐厅"}]
    assert captured["url"] == amap_demo.AMAP_PLACE_TEXT_URL
    assert captured["params"]["city"] == "苏州"
    assert captured["params"]["keywords"] == "餐厅"


def test_amap_demo_route_requires_city_for_transit():
    client = TestClient(app)

    response = client.get(
        "/api/amap-demo/route",
        params={"origin": "120.1,31.1", "destination": "120.2,31.2", "mode": "transit"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "CITY_REQUIRED"


def test_amap_demo_weather_reports_missing_key(monkeypatch):
    monkeypatch.setattr(amap_demo, "get_amap_key", lambda: None)
    client = TestClient(app)

    response = client.get("/api/amap-demo/weather", params={"city": "苏州"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["source"] == "amap"
    assert payload["error"]["code"] == "AMAP_KEY_MISSING"


def test_amap_demo_explains_jsapi_key_platform_mismatch(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "0", "infocode": "10009", "info": "USERKEY_PLAT_NOMATCH"}

    def fake_get(self, url, params):
        return FakeResponse()

    monkeypatch.setattr(amap_demo.httpx.Client, "get", fake_get)

    try:
        amap_demo.AmapDemoClient(api_key="jsapi-key").weather("南京")
    except amap_demo.AmapDemoError as exc:
        response = amap_demo.amap_demo_error(exc)

    assert response["success"] is False
    assert response["error"]["code"] == "AMAP_RESPONSE_ERROR"
    assert "Web Service" in response["error"]["message"]


def test_amap_demo_does_not_block_plan_when_amap_fails(monkeypatch):
    monkeypatch.setattr(
        "app.main.check_runtime",
        lambda: {
            "ok": True,
            "deepseek_key_configured": True,
            "database_ready": True,
            "sqlite_database_ready": True,
            "sqlite_database_path": "chinatravel/environment/database/chinatravel.sqlite",
            "missing_database_paths": [],
        },
    )

    class FakePlanner:
        def plan(self, request):
            return {"success": True, "plan": {"itinerary": []}, "meta": {"agent": "test"}}

    monkeypatch.setattr("app.main.get_planner", lambda: FakePlanner())
    client = TestClient(app)

    response = client.post("/api/plan", json={"query": "从上海去苏州"})

    assert response.status_code == 200
    assert response.json()["success"] is True
