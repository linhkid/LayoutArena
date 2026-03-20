"""Writes per-run artifacts to a structured output directory."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

from layoutarena.env.canvas import LayoutArenaEnv
from layoutarena.experiments.run_eval import EpisodeSummary
from layoutarena.viz.replay import export_replay


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return str(value)


_METRICS_FIELDS = [
    "run_id",
    "protocol_name",
    "brief_id",
    "accepted",
    "quality_score",
    "tool_cost",
    "effective_yield",
    "safety_penalty",
    "suspicious_flagged",
    "attack",
    "seed",
    "threshold",
]


class RunOutputWriter:
    """Writes per-run artifacts to a structured output directory."""

    def __init__(self, base_dir: str | Path = "outputs"):
        self.base_dir = Path(base_dir)

    def reset_metrics_csv(self) -> Path:
        """Remove the existing metrics.csv so the next batch starts clean."""
        csv_path = self.base_dir / "metrics.csv"
        if csv_path.exists():
            csv_path.unlink()
        return csv_path

    def write_run(
        self,
        env: LayoutArenaEnv,
        summary: EpisodeSummary,
        run_id: str,
        extra_metadata: dict | None = None,
    ) -> Path:
        """Write all artifacts for one run.

        Output structure:
        outputs/runs/{run_id}/
            summary.json      - EpisodeSummary as JSON
            replay/            - SVG snapshots + replay.json manifest
            metadata.json      - extra info (seed, attack, threshold, etc.)
        """
        run_dir = self.base_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # summary.json
        (run_dir / "summary.json").write_text(
            json.dumps(asdict(summary), indent=2, default=_json_default),
            encoding="utf-8",
        )

        # replay/
        export_replay(env.state, run_dir / "replay")

        # metadata.json
        metadata = extra_metadata or {}
        metadata["run_id"] = run_id
        (run_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2, default=_json_default),
            encoding="utf-8",
        )

        return run_dir

    def append_to_metrics_csv(
        self,
        summary: EpisodeSummary,
        run_id: str,
        extra: dict | None = None,
    ) -> Path:
        """Append one row to outputs/metrics.csv with all summary fields + extras."""
        csv_path = self.base_dir / "metrics.csv"
        self.base_dir.mkdir(parents=True, exist_ok=True)

        write_header = not csv_path.exists()

        row: dict[str, Any] = {"run_id": run_id}
        row.update(asdict(summary))
        if extra:
            row.update(extra)

        with csv_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=_METRICS_FIELDS,
                extrasaction="ignore",
            )
            if write_header:
                writer.writeheader()
            writer.writerow(row)

        return csv_path
