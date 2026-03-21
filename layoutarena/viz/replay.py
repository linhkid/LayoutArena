from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from layoutarena.env.models import LayoutState
from layoutarena.viz.render_canvas import write_snapshot_svg


def export_replay(state: LayoutState, output_dir: str | Path) -> Path:
    """Write one SVG per snapshot, a JSON manifest, and an HTML step viewer.

    The HTML viewer (``index.html``) provides step-by-step navigation through
    the full episode without requiring any external tooling — open it directly
    in a browser for the demo.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    svg_filenames: list[str] = []
    for snapshot in state.snapshots:
        filename = (
            f"{snapshot.step_index:03d}_{snapshot.tool_name}_{snapshot.status}.svg"
        )
        write_snapshot_svg(snapshot, output / filename)
        svg_filenames.append(filename)

    manifest = {
        "brief_id": state.brief.brief_id,
        "tool_history": [asdict(record) for record in state.tool_history],
        "snapshots": [asdict(snapshot) for snapshot in state.snapshots],
        "risk_score": state.risk_score,
        "flagged_suspicious": state.flagged_suspicious,
        "blocked_regions": state.blocked_regions,
    }
    (output / "replay.json").write_text(
        json.dumps(manifest, indent=2, default=_json_default),
        encoding="utf-8",
    )

    if svg_filenames:
        _write_html_viewer(
            output_dir=output,
            svg_filenames=svg_filenames,
            state=state,
        )

    return output


def _write_html_viewer(
    output_dir: Path,
    svg_filenames: list[str],
    state: LayoutState,
) -> None:
    """Generate a self-contained HTML file for browsing the replay step by step.

    The viewer embeds step metadata (tool name, status, risk score, monitor
    reasons) alongside the SVG so judges can follow the episode without
    needing additional tooling.

    Design goals:
    - No external dependencies (pure HTML + inline CSS + vanilla JS).
    - Works when opened from the local filesystem (file:// URLs).
    - Easy to extend: add new metadata fields by updating ``_step_meta``.
    """
    steps = _build_step_metadata(state, svg_filenames)
    steps_json = json.dumps(steps, indent=2)
    brief_title = escape(state.brief.title)
    brief_id = escape(state.brief.brief_id)
    final_risk = f"{state.risk_score:.3f}"
    flagged = "Yes ⚠" if state.flagged_suspicious else "No"

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LayoutArena Replay — {brief_title}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: Helvetica, Arial, sans-serif; background: #f0ede6; color: #1c1c1c; }}
    header {{ background: #1c1c1c; color: #fff; padding: 16px 24px; display: flex; align-items: baseline; gap: 16px; }}
    header h1 {{ font-size: 18px; font-weight: 700; }}
    header span {{ font-size: 13px; opacity: 0.6; }}
    .summary-bar {{ background: #fff; border-bottom: 1px solid #ddd; padding: 8px 24px;
                    display: flex; gap: 24px; font-size: 13px; color: #555; }}
    .summary-bar strong {{ color: #1c1c1c; }}
    .layout {{ display: flex; height: calc(100vh - 96px); overflow: hidden; }}
    .sidebar {{ width: 220px; min-width: 180px; background: #fff; border-right: 1px solid #ddd;
                overflow-y: auto; padding: 8px 0; flex-shrink: 0; }}
    .step-btn {{ display: block; width: 100%; text-align: left; padding: 8px 14px; border: none;
                 background: none; cursor: pointer; font-size: 12px; border-left: 3px solid transparent;
                 line-height: 1.4; transition: background 0.1s; }}
    .step-btn:hover {{ background: #f5f0e8; }}
    .step-btn.active {{ background: #f5f0e8; border-left-color: #1c1c1c; font-weight: 700; }}
    .step-btn.blocked {{ border-left-color: #e74c3c; }}
    .step-btn.failed  {{ border-left-color: #f39c12; }}
    .step-label {{ font-weight: 600; }}
    .step-status {{ display: inline-block; font-size: 10px; padding: 1px 5px; border-radius: 3px;
                    margin-left: 4px; font-weight: 700; letter-spacing: 0.03em; }}
    .status-ok      {{ background: #d5f0dc; color: #1a6630; }}
    .status-blocked {{ background: #fde8e8; color: #7b1c1c; }}
    .status-failed  {{ background: #fef3e2; color: #7a4200; }}
    .main {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
    .canvas-area {{ flex: 1; overflow: auto; display: flex; align-items: flex-start;
                    justify-content: center; padding: 16px; background: #e8e4dc; }}
    .canvas-area img {{ max-width: 100%; box-shadow: 0 2px 16px rgba(0,0,0,0.15); border-radius: 4px; }}
    .meta-panel {{ height: 140px; min-height: 120px; background: #fff; border-top: 1px solid #ddd;
                   padding: 12px 20px; overflow-y: auto; font-size: 13px; display: flex; gap: 32px; }}
    .meta-col h3 {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em;
                    color: #888; margin-bottom: 6px; }}
    .meta-col p  {{ margin: 2px 0; }}
    .reasons {{ font-size: 12px; color: #c0392b; }}
    .nav-bar {{ background: #1c1c1c; padding: 8px 16px; display: flex; align-items: center; gap: 12px; }}
    .nav-bar button {{ background: #fff; color: #1c1c1c; border: none; padding: 6px 16px;
                       border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 600; }}
    .nav-bar button:disabled {{ opacity: 0.35; cursor: default; }}
    .nav-bar .counter {{ color: #aaa; font-size: 12px; flex: 1; text-align: center; }}
  </style>
</head>
<body>
  <header>
    <h1>LayoutArena Replay</h1>
    <span>{brief_title} ({brief_id})</span>
  </header>
  <div class="summary-bar">
    <span>Total steps: <strong id="total-steps">—</strong></span>
    <span>Final risk score: <strong>{final_risk}</strong></span>
    <span>Flagged suspicious: <strong>{flagged}</strong></span>
  </div>
  <div class="layout">
    <nav class="sidebar" id="sidebar"></nav>
    <div class="main">
      <div class="canvas-area">
        <img id="canvas-img" src="" alt="Canvas snapshot">
      </div>
      <div class="nav-bar">
        <button id="btn-prev" onclick="navigate(-1)">&#8592; Prev</button>
        <span class="counter" id="step-counter"></span>
        <button id="btn-next" onclick="navigate(1)">Next &#8594;</button>
      </div>
      <div class="meta-panel">
        <div class="meta-col">
          <h3>Step info</h3>
          <p>Tool: <strong id="meta-tool">—</strong></p>
          <p>Status: <strong id="meta-status">—</strong></p>
          <p>Risk score: <strong id="meta-risk">—</strong></p>
          <p>Cost: <strong id="meta-cost">—</strong></p>
        </div>
        <div class="meta-col">
          <h3>Message</h3>
          <p id="meta-message">—</p>
        </div>
        <div class="meta-col" style="flex:1">
          <h3>Monitor reasons</h3>
          <p class="reasons" id="meta-reasons">—</p>
        </div>
      </div>
    </div>
  </div>

  <script>
    const STEPS = {steps_json};
    let current = 0;

    document.getElementById('total-steps').textContent = STEPS.length;

    const sidebar = document.getElementById('sidebar');
    STEPS.forEach((step, i) => {{
      const btn = document.createElement('button');
      btn.className = 'step-btn ' + (step.status === 'blocked' ? 'blocked' : step.status === 'failed' ? 'failed' : '');
      btn.id = 'step-btn-' + i;
      const badge = `<span class="step-status status-${{step.status}}">${{step.status}}</span>`;
      btn.innerHTML = `<span class="step-label">${{i + 1}}. ${{step.tool_name}}</span>${{badge}}`;
      btn.onclick = () => goTo(i);
      sidebar.appendChild(btn);
    }});

    function goTo(index) {{
      if (index < 0 || index >= STEPS.length) return;
      document.querySelectorAll('.step-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('step-btn-' + index).classList.add('active');

      const step = STEPS[index];
      current = index;

      document.getElementById('canvas-img').src = step.svg_file;
      document.getElementById('meta-tool').textContent = step.tool_name;
      document.getElementById('meta-status').textContent = step.status;
      document.getElementById('meta-risk').textContent = step.risk_score.toFixed(3);
      document.getElementById('meta-cost').textContent = step.cost;
      document.getElementById('meta-message').textContent = step.message || '—';
      document.getElementById('meta-reasons').textContent =
        step.monitor_reasons.length ? step.monitor_reasons.join(' · ') : '—';
      document.getElementById('step-counter').textContent =
        (index + 1) + ' / ' + STEPS.length;
      document.getElementById('btn-prev').disabled = index === 0;
      document.getElementById('btn-next').disabled = index === STEPS.length - 1;

      // Scroll sidebar button into view
      document.getElementById('step-btn-' + index).scrollIntoView({{block: 'nearest'}});
    }}

    function navigate(delta) {{ goTo(current + delta); }}

    // Keyboard navigation
    document.addEventListener('keydown', e => {{
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') navigate(1);
      if (e.key === 'ArrowLeft'  || e.key === 'ArrowUp')   navigate(-1);
    }});

    goTo(0);
  </script>
</body>
</html>
"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")


def _build_step_metadata(
    state: LayoutState,
    svg_filenames: list[str],
) -> list[dict[str, Any]]:
    """Build a list of per-step metadata dicts for the HTML viewer."""
    history_by_step: dict[int, Any] = {
        rec.step_index: rec for rec in state.tool_history
    }
    steps: list[dict[str, Any]] = []
    for filename, snapshot in zip(svg_filenames, state.snapshots):
        record = history_by_step.get(snapshot.step_index)
        steps.append(
            {
                "svg_file": filename,
                "step_index": snapshot.step_index,
                "tool_name": snapshot.tool_name,
                "status": snapshot.status,
                "message": snapshot.message,
                "risk_score": snapshot.risk_score,
                "cost": record.cost if record is not None else 0,
                "monitor_reasons": record.monitor_reasons if record is not None else [],
            },
        )
    return steps


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    return str(value)
