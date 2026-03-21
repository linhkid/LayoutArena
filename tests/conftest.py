"""Shared fixtures for the LayoutArena test suite."""

from __future__ import annotations

import pytest

from layoutarena.env.elements import ElementType
from layoutarena.env.models import CanvasSpec, LayoutBrief, ProposedAction


@pytest.fixture
def canvas() -> CanvasSpec:
    return CanvasSpec(width=1200, height=800, min_spacing=24, max_elements=6)


@pytest.fixture
def brief() -> LayoutBrief:
    return LayoutBrief(
        brief_id="test_brief",
        title="Test Hero",
        instructions="Place required elements for testing.",
    )


@pytest.fixture
def nominal_actions(canvas) -> list[ProposedAction]:
    """A clean set of actions that always produce an accepted layout."""
    return [
        ProposedAction(
            tool_name="place_element",
            params={
                "element_type": ElementType.LOGO,
                "x": 56,
                "y": 40,
                "width": 132,
                "height": 48,
                "content": "Logo",
            },
        ),
        ProposedAction(
            tool_name="place_element",
            params={
                "element_type": ElementType.HEADLINE,
                "x": 80,
                "y": 140,
                "width": 460,
                "height": 96,
                "content": "Test Headline",
                "style_patch": {"font_size": 42, "font_weight": 700},
            },
        ),
        ProposedAction(
            tool_name="place_element",
            params={
                "element_type": ElementType.SUBHEAD,
                "x": 80,
                "y": 330,
                "width": 460,
                "height": 88,
                "content": "Test Subhead",
                "style_patch": {"font_size": 22},
            },
        ),
        ProposedAction(
            tool_name="place_element",
            params={
                "element_type": ElementType.IMAGE,
                "x": 700,
                "y": 120,
                "width": 360,
                "height": 420,
                "asset_id": "test_image",
            },
        ),
        ProposedAction(tool_name="submit_layout"),
    ]
