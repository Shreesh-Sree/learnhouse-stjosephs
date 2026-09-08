"""Pydantic AI tools for the course-planning and activity-content agents.

Each function here is a plain, type-annotated async function — Pydantic AI
introspects the signature and docstring to build the tool schema, so passing
these directly via ``Agent(model, tools=[...])`` is all that's needed.

``course_authoring_tools()`` is the single place callers ask "what tools does
this agent get" — right now that's just Firecrawl-backed search, gated on
whether Firecrawl is actually configured. Adding a tool later (e.g. a
YouTube-specific search once someone wires in a Data API key) means adding
one function here and one line in that list, not touching the agent
construction or system-prompt plumbing in courseplanning.py.
"""

from __future__ import annotations

import re
from typing import Optional

from src.services.ai.tools import firecrawl

_VIDEO_HOSTS = ("youtube.com", "youtu.be", "vimeo.com")

# Matches the video id out of the handful of YouTube URL shapes Firecrawl's
# search results actually return (watch?v=, youtu.be/, /embed/, /shorts/).
_YOUTUBE_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{6,})"
)


def _normalize_youtube_url(url: str) -> str:
    """A blockEmbed's embedUrl is rendered through the same tiptap YouTube
    extension as a manually-pasted link, which expects the canonical
    watch?v= form — normalize youtu.be/shorts/embed variants to that so the
    agent doesn't have to (and can't get it subtly wrong)."""
    match = _YOUTUBE_ID_RE.search(url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url


async def search_web(query: str) -> list[dict]:
    """Search the open web for pages relevant to `query`.

    Returns up to 5 results, each {"title", "url", "description"}. Use this
    before citing a fact or before pointing a blockEmbed at a video/article —
    never invent a URL from memory; if this returns nothing relevant, say so
    instead of guessing.
    """
    return await firecrawl.search(query, limit=5)


async def find_video(topic: str) -> Optional[dict]:
    """Search for a real, currently-existing YouTube or Vimeo video about
    `topic`.

    Returns {"title", "url"} with `url` already normalized to a working
    embeddable link, or None if no video result was found — in that case,
    skip the blockEmbed for this activity rather than fabricating a URL.
    """
    results = await firecrawl.search(f"{topic} video", limit=8)
    for r in results:
        url = r.get("url", "")
        if any(host in url for host in _VIDEO_HOSTS):
            return {"title": r.get("title") or topic, "url": _normalize_youtube_url(url)}
    return None


async def fetch_page_content(url: str) -> Optional[str]:
    """Fetch the clean text content of a specific page (markdown), to quote
    or summarize accurately instead of paraphrasing from memory. Returns
    None if the page couldn't be fetched."""
    return await firecrawl.scrape(url)


def course_authoring_tools() -> list:
    """Tools to register on the course-planning / activity-content agent.

    Empty when Firecrawl isn't configured — the agent falls back to its
    current (no-grounding) behavior with no code-path change, since Pydantic
    AI simply has no tools to offer the model in that case.
    """
    if not firecrawl.is_configured():
        return []
    return [search_web, find_video, fetch_page_content]
