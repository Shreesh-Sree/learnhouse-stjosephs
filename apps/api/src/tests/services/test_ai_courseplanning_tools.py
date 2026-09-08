"""Course-planning/activity-content generation actually offers its tools to
the model when Firecrawl is configured, and doesn't when it isn't — the
system-prompt guidance and the tools kwarg passed to generate_stream must
agree, so the model is never told about tools it doesn't have or left
silent about ones it does.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.ai import courseplanning
from src.services.ai.tools import firecrawl


def _patch_firecrawl(monkeypatch, configured: bool):
    cfg = SimpleNamespace(
        firecrawl_url="http://localhost:3002" if configured else None,
        firecrawl_api_key=None,
    )
    monkeypatch.setattr(
        firecrawl, "get_learnhouse_config", lambda: SimpleNamespace(ai_config=cfg)
    )


async def _fake_stream(*args, **kwargs):
    yield '{"name": "n", "description": "d", "chapters": []}'


def _session():
    return courseplanning.CoursePlanningSessionData(session_uuid="s1", org_id=1)


class TestCoursePlanToolWiring:
    @pytest.mark.asyncio
    async def test_tools_passed_through_when_firecrawl_configured(self, monkeypatch):
        _patch_firecrawl(monkeypatch, configured=True)
        monkeypatch.setattr(courseplanning, "save_course_planning_session", lambda s: True)
        captured = {}

        def fake_generate_stream(**kwargs):
            captured.update(kwargs)
            return _fake_stream()

        monkeypatch.setattr(courseplanning, "generate_stream", fake_generate_stream)

        async for _ in courseplanning.generate_course_plan_stream("build a python course", _session()):
            pass

        assert len(captured["tools"]) == 3
        assert "WEB SEARCH TOOLS" in captured["system_prompt"]

    @pytest.mark.asyncio
    async def test_no_tools_and_no_guidance_when_firecrawl_unconfigured(self, monkeypatch):
        _patch_firecrawl(monkeypatch, configured=False)
        monkeypatch.setattr(courseplanning, "save_course_planning_session", lambda s: True)
        captured = {}

        def fake_generate_stream(**kwargs):
            captured.update(kwargs)
            return _fake_stream()

        monkeypatch.setattr(courseplanning, "generate_stream", fake_generate_stream)

        async for _ in courseplanning.generate_course_plan_stream("build a python course", _session()):
            pass

        assert captured["tools"] == []
        assert "WEB SEARCH TOOLS" not in captured["system_prompt"]

    @pytest.mark.asyncio
    async def test_activity_content_generation_gets_tools_too(self, monkeypatch):
        _patch_firecrawl(monkeypatch, configured=True)
        monkeypatch.setattr(courseplanning, "save_course_planning_session", lambda s: True)
        captured = {}

        def fake_generate_stream(**kwargs):
            captured.update(kwargs)
            return _fake_stream()

        monkeypatch.setattr(courseplanning, "generate_stream", fake_generate_stream)

        async for _ in courseplanning.generate_activity_content_stream(
            session=_session(),
            activity_uuid="a1",
            activity_name="Intro",
            activity_description="desc",
            chapter_name="ch1",
            course_name="course",
            course_description="desc",
        ):
            pass

        assert len(captured["tools"]) == 3
        assert "find_video" in captured["system_prompt"]


class TestBlockEmbedGuardrail:
    def test_prompt_warns_against_fabricating_urls(self):
        prompt = courseplanning.build_activity_content_system_prompt(
            course_name="c", course_description="d", chapter_name="ch",
            activity_name="a", activity_description="d",
        )
        assert "Never invent a video ID or URL" in prompt
