from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import unquote

import httpx


STATION_JS_URL = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
INIT_URL = "https://kyfw.12306.cn/otn/leftTicket/init"
QUERY_URL = "https://kyfw.12306.cn/otn/leftTicket/queryA"
PRICE_URL = "https://kyfw.12306.cn/otn/leftTicket/queryTicketPrice"
BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    ),
    "Referer": INIT_URL,
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

SEAT_FIELDS = {
    "business": {"left_index": 32, "price_keys": ("A9", "9"), "label": "商务座/特等座"},
    "first": {"left_index": 31, "price_keys": ("M",), "label": "一等座"},
    "second": {"left_index": 30, "price_keys": ("O",), "label": "二等座"},
    "no_seat": {"left_index": 26, "price_keys": ("WZ", "W"), "label": "无座"},
    "soft_sleeper": {"left_index": 23, "price_keys": ("A4", "4"), "label": "软卧"},
    "hard_sleeper": {"left_index": 28, "price_keys": ("A3", "3"), "label": "硬卧"},
    "hard_seat": {"left_index": 29, "price_keys": ("A1", "1"), "label": "硬座"},
}


class Train12306Error(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


def train_demo_response(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data, "source": "12306"}


def train_demo_error(exc: Train12306Error) -> dict[str, Any]:
    return {
        "success": False,
        "data": None,
        "source": "12306",
        "error": {"code": exc.code, "message": exc.message, "details": exc.details},
    }


def _normalize_left_ticket(value: str) -> str:
    if not value:
        return ""
    if value == "有":
        return "有"
    if value in ("无", "--"):
        return "无"
    return value


def _normalize_price(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.startswith("¥"):
        return text
    if text.startswith("\xa5"):
        return f"¥{text[1:]}"
    if text.isdigit() and len(text) > 2:
        return f"¥{int(text) / 10:.1f}"
    return text


class Train12306Client:
    def __init__(self, timeout: float = 10, retry: int = 1):
        self.timeout = timeout
        self.retry = retry
        self._client = httpx.Client(
            headers=BASE_HEADERS,
            timeout=httpx.Timeout(timeout, connect=8),
            follow_redirects=True,
        )
        self._station_code_to_name: dict[str, str] = {}
        self._station_name_to_code: dict[str, str] = {}
        self._session_initialized = False

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Train12306Client":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _ensure_session(self) -> None:
        if self._session_initialized:
            return
        try:
            response = self._client.get(INIT_URL)
            response.raise_for_status()
        except Exception as exc:
            raise Train12306Error("SESSION_INIT_FAILED", str(exc)) from exc
        self._session_initialized = True

    def load_station_map(self, force: bool = False) -> dict[str, str]:
        if self._station_code_to_name and not force:
            return self._station_code_to_name
        try:
            response = self._client.get(STATION_JS_URL)
            response.raise_for_status()
        except Exception as exc:
            raise Train12306Error("STATION_MAP_FAILED", str(exc)) from exc

        pattern = re.compile(r"@[^|]+\|([^|]+)\|([A-Z]{3})\|")
        self._station_code_to_name = {}
        self._station_name_to_code = {}
        for match in pattern.finditer(response.text):
            name, code = match.group(1), match.group(2)
            self._station_code_to_name[code] = name
            self._station_name_to_code[name] = code
        return self._station_code_to_name

    def resolve_station_code(self, station: str) -> str:
        station = station.strip()
        if re.fullmatch(r"[A-Z]{3}", station):
            return station
        self.load_station_map()
        if station in self._station_name_to_code:
            return self._station_name_to_code[station]
        for name, code in self._station_name_to_code.items():
            if station in name or name in station:
                return code
        raise Train12306Error("STATION_NOT_FOUND", f"未找到车站：{station}", {"station": station})

    def query_tickets(
        self,
        date: str,
        from_station: str,
        to_station: str,
        *,
        purpose_codes: str = "ADULT",
        include_price: bool = True,
        limit: int = 30,
    ) -> dict[str, Any]:
        self._ensure_session()
        self.load_station_map()
        from_code = self.resolve_station_code(from_station)
        to_code = self.resolve_station_code(to_station)

        payload = self._query_payload(date, from_code, to_code, purpose_codes)
        data = payload.get("data") or {}
        raw_rows = data.get("result") or []
        station_map = data.get("map") or {}
        rows = [self._parse_row(raw, station_map) for raw in raw_rows]
        rows = rows[: max(1, min(limit, 100))]

        price_errors: list[str] = []
        if include_price:
            for row in rows:
                try:
                    row["prices"] = self._query_price(row, date)
                except Exception as exc:
                    row["prices"] = {}
                    price_errors.append(f"{row.get('train_code')}: {exc}")

        return {
            "date": date,
            "from_station": self._station_code_to_name.get(from_code, from_code),
            "from_station_code": from_code,
            "to_station": self._station_code_to_name.get(to_code, to_code),
            "to_station_code": to_code,
            "count": len(raw_rows),
            "items": rows,
            "price_errors": price_errors,
            "note": "12306 网页接口非公开稳定开放 API，仅建议低频参考查询；失败时应降级到本地交通参考。",
        }

    def _query_payload(self, date: str, from_code: str, to_code: str, purpose_codes: str) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self.retry + 1):
            try:
                response = self._client.get(
                    QUERY_URL,
                    params={
                        "leftTicketDTO.train_date": date,
                        "leftTicketDTO.from_station": from_code,
                        "leftTicketDTO.to_station": to_code,
                        "purpose_codes": purpose_codes,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("httpstatus") != 200 or payload.get("status") is False:
                    raise Train12306Error("QUERY_RESPONSE_ERROR", "12306 返回查询失败", payload)
                return payload
            except Exception as exc:
                last_exc = exc
                if attempt < self.retry:
                    self._session_initialized = False
                    self._ensure_session()
                    time.sleep(0.8)
        raise Train12306Error(
            "QUERY_FAILED",
            str(last_exc),
            {"date": date, "from_station": from_code, "to_station": to_code},
        ) from last_exc

    def _parse_row(self, raw: str, station_map: dict[str, str]) -> dict[str, Any]:
        parts = unquote(raw).split("|")

        def part(index: int) -> str:
            return parts[index] if index < len(parts) else ""

        from_code = part(6) or part(4)
        to_code = part(7) or part(5)
        seats = {
            key: {
                "label": config["label"],
                "left": _normalize_left_ticket(part(int(config["left_index"]))),
            }
            for key, config in SEAT_FIELDS.items()
        }
        return {
            "train_code": part(3),
            "train_no": part(2),
            "from_station": station_map.get(from_code) or self._station_code_to_name.get(from_code, from_code),
            "from_station_code": from_code,
            "to_station": station_map.get(to_code) or self._station_code_to_name.get(to_code, to_code),
            "to_station_code": to_code,
            "depart_time": part(8),
            "arrive_time": part(9),
            "duration": part(10),
            "saleable": part(11) == "Y",
            "from_station_no": part(16),
            "to_station_no": part(17),
            "seat_types": part(35),
            "seats": seats,
        }

    def _query_price(self, row: dict[str, Any], date: str) -> dict[str, str]:
        if not row.get("train_no") or not row.get("from_station_no") or not row.get("to_station_no"):
            return {}
        response = self._client.get(
            PRICE_URL,
            params={
                "train_no": row["train_no"],
                "from_station_no": row["from_station_no"],
                "to_station_no": row["to_station_no"],
                "seat_types": row.get("seat_types") or "",
                "train_date": date,
            },
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or {}
        prices: dict[str, str] = {}
        for seat_key, config in SEAT_FIELDS.items():
            for price_key in config["price_keys"]:
                value = _normalize_price(data.get(price_key))
                if value:
                    prices[seat_key] = value
                    break
        return prices
