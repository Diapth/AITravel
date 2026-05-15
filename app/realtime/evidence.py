from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse


DEFAULT_EVIDENCE_TTL_HOURS = 24
DEFAULT_MAX_SUMMARY_CHARS = 800
RISK_PATTERNS = (
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"developer\s+message", re.IGNORECASE),
    re.compile(r"忽略(?:之前|以上|所有).{0,12}指令"),
    re.compile(r"无视(?:之前|以上|所有).{0,12}指令"),
    re.compile(r"系统提示词"),
)


@dataclass(frozen=True)
class EvidenceCard:
    title: str
    url: str
    content_summary: str
    source: str
    fetched_at: str
    expires_at: str
    confidence: float
    risk_flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "…"


def _source_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.") or "unknown"


def _risk_flags(text: str) -> list[str]:
    return ["prompt_injection"] if any(pattern.search(text) for pattern in RISK_PATTERNS) else []


def normalize_evidence_item(
    item: dict[str, Any],
    *,
    fetched_at: datetime | None = None,
    ttl_hours: int = DEFAULT_EVIDENCE_TTL_HOURS,
    max_summary_chars: int = DEFAULT_MAX_SUMMARY_CHARS,
) -> EvidenceCard | None:
    url = _clean_text(item.get("url"))
    title = _clean_text(item.get("title"))
    if not url or not title:
        return None

    raw_content = _clean_text(item.get("content") or item.get("snippet") or item.get("description"))
    flags = _risk_flags(f"{title} {raw_content}")
    confidence = float(item.get("score") or item.get("confidence") or 0.7)
    confidence = max(0.0, min(1.0, confidence))
    if flags:
        confidence = min(confidence, 0.3)

    now = fetched_at or utc_now()
    expires_at = now + timedelta(hours=ttl_hours)
    return EvidenceCard(
        title=_truncate(title, 200),
        url=url,
        content_summary=_truncate(raw_content, max_summary_chars),
        source=_source_from_url(url),
        fetched_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        confidence=confidence,
        risk_flags=flags,
    )


def normalize_evidence(
    items: list[dict[str, Any]],
    *,
    fetched_at: datetime | None = None,
    ttl_hours: int = DEFAULT_EVIDENCE_TTL_HOURS,
    max_summary_chars: int = DEFAULT_MAX_SUMMARY_CHARS,
) -> list[EvidenceCard]:
    cards: list[EvidenceCard] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        card = normalize_evidence_item(
            item,
            fetched_at=fetched_at,
            ttl_hours=ttl_hours,
            max_summary_chars=max_summary_chars,
        )
        if card is not None:
            cards.append(card)
    return cards
