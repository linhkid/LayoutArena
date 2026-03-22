"""Tests for layout element and style helpers."""
from __future__ import annotations

from layoutarena.env.elements import ElementStyle, merge_element_style


def test_merge_element_style_ignores_unknown_keys():
    style = merge_element_style(
        ElementStyle(),
        {"line_height": 1.4, "letter_spacing": 2, "font_size": 40},
    )
    assert style.font_size == 40
    assert style.font_weight == 400


def test_merge_element_style_preserves_base():
    base = ElementStyle(font_size=22, opacity=0.9)
    style = merge_element_style(base, {"font_weight": 700})
    assert style.font_size == 22
    assert style.opacity == 0.9
    assert style.font_weight == 700
