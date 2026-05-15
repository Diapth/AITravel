from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import httpx

from app.realtime.evidence import EvidenceCard, normalize_evidence
from chinatravel.config import get_env_value, get_int_env


TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_TAVILY_TIMEOUT_SEC = 10
DEFAULT_TAVILY_MAX_RESULTS = 5
DEFAULT_TAVILY_SEARCH_DEPTH = "basic"


@dataclass(frozen=True)
class TavilySearchResult:
    success: bool
    evidence: list[EvidenceCard]
    usage: dict[str, Any] | None = None
    error: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "evidence": [card.to_dict() for card in self.evidence],
            "usage": self.usage or {},
            "error": self.error,
        }


def get_tavily_api_key() -> str | None:
    return get_env_value("TAVILY_API_KEY", "TAVILY_SEARCH_KEY")


class TavilySearchClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float | None = None,
        endpoint: str = TAVILY_SEARCH_URL,
    ) -> None:
        self.api_key = api_key if api_key is not None else get_tavily_api_key()
        self.timeout = timeout or get_int_env("CHINATRAVEL_TAVILY_TIMEOUT_SEC", DEFAULT_TAVILY_TIMEOUT_SEC)
        self.endpoint = endpoint

    def search(
        self,
        query: str,
        *,
        topic: str = "general",
        search_depth: str = DEFAULT_TAVILY_SEARCH_DEPTH,
        max_results: int | None = None,
        time_range: str | None = None,
        include_domains: list[str] | None = None,
    ) -> TavilySearchResult:
        keyword = query.strip()
        if not keyword:
            return TavilySearchResult(
                success=False,
                evidence=[],
                error={"code": "TAVILY_EMPTY_QUERY", "message": "Tavily search query must not be blank."},
            )
        if not self.api_key:
            return TavilySearchResult(
                success=False,
                evidence=[],
                error={"code": "TAVILY_KEY_MISSING", "message": "Tavily API key is not configured."},
            )

        payload: dict[str, Any] = {
            "query": keyword,
            "topic": topic,
            "search_depth": search_depth,
            "max_results": max_results
            if max_results is not None
            else get_int_env("CHINATRAVEL_TAVILY_MAX_RESULTS", DEFAULT_TAVILY_MAX_RESULTS),
            "include_answer": False,
            "include_raw_content": False,
            "include_usage": True,
            "auto_parameters": False,
            "country": "china",
        }
        if time_range:
            payload["time_range"] = time_range
        if include_domains:
            payload["include_domains"] = include_domains

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.post(
                    self.endpoint,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            return TavilySearchResult(
                success=False,
                evidence=[],
                error={"code": "TAVILY_REQUEST_FAILED", "message": str(exc)},
            )

        results = data.get("results") if isinstance(data, dict) else None
        evidence = normalize_evidence(results if isinstance(results, list) else [])
        usage = data.get("usage") if isinstance(data, dict) and isinstance(data.get("usage"), dict) else {}
        if isinstance(data, dict) and "credits_used" in data:
            usage = {**usage, "credits_used": data["credits_used"]}
        return TavilySearchResult(success=True, evidence=evidence, usage=usage, error=None)


def tavily_result_from_cache(payload: dict[str, Any]) -> TavilySearchResult:
    evidence_items = payload.get("evidence", [])
    evidence = [
        EvidenceCard(**item)
        for item in evidence_items
        if isinstance(item, dict)
        and {"title", "url", "content_summary", "source", "fetched_at", "expires_at", "confidence", "risk_flags"} <= set(item)
    ]
    return TavilySearchResult(
        success=bool(payload.get("success", True)),
        evidence=evidence,
        usage=payload.get("usage") if isinstance(payload.get("usage"), dict) else {},
        error=payload.get("error") if isinstance(payload.get("error"), dict) else None,
    )


def tavily_result_to_cache(result: TavilySearchResult) -> dict[str, Any]:
    return asdict(result)
