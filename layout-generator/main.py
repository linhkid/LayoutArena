"""Minimal layout generation pipeline: LLM + HumanTools + Asset Library."""

import atexit
import argparse
from datetime import datetime
import json
import socket
import subprocess
import time
import traceback
from pathlib import Path

import requests

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from llm import call_llm
from renderer import ObelloRenderer
from tools import HumanToolLayoutTransformer
from asset_library import AssetLibrary

API_RENDER_DIR = Path(__file__).parent / "api-render"
_render_proc: subprocess.Popen | None = None
_render_endpoint: str | None = None


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def _find_free_port(start: int = 3000, end: int = 3100) -> int:
    for port in range(start, end):
        if not _port_in_use(port):
            return port
    raise RuntimeError(f"No free port found in {start}-{end}")


def ensure_renderer(timeout: int = 30) -> str:
    """Start api-render server if not already running. Returns the endpoint URL."""
    global _render_proc, _render_endpoint
    if _render_endpoint:
        return _render_endpoint

    # Check if already running on default port
    if _port_in_use(3000):
        try:
            requests.get("http://localhost:3000", timeout=2)
            _render_endpoint = "http://localhost:3000"
            return _render_endpoint
        except requests.ConnectionError:
            pass  # port taken by something else

    port = _find_free_port()
    endpoint = f"http://localhost:{port}"
    print(f"Starting api-render on port {port}...")

    _render_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "-p", str(port)],
        cwd=API_RENDER_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    atexit.register(lambda: _render_proc.terminate() if _render_proc and _render_proc.poll() is None else None)

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(endpoint, timeout=2)
            print(f"Renderer ready at {endpoint}")
            _render_endpoint = endpoint
            return endpoint
        except requests.ConnectionError:
            time.sleep(1)
    raise RuntimeError(f"api-render failed to start within {timeout}s")

SYSTEM_PROMPT = """\
You are an expert graphic designer. You compose professional, visually striking layouts by writing Python code that uses `HumanToolLayoutTransformer`.

## API

All methods that take `ids` accept a single id string OR a list of id strings.

```python
# The transformer is pre-initialized as `T` with a blank canvas.
# Available assets are in the `ASSETS` dict keyed by asset_id → data_url string.

# --- Add elements ---
T.add_element(type, x, y, w, h, **kwargs) → new_id
# type: "image", "svg", "text"
# For images/svgs: pass src=ASSETS["asset_id"]
# For text: pass text="...", fontFamily="...", fontSize=N, textFill="#hex", align="left|center|right", lineHeight=1.2

# --- Move & Resize ---
T.move_elements(ids, dx, dy)
T.resize_elements(ids, w, h, lock_aspect=True, anchor="center"|"top-left")

# --- Layout ---
T.align_elements(ids, align_x="left|center|right", align_y="top|middle|bottom", to_stage=False)
T.distribute_elements(ids, axis="x"|"y", spacing=N)
T.create_grid_layout(ids, cols, gutter=10)

# --- Layer order ---
T.reorder_layer(ids, "front"|"back"|"forward"|"backward")

# --- Style (works for any property including text properties) ---
T.update_style(ids, fill=, stroke=, opacity=, cornerRadius=, text=, fontFamily=, fontSize=, textFill=, align=, lineHeight=, ...)

# --- Delete ---
T.delete_elements(ids)

# --- Grouping ---
T.group_elements(ids) → group_id
T.ungroup_elements(group_id)

# --- Canvas background ---
# Set via layout dict directly: T.layout["background"] = "#hexcolor"
```

## Design Principles
- **Visual hierarchy**: One dominant element (hero image or headline), supporting elements smaller. Size contrast creates focus.
- **Whitespace**: Leave breathing room. Margins of 40-80px from canvas edges. Don't crowd elements.
- **Alignment**: Align elements to a consistent grid or axis. Left-align text blocks together. Center-align headlines.
- **Color harmony**: Pick 2-3 colors max. Use a dark background with light text, or vice versa. NEVER use the same color for text and background — ensure strong contrast for readability.
- **Typography scale**: Headlines 60-140px bold, subheads 28-45px, body 14-22px. One font for headlines, one for body. Max 2 fonts.
- **Layer order**: Background shapes go to back. Text always on top. Decorative elements behind content.
- **Composition**: Use shapes as colored panels/cards behind text groups for readability. Overlap images with text panels for depth.

## Rules
- Output ONLY a Python code block. No explanation outside the code block.
- Use ALL relevant assets from the library — don't leave good assets unused. Pick the ones that match the design intent.
- Every text element must have explicit fontFamily, fontSize, textFill, and align.
- Build the layout back-to-front: background → shapes/panels → images → text on top.
- Store every element ID from add_element for later alignment/reordering.
- Keep images at reasonable aspect ratios (use lock_aspect=True when resizing).
"""


def build_user_prompt(brief: str, library: AssetLibrary, canvas_width: int, canvas_height: int) -> list:
    """Build multimodal user prompt with asset thumbnails so the LLM can see them."""
    parts: list = []

    parts.append({"type": "text", "text": f"## Canvas: {canvas_width} x {canvas_height} px\n\n## Design Intent\n{brief}\n\n## Available Assets\n"})

    for cat in ["images", "logos", "shapes"]:
        items = library.by_category(cat)
        if not items:
            continue
        parts.append({"type": "text", "text": f"\n### {cat.upper()} ({len(items)})"})
        for a in items:
            parts.append({"type": "text", "text": f'`{a["id"]}` ({a["original_width"]:.0f}x{a["original_height"]:.0f}px):'})
            parts.append({"type": "image_url", "image_url": {"url": a["data_url"]}})

    parts.append({"type": "text", "text": f"\n### FONTS ({len(library.fonts)})\n{', '.join(library.fonts)}"})
    parts.append({"type": "text", "text": f"\n### COLORS ({len(library.colors)})\n{', '.join(library.colors)}"})
    parts.append({"type": "text", "text": "\nCompose a polished, professional layout for this design. Use `T` and `ASSETS`."})

    return parts


def make_blank_canvas(width: int, height: int, background: str = "#ffffff") -> dict:
    return {
        "id": "generated_layout",
        "width": float(width),
        "height": float(height),
        "background": background,
        "children": [],
    }


def execute_code(code: str, transformer: HumanToolLayoutTransformer, assets: dict) -> dict:
    """Execute LLM-generated code with T and ASSETS in scope."""
    exec(code, {"T": transformer, "ASSETS": assets})
    return transformer.layout


REFINE_PROMPT = """\
You generated the code below which produced the attached layout image.

## Previous Code
```python
{code}
```

## Previous Layout JSON (element summary)
{layout_summary}

## Rendered Result
(see attached image)

## Task
Improve this layout. Fix any issues: overlapping text, poor alignment, wasted space, missing assets, bad contrast, elements off-canvas.
Write a COMPLETE replacement Python code block (not a patch). Start fresh with `T` and `ASSETS`."""


def _layout_summary(layout: dict) -> str:
    lines = [f"Canvas: {layout['width']}x{layout['height']}, bg={layout.get('background')}"]
    for c in layout.get("children", []):
        t = c.get("type", "?")
        desc = f"  {c.get('id','?')}: {t} at ({c.get('x',0):.0f},{c.get('y',0):.0f}) {c.get('width',0):.0f}x{c.get('height',0):.0f}"
        if t == "text":
            desc += f" text=\"{c.get('text','')[:40]}\" font={c.get('fontFamily')} sz={c.get('fontSize')}"
        lines.append(desc)
    return "\n".join(lines)


def _render_layout(layout: dict) -> bytes | None:
    try:
        endpoint = ensure_renderer()
        renderer = ObelloRenderer(endpoint=endpoint)
        return renderer.render(layout)
    except Exception as e:
        print(f"Render failed: {e}")
        return None


def _build_refine_prompt(prev_code: str, layout: dict, render_png: bytes | None) -> list:
    parts: list = []
    parts.append({"type": "text", "text": REFINE_PROMPT.format(code=prev_code, layout_summary=_layout_summary(layout))})
    if render_png:
        import base64
        data_url = f"data:image/png;base64,{base64.b64encode(render_png).decode()}"
        parts.append({"type": "image_url", "image_url": {"url": data_url}})
    return parts


def run(
    brief: str,
    model: str = "gemini/gemini-3.1-flash-lite-preview",
    canvas_width: int = 1920,
    canvas_height: int = 1080,
    background: str = "#ffffff",
    output_dir: str | None = None,
    temperature: float = 0.7,
    iterations: int = 3,
):
    library = AssetLibrary()
    assets = {a["id"]: a["data_url"] for a in library.assets}
    user_prompt = build_user_prompt(brief, library, canvas_width, canvas_height)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(output_dir) if output_dir else Path(__file__).parent / "runs" / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    code = None
    layout = None
    render_png = None

    for i in range(iterations):
        print(f"\n{'='*60}\nIteration {i+1}/{iterations}\n{'='*60}")

        if i == 0:
            prompt = user_prompt
        else:
            prompt = _build_refine_prompt(code, layout, render_png)

        print(f"Calling {model}...")
        code = call_llm(
            model=model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=temperature,
            extract_code=True,
        )
        print(f"Generated code:\n{code}\n")

        canvas = make_blank_canvas(canvas_width, canvas_height, background)
        transformer = HumanToolLayoutTransformer(canvas)

        print("Executing code...")
        try:
            layout = execute_code(code, transformer, assets)
        except Exception:
            traceback.print_exc()
            print("\nFailed to execute generated code.")
            layout = canvas

        # Save iteration artifacts
        iter_dir = run_dir / f"iter_{i+1}"
        iter_dir.mkdir(exist_ok=True)
        (iter_dir / "code.py").write_text(code)
        (iter_dir / "layout.json").write_text(json.dumps(layout, indent=2))

        print("Rendering...")
        render_png = _render_layout(layout)
        if render_png:
            (iter_dir / "render.png").write_bytes(render_png)
            print(f"Saved to {iter_dir} ({len(render_png)} bytes)")
        else:
            print(f"Saved code and layout to {iter_dir} (no render)")

    # Copy final iteration to run root for easy access
    if render_png:
        (run_dir / "render.png").write_bytes(render_png)
    (run_dir / "code.py").write_text(code)
    (run_dir / "layout.json").write_text(json.dumps(layout, indent=2))
    print(f"\nFinal output: {run_dir}")


def main():
    parser = argparse.ArgumentParser(description="Minimal layout generation pipeline")
    parser.add_argument("brief", help="Design brief / prompt")
    parser.add_argument("--model", default="gemini/gemini-3.1-flash-lite-preview")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--background", default="#ffffff")
    parser.add_argument("--output", default=None, help="Output dir (default: runs/<timestamp>)")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--iterations", type=int, default=3, help="Number of refinement iterations (default: 3)")
    args = parser.parse_args()

    run(
        brief=args.brief,
        model=args.model,
        canvas_width=args.width,
        canvas_height=args.height,
        background=args.background,
        output_dir=args.output,
        temperature=args.temperature,
        iterations=args.iterations,
    )


if __name__ == "__main__":
    main()
