"""Unit tests for episode summary helpers."""

from __future__ import annotations

from layoutarena.env.models import CanvasSpec, LayoutBrief, LayoutState, ToolCallRecord
from layoutarena.experiments.run_eval import compute_monitor_metrics


def _record(
    *,
    status: str,
    reasons: list[str] | None = None,
) -> ToolCallRecord:
    return ToolCallRecord(
        step_index=1,
        tool_name="place_element",
        parameters={},
        status=status,
        cost=1,
        succeeded=status == "applied",
        monitor_reasons=list(reasons or []),
    )


def test_compute_monitor_metrics_empty_history():
    state = LayoutState(
        brief=LayoutBrief(brief_id="t", title="T", instructions=""),
        canvas=CanvasSpec(),
        tool_history=[],
    )
    det, blocks, nudges = compute_monitor_metrics(state)
    assert det is False and blocks == 0 and nudges == 0


def test_compute_monitor_metrics_block_counts_not_nudge():
    state = LayoutState(
        brief=LayoutBrief(brief_id="t", title="T", instructions=""),
        canvas=CanvasSpec(),
        tool_history=[
            _record(status="blocked", reasons=["policy"]),
        ],
    )
    det, blocks, nudges = compute_monitor_metrics(state)
    assert det is True and blocks == 1 and nudges == 0


def test_compute_monitor_metrics_nudge_without_block():
    state = LayoutState(
        brief=LayoutBrief(brief_id="t", title="T", instructions=""),
        canvas=CanvasSpec(),
        tool_history=[
            _record(status="applied", reasons=["redirect note"]),
        ],
    )
    det, blocks, nudges = compute_monitor_metrics(state)
    assert det is True and blocks == 0 and nudges == 1


def test_compute_monitor_metrics_applied_without_reasons_is_clean():
    state = LayoutState(
        brief=LayoutBrief(brief_id="t", title="T", instructions=""),
        canvas=CanvasSpec(),
        tool_history=[
            _record(status="applied", reasons=[]),
        ],
    )
    det, blocks, nudges = compute_monitor_metrics(state)
    assert det is False and blocks == 0 and nudges == 0
