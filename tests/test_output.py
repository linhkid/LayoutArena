"""Tests for output writer, replay export, and HTML viewer."""
from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import pytest

from layoutarena.experiments.briefs import hero_briefs
from layoutarena.experiments.output_writer import RunOutputWriter
from layoutarena.experiments.run_eval import run_scripted_episode
from layoutarena.viz.replay import export_replay


def _run_nominal():
    brief = hero_briefs()[0]
    return run_scripted_episode(brief=brief, protocol_name="enforcement")


# ---------------------------------------------------------------------------
# RunOutputWriter
# ---------------------------------------------------------------------------

class TestRunOutputWriter:
    def test_write_run_creates_directory_structure(self):
        env, summary = _run_nominal()
        with tempfile.TemporaryDirectory() as tmp:
            writer = RunOutputWriter(tmp)
            run_dir = writer.write_run(env, summary, "test_run_001")
            assert (run_dir / "summary.json").exists()
            assert (run_dir / "metadata.json").exists()
            assert (run_dir / "replay").is_dir()

    def test_summary_json_has_expected_fields(self):
        env, summary = _run_nominal()
        with tempfile.TemporaryDirectory() as tmp:
            writer = RunOutputWriter(tmp)
            run_dir = writer.write_run(env, summary, "test_run_002")
            data = json.loads((run_dir / "summary.json").read_text())
            for field in (
                "protocol_name",
                "brief_id",
                "accepted",
                "quality_score",
                "tool_cost",
                "effective_yield",
                "monitor_detected",
                "monitor_block_count",
                "monitor_nudge_count",
            ):
                assert field in data

    def test_metadata_json_includes_extra_fields(self):
        env, summary = _run_nominal()
        with tempfile.TemporaryDirectory() as tmp:
            writer = RunOutputWriter(tmp)
            extra = {"attack": "none", "seed": 7, "threshold": 0.9}
            run_dir = writer.write_run(env, summary, "run_003", extra_metadata=extra)
            data = json.loads((run_dir / "metadata.json").read_text())
            assert data["attack"] == "none"
            assert data["seed"] == 7

    def test_metrics_csv_written_and_appendable(self):
        env, summary = _run_nominal()
        with tempfile.TemporaryDirectory() as tmp:
            writer = RunOutputWriter(tmp)
            extra = {"attack": "none", "seed": 0, "threshold": None}
            writer.append_to_metrics_csv(summary, "run_a", extra=extra)
            writer.append_to_metrics_csv(summary, "run_b", extra=extra)
            csv_path = Path(tmp) / "metrics.csv"
            assert csv_path.exists()
            rows = list(csv.DictReader(csv_path.open()))
            assert len(rows) == 2
            assert rows[0]["run_id"] == "run_a"
            assert rows[1]["run_id"] == "run_b"
            assert "monitor_block_count" in rows[0]
            assert "monitor_nudge_count" in rows[0]

    def test_reset_metrics_csv_removes_existing(self):
        env, summary = _run_nominal()
        with tempfile.TemporaryDirectory() as tmp:
            writer = RunOutputWriter(tmp)
            extra = {"attack": "none", "seed": 0, "threshold": None}
            writer.append_to_metrics_csv(summary, "run_a", extra=extra)
            writer.reset_metrics_csv()
            assert not (Path(tmp) / "metrics.csv").exists()


# ---------------------------------------------------------------------------
# Replay export
# ---------------------------------------------------------------------------

class TestReplayExport:
    def test_svg_files_created_for_each_snapshot(self):
        env, _ = _run_nominal()
        with tempfile.TemporaryDirectory() as tmp:
            out = export_replay(env.state, tmp)
            svgs = list(Path(tmp).glob("*.svg"))
            assert len(svgs) == len(env.state.snapshots)

    def test_replay_json_manifest_created(self):
        env, _ = _run_nominal()
        with tempfile.TemporaryDirectory() as tmp:
            export_replay(env.state, tmp)
            manifest = json.loads((Path(tmp) / "replay.json").read_text())
            assert "brief_id" in manifest
            assert "tool_history" in manifest
            assert "snapshots" in manifest

    def test_html_viewer_created(self):
        env, _ = _run_nominal()
        with tempfile.TemporaryDirectory() as tmp:
            export_replay(env.state, tmp)
            html_path = Path(tmp) / "index.html"
            assert html_path.exists()

    def test_html_viewer_contains_steps_json(self):
        env, _ = _run_nominal()
        with tempfile.TemporaryDirectory() as tmp:
            export_replay(env.state, tmp)
            html = (Path(tmp) / "index.html").read_text()
            assert "const STEPS" in html

    def test_html_viewer_has_navigation(self):
        env, _ = _run_nominal()
        with tempfile.TemporaryDirectory() as tmp:
            export_replay(env.state, tmp)
            html = (Path(tmp) / "index.html").read_text()
            assert "btn-prev" in html
            assert "btn-next" in html
            assert "ArrowRight" in html


# ---------------------------------------------------------------------------
# SVG color coding
# ---------------------------------------------------------------------------

class TestSVGColorCoding:
    def _get_snapshots_by_status(self, env):
        from layoutarena.viz.render_canvas import render_snapshot_svg
        return {
            snap.status: render_snapshot_svg(snap)
            for snap in env.state.snapshots
        }

    def test_blocked_snapshot_has_red_header(self):
        from layoutarena.attacks.hidden_content import HiddenContentAttack
        from layoutarena.experiments.batch_runner import build_episode_actions
        from layoutarena.env.models import CanvasSpec
        canvas = CanvasSpec()
        brief = hero_briefs()[0]
        actions = build_episode_actions(canvas, brief, HiddenContentAttack())
        env, _ = run_scripted_episode(
            brief=brief, protocol_name="stewardship_monitoring",
            actions=actions, canvas=canvas, stewardship_threshold=0.5,
        )
        svgs = self._get_snapshots_by_status(env)
        if "blocked" in svgs:
            assert "#fde8e8" in svgs["blocked"] or "#e74c3c" in svgs["blocked"]

    def test_accepted_snapshot_has_green_header(self):
        env, _ = _run_nominal()
        svgs = self._get_snapshots_by_status(env)
        if "accepted" in svgs:
            assert "#e8f8ed" in svgs["accepted"] or "#27ae60" in svgs["accepted"]

    def test_applied_snapshot_is_neutral(self):
        env, _ = _run_nominal()
        svgs = self._get_snapshots_by_status(env)
        if "applied" in svgs:
            # Should NOT have red or orange emergency colors
            assert "#fde8e8" not in svgs["applied"]
            assert "#fef3e2" not in svgs["applied"]
