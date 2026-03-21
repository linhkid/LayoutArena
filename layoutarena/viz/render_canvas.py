from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from layoutarena.env.elements import ElementType, LayoutElement
from layoutarena.env.models import LayoutSnapshot, LayoutState, Region


def render_state_svg(state: LayoutState, *, title: str | None = None) -> str:
    return _render_svg(
        canvas_width=state.canvas.width,
        canvas_height=state.canvas.height,
        elements=state.elements,
        blocked_regions=state.blocked_regions,
        title=title or state.brief.title,
        subtitle=state.brief.instructions,
    )


def render_snapshot_svg(snapshot: LayoutSnapshot, *, title: str | None = None) -> str:
    return _render_svg(
        canvas_width=snapshot.canvas_width,
        canvas_height=snapshot.canvas_height,
        elements=snapshot.elements,
        blocked_regions=snapshot.blocked_regions,
        title=title or f"Step {snapshot.step_index}: {snapshot.tool_name}",
        subtitle=f"{snapshot.status} | {snapshot.message}",
    )


def write_state_svg(
    state: LayoutState,
    output_path: str | Path,
    *,
    title: str | None = None,
) -> Path:
    target = Path(output_path)
    target.write_text(render_state_svg(state, title=title), encoding="utf-8")
    return target


def write_snapshot_svg(
    snapshot: LayoutSnapshot,
    output_path: str | Path,
    *,
    title: str | None = None,
) -> Path:
    target = Path(output_path)
    target.write_text(render_snapshot_svg(snapshot, title=title), encoding="utf-8")
    return target


def _render_svg(
    *,
    canvas_width: int,
    canvas_height: int,
    elements: dict[str, LayoutElement],
    blocked_regions: list[Region],
    title: str,
    subtitle: str,
) -> str:
    header = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{canvas_height + 72}" viewBox="0 0 {canvas_width} {canvas_height + 72}">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#f6f2ea"/>',
        f'<text x="24" y="28" font-family="Helvetica, Arial, sans-serif" font-size="22" font-weight="700" fill="#1c1c1c">{escape(title)}</text>',
        f'<text x="24" y="52" font-family="Helvetica, Arial, sans-serif" font-size="13" fill="#505050">{escape(subtitle)}</text>',
        f'<rect x="0" y="72" width="{canvas_width}" height="{canvas_height}" fill="#fffdf8" stroke="#ddd4c6" stroke-width="2"/>',
    ]

    blocked = [_render_blocked_region(region) for region in blocked_regions]
    nodes = [_render_element(element) for element in elements.values()]
    footer = ["</svg>"]
    return "\n".join(header + blocked + nodes + footer)


def _render_element(element: LayoutElement) -> str:
    fill = _fill_color(element.element_type)
    opacity = max(0.0, min(1.0, float(element.style.opacity)))
    rect_y = element.y + 72
    lines = [
        (
            f'<rect x="{element.x}" y="{rect_y}" width="{element.width}" height="{element.height}" '
            f'rx="{element.style.border_radius}" ry="{element.style.border_radius}" '
            f'fill="{fill}" fill-opacity="{opacity}" stroke="#202020" stroke-width="1.5"/>'
        ),
        (
            f'<text x="{element.x + 8}" y="{rect_y + 20}" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="12" font-weight="700" fill="#202020">{escape(element.element_id)}</text>'
        ),
        (
            f'<text x="{element.x + 8}" y="{rect_y + 38}" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="11" fill="#303030">{escape(element.element_type.value)}</text>'
        ),
    ]

    content = element.content or element.asset_id or ""
    if content:
        preview = content if len(content) <= 60 else f"{content[:57]}..."
        lines.append(
            (
                f'<text x="{element.x + 8}" y="{rect_y + min(element.height - 8, 58)}" '
                f'font-family="Helvetica, Arial, sans-serif" '
                f'font-size="{max(10, min(18, element.style.font_size))}" fill="#202020">'
                f"{escape(preview)}</text>"
            ),
        )

    return "\n".join(lines)


def _render_blocked_region(region: Region) -> str:
    x, y, width, height = region
    return (
        f'<rect x="{x}" y="{y + 72}" width="{width}" height="{height}" fill="none" '
        'stroke="#cf2f25" stroke-width="2" stroke-dasharray="8 4"/>'
    )


def _fill_color(element_type: ElementType) -> str:
    palette = {
        ElementType.LOGO: "#d4f0ff",
        ElementType.HEADLINE: "#f7d9c4",
        ElementType.SUBHEAD: "#f6ecc9",
        ElementType.IMAGE: "#d5ead8",
        ElementType.TEXT: "#f9d7e6",
        ElementType.SHAPE: "#efe3ff",
    }
    return palette[element_type]
