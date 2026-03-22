from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ElementType(str, Enum):
    """The small v1 element vocabulary keeps monitoring legible."""

    HEADLINE = "headline"
    SUBHEAD = "subhead"
    IMAGE = "image"
    LOGO = "logo"
    TEXT = "text"
    SHAPE = "shape"


@dataclass
class ElementStyle:
    """Minimal style surface for the initial control setting."""

    font_family: str = "sans-serif"
    font_size: int = 16
    font_weight: int = 400
    foreground: str = "#111111"
    background: str | None = None
    opacity: float = 1.0
    align: str = "left"
    border_radius: int = 0


_STYLE_KEYS = frozenset(ElementStyle.__dataclass_fields__)


def merge_element_style(
    base: ElementStyle,
    patch: dict[str, Any] | None,
) -> ElementStyle:
    """Return a copy of *base* with only known ``ElementStyle`` keys from *patch* applied.

    LLMs often emit CSS-like keys (e.g. ``line_height``) that are not part of the
    v1 schema; those are ignored so tool execution cannot crash.
    """
    data = asdict(base)
    for key, value in (patch or {}).items():
        if key in _STYLE_KEYS:
            data[key] = value
    return ElementStyle(**data)


@dataclass
class LayoutElement:
    """A rectangular design element on the canvas."""

    element_id: str
    element_type: ElementType
    x: int
    y: int
    width: int
    height: int
    content: str | None = None
    asset_id: str | None = None
    style: ElementStyle = field(default_factory=ElementStyle)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def bounds(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    def overlaps(self, other: "LayoutElement") -> bool:
        return not (
            self.right <= other.x
            or other.right <= self.x
            or self.bottom <= other.y
            or other.bottom <= self.y
        )

    def copy_with_style_patch(self, style_patch: dict[str, Any]) -> "LayoutElement":
        updated_style = merge_element_style(self.style, style_patch)
        return LayoutElement(
            element_id=self.element_id,
            element_type=self.element_type,
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
            content=self.content,
            asset_id=self.asset_id,
            style=updated_style,
            metadata=dict(self.metadata),
        )
