from __future__ import annotations

from dataclasses import dataclass

from layoutarena.env.models import CanvasSpec, LayoutBrief, ProposedAction
from layoutarena.experiments.run_eval import EpisodeSummary, run_scripted_episode


@dataclass
class ThresholdSweepResult:
    threshold: float
    summary: EpisodeSummary


def sweep_stewardship_thresholds(
    *,
    brief: LayoutBrief,
    thresholds: list[float],
    actions: list[ProposedAction],
    canvas: CanvasSpec | None = None,
) -> list[ThresholdSweepResult]:
    results: list[ThresholdSweepResult] = []
    for threshold in thresholds:
        _, summary = run_scripted_episode(
            brief=brief,
            protocol_name="stewardship_monitoring",
            actions=actions,
            canvas=canvas,
            stewardship_threshold=threshold,
        )
        results.append(ThresholdSweepResult(threshold=threshold, summary=summary))
    return results
