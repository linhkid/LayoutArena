from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from layoutarena.env.models import LayoutState
from layoutarena.viz.render_canvas import write_snapshot_svg


def export_replay(state: LayoutState, output_dir: str | Path) -> Path:
    """
    Writes one SVG per snapshot plus a JSON manifest.

    This is enough for the hackathon demo. If needed later, a notebook or shell
    script can stitch the SVGs into a GIF or MP4.
    """

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    for snapshot in state.snapshots:
        filename = (
            f"{snapshot.step_index:03d}_{snapshot.tool_name}_{snapshot.status}.svg"
        )
        write_snapshot_svg(snapshot, output / filename)

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
    return output


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    return str(value)
