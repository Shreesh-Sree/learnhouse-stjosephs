"""Thin async client for a self-hosted Firecrawl instance.

Firecrawl (https://github.com/mendableai/firecrawl) is the web search/scrape
backend the course-authoring agents call to ground generated content in real,
currently-existing pages and videos — an LLM asked to fill in a `blockEmbed`
URL will happily invent a plausible-looking but non-existent YouTube video ID;
these calls give it something real to point at instead.

Unset `firecrawl_url` is a supported, first-class state (most deployments
won't run Firecrawl): every function here returns an empty/None result rather
than raising, and callers use ``is_configured()`` to decide whether to
register the corresponding agent tool at all.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from config.config import get_learnhouse_config

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20.0


def is_configured() -> bool:
    cfg = get_learnhouse_config().ai_config
    return bool(getattr(cfg, "firecrawl_url", None))


def _client() -> Optional[httpx.AsyncClient]:
    cfg = get_learnhouse_config().ai_config
    base_url = getattr(cfg, "firecrawl_url", None)
    if not base_url:
        return None
    api_key = getattr(cfg, "firecrawl_api_key", None)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return httpx.AsyncClient(
        base_url=base_url.rstrip("/"), headers=headers, timeout=DEFAULT_TIMEOUT
    )


async def search(query: str, limit: int = 5) -> list[dict]:
    """Search the web via Firecrawl. Returns [] if unconfigured or on failure —
    never raises, so a flaky/misconfigured Firecrawl degrades the agent (no
    search results) rather than breaking generation entirely."""
    client = _client()
    if client is None:
        return []
    try:
        async with client:
            resp = await client.post("/v1/search", json={"query": query, "limit": limit})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("Firecrawl search failed for %r: %s", query, e)
        return []

    results = data.get("data") or []
    return [
        {
            "title": r.get("title") or "",
            "url": r.get("url") or "",
            "description": r.get("description") or "",
        }
        for r in results
        if r.get("url")
    ]


async def scrape(url: str) -> Optional[str]:
    """Fetch a single URL's content as clean markdown via Firecrawl. Returns
    None if unconfigured or on failure."""
    client = _client()
    if client is None:
        return None
    try:
        async with client:
            resp = await client.post(
                "/v1/scrape", json={"url": url, "formats": ["markdown"]}
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("Firecrawl scrape failed for %r: %s", url, e)
        return None

    return (data.get("data") or {}).get("markdown")
