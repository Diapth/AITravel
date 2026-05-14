from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app
from app.train_12306 import Train12306Client


def test_train_12306_parses_ticket_row_and_prices(monkeypatch):
    client = Train12306Client()
    client._session_initialized = True
    client._station_code_to_name = {"BJP": "北京", "SHH": "上海"}
    client._station_name_to_code = {"北京": "BJP", "上海": "SHH"}

    raw_parts = [""] * 57
    raw_parts[2] = "240000G10000"
    raw_parts[3] = "G100"
    raw_parts[6] = "BJP"
    raw_parts[7] = "SHH"
    raw_parts[8] = "08:00"
    raw_parts[9] = "12:30"
    raw_parts[10] = "04:30"
    raw_parts[11] = "Y"
    raw_parts[16] = "01"
    raw_parts[17] = "05"
    raw_parts[26] = "无"
    raw_parts[30] = "有"
    raw_parts[31] = "12"
    raw_parts[32] = "3"
    raw_parts[35] = "9MOO"
    raw = "|".join(raw_parts)

    monkeypatch.setattr(
        client,
        "_query_payload",
        lambda date, from_code, to_code, purpose_codes: {
            "status": True,
            "httpstatus": 200,
            "data": {"result": [raw], "map": {"BJP": "北京", "SHH": "上海"}},
        },
    )
    monkeypatch.setattr(
        client,
        "_query_price",
        lambda row, date: {"business": "¥2158.0", "first": "¥1006.0", "second": "¥598.0"},
    )

    result = client.query_tickets("2026-05-20", "北京", "上海")

    assert result["count"] == 1
    item = result["items"][0]
    assert item["train_code"] == "G100"
    assert item["from_station"] == "北京"
    assert item["to_station"] == "上海"
    assert item["depart_time"] == "08:00"
    assert item["seats"]["business"]["left"] == "3"
    assert item["seats"]["second"]["left"] == "有"
    assert item["prices"]["second"] == "¥598.0"


def test_train_demo_endpoint_returns_unified_shape(monkeypatch):
    class FakeTrainClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def query_tickets(self, date, from_station, to_station, include_price=True, limit=30):
            return {
                "date": date,
                "from_station": from_station,
                "to_station": to_station,
                "count": 1,
                "items": [{"train_code": "G100"}],
            }

    monkeypatch.setattr(main_module, "Train12306Client", FakeTrainClient)
    client = TestClient(app)

    response = client.get(
        "/api/train-demo/tickets",
        params={"date": "2026-05-20", "from_station": "北京", "to_station": "上海"},
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["source"] == "12306"
    assert payload["data"]["items"][0]["train_code"] == "G100"
