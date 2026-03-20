from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParetoPoint:
    protocol_name: str
    safety: float
    usefulness: float
    threshold: float | None = None


def pareto_frontier(points: list[ParetoPoint]) -> list[ParetoPoint]:
    """
    Returns non-dominated points when maximizing both safety and usefulness.
    """

    sorted_points = sorted(points, key=lambda point: (-point.usefulness, -point.safety))
    frontier: list[ParetoPoint] = []
    best_safety = float("-inf")
    for point in sorted_points:
        if point.safety > best_safety:
            frontier.append(point)
            best_safety = point.safety
    return sorted(frontier, key=lambda point: (point.usefulness, point.safety))


def write_points_csv(points: list[ParetoPoint], output_path: str | Path) -> Path:
    target = Path(output_path)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["protocol_name", "safety", "usefulness", "threshold"],
        )
        writer.writeheader()
        for point in points:
            writer.writerow(
                {
                    "protocol_name": point.protocol_name,
                    "safety": point.safety,
                    "usefulness": point.usefulness,
                    "threshold": point.threshold,
                },
            )
    return target
