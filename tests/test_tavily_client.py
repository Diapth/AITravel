import httpx

from app.realtime.tavily_client import TavilySearchClient, get_tavily_api_key


def test_tavily_key_prefers_api_key_and_falls_back(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "api-key")
    monkeypatch.setenv("TAVILY_SEARCH_KEY", "search-key")
    assert get_tavily_api_key() == "api-key"

    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    assert get_tavily_api_key() == "search-key"


def test_tavily_client_returns_key_missing_without_request(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_SEARCH_KEY", raising=False)

    result = TavilySearchClient(api_key="").search("苏州博物馆 最近公告")

    assert result.success is False
    assert result.error["code"] == "TAVILY_KEY_MISSING"


def test_tavily_client_normalizes_success_response(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "title": "苏州博物馆预约公告",
                        "url": "https://www.szmuseum.com/notice",
                        "content": "近期预约开放。",
                        "score": 0.93,
                    }
                ],
                "usage": {"credits": 1},
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, url, json, headers):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    result = TavilySearchClient(api_key="test-key").search("苏州博物馆", max_results=3)

    assert result.success is True
    assert result.evidence[0].title == "苏州博物馆预约公告"
    assert result.usage == {"credits": 1}
    assert captured["json"]["search_depth"] == "basic"
    assert captured["json"]["auto_parameters"] is False
    assert captured["json"]["include_raw_content"] is False
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_tavily_client_returns_request_failed(monkeypatch):
    class BrokenClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def post(self, *args, **kwargs):
            raise httpx.ConnectError("network down")

    monkeypatch.setattr(httpx, "Client", BrokenClient)

    result = TavilySearchClient(api_key="test-key").search("苏州博物馆")

    assert result.success is False
    assert result.error["code"] == "TAVILY_REQUEST_FAILED"
