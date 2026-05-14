from __future__ import annotations

from typing import Any

import httpx

from chinatravel.config import get_env_value


AMAP_KEY_ENV = "AMAP_WEB_SERVICE_KEY"
AMAP_PLACE_TEXT_URL = "https://restapi.amap.com/v5/place/text"
AMAP_ROUTE_URLS = {
    "driving": "https://restapi.amap.com/v5/direction/driving",
    "walking": "https://restapi.amap.com/v5/direction/walking",
    "transit": "https://restapi.amap.com/v5/direction/transit/integrated",
}
AMAP_WEATHER_URL = "https://restapi.amap.com/v3/weather/weatherInfo"


class AmapDemoError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def get_amap_key() -> str | None:
    return get_env_value(AMAP_KEY_ENV) or get_env_value("VITE_AMAP_API_KEY")


def amap_demo_response(data: Any, source: str = "amap") -> dict[str, Any]:
    return {"success": True, "data": data, "source": source}


def amap_demo_error(exc: AmapDemoError) -> dict[str, Any]:
    return {
        "success": False,
        "data": None,
        "source": "amap",
        "error": {"code": exc.code, "message": exc.message, "details": exc.details},
    }


class AmapDemoClient:
    def __init__(self, api_key: str | None = None, timeout: float = 8):
        self.api_key = api_key if api_key is not None else get_amap_key()
        self.timeout = timeout

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise AmapDemoError("AMAP_KEY_MISSING", "缺少 AMAP_WEB_SERVICE_KEY，无法调用高德 Web 服务。")

        request_params = {"key": self.api_key, **params}
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.get(url, params=request_params)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise AmapDemoError("AMAP_REQUEST_FAILED", str(exc)) from exc

        status = str(payload.get("status", "1"))
        infocode = str(payload.get("infocode", ""))
        if status != "1" or infocode not in ("", "10000"):
            message = str(payload.get("info") or "AMap request failed.")
            if infocode == "10009" or message == "USERKEY_PLAT_NOMATCH":
                message = (
                    "AMap key platform mismatch: configure a Web Service "
                    "AMAP_WEB_SERVICE_KEY instead of a JSAPI-only frontend key."
                )
            raise AmapDemoError(
                "AMAP_RESPONSE_ERROR",
                message,
                {"infocode": infocode},
            )
        return payload

    def search_pois(self, city: str, keywords: str, page_size: int = 10) -> list[dict[str, Any]]:
        payload = self._get(
            AMAP_PLACE_TEXT_URL,
            {
                "keywords": keywords,
                "city": city,
                "city_limit": "true",
                "page_size": max(1, min(page_size, 25)),
                "page_num": 1,
                "show_fields": "business,photos,cost",
            },
        )
        pois = payload.get("pois")
        return pois if isinstance(pois, list) else []

    def route(self, origin: str, destination: str, mode: str, city: str | None = None) -> dict[str, Any]:
        if mode not in AMAP_ROUTE_URLS:
            raise AmapDemoError("INVALID_ROUTE_MODE", "mode 仅支持 driving、walking、transit。")

        params: dict[str, Any] = {
            "origin": origin,
            "destination": destination,
            "show_fields": "cost",
        }
        if mode == "transit":
            if not city:
                raise AmapDemoError("CITY_REQUIRED", "公交/地铁路线需要提供 city 参数。")
            params["city1"] = city
            params["city2"] = city
        return self._get(AMAP_ROUTE_URLS[mode], params)

    def weather(self, city: str, extensions: str = "base") -> dict[str, Any]:
        if extensions not in ("base", "all"):
            raise AmapDemoError("INVALID_WEATHER_EXTENSIONS", "extensions 仅支持 base 或 all。")
        return self._get(
            AMAP_WEATHER_URL,
            {
                "city": city,
                "extensions": extensions,
            },
        )
