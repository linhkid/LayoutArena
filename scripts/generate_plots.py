#!/usr/bin/env python3
"""Read outputs/metrics.csv and generate all figures to outputs/figures/.

Usage
-----
    python scripts/generate_plots.py                       # defaults
    python scripts/generate_plots.py --csv path/to/csv     # custom input
    python scripts/generate_plots.py --out-dir path/to/dir # custom output

The CSV is expected to have columns matching ``EpisodeSummary`` fields:
    protocol_name, brief_id, accepted, quality_score, tool_cost,
    effective_yield, safety_penalty, suspicious_flagged,
    monitor_detected, monitor_block_count, monitor_nudge_count

Plus ``attack`` (attack family) and ``threshold`` (stewardship threshold).
Older CSVs without the two count columns default those values to zero.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

# Ensure the project root is importable when running the script directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dataclasses import dataclass  # noqa: E402


@dataclass
class _Summary:
    """Lightweight stand-in that mirrors EpisodeSummary fields."""

    protocol_name: str
    brief_id: str
    accepted: bool
    quality_score: float
    tool_cost: int
    effective_yield: float
    safety_penalty: float
    suspicious_flagged: bool
    attack_family: str = "unknown"
    monitor_detected: bool = False
    monitor_block_count: float = 0.0
    monitor_nudge_count: float = 0.0
    threshold: float | None = None
    seed: int | None = None


def _load_csv(path: Path) -> list[_Summary]:
    summaries: list[_Summary] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            raw_threshold = row.get("threshold", "")
            threshold: float | None = None
            if raw_threshold and raw_threshold.lower() not in ("", "none"):
                try:
                    threshold = float(raw_threshold)
                except ValueError:
                    pass

            raw_seed = row.get("seed", "")
            seed: int | None = None
            if raw_seed and raw_seed.lower() not in ("", "none"):
                try:
                    seed = int(float(raw_seed))
                except ValueError:
                    pass

            def _float_col(key: str, default: float = 0.0) -> float:
                raw = row.get(key, "")
                if raw is None or str(raw).strip() == "":
                    return default
                try:
                    return float(raw)
                except ValueError:
                    return default

            summaries.append(
                _Summary(
                    protocol_name=row["protocol_name"],
                    brief_id=row.get("brief_id", ""),
                    accepted=row.get("accepted", "true").lower()
                    in ("true", "1", "yes"),
                    quality_score=float(row.get("quality_score", 0)),
                    tool_cost=int(float(row.get("tool_cost", 0))),
                    effective_yield=float(row.get("effective_yield", 0)),
                    safety_penalty=float(row.get("safety_penalty", 0)),
                    suspicious_flagged=row.get("suspicious_flagged", "false").lower()
                    in ("true", "1", "yes"),
                    attack_family=row.get("attack_family", "")
                    or row.get("attack", "unknown"),
                    monitor_detected=row.get("monitor_detected", "false").lower()
                    in ("true", "1", "yes"),
                    monitor_block_count=_float_col("monitor_block_count"),
                    monitor_nudge_count=_float_col("monitor_nudge_count"),
                    threshold=threshold,
                    seed=seed,
                ),
            )
    return summaries


# ---------------------------------------------------------------------------
# Threshold sweep: group stewardship rows by actual threshold value
# ---------------------------------------------------------------------------


def _build_threshold_sweep(summaries: list[_Summary]) -> list:
    """Build sweep results from CSV rows using real threshold values.

    Each point includes a ``detection_rate`` (fraction of runs where the
    monitor detected something) alongside the averaged summary.
    """
    stewardship = [
        s
        for s in summaries
        if s.protocol_name == "stewardship_monitoring" and s.threshold is not None
    ]
    if not stewardship:
        return []

    # Group by threshold and average
    by_threshold: dict[float, list[_Summary]] = defaultdict(list)
    for s in stewardship:
        by_threshold[s.threshold].append(s)

    @dataclass
    class _SweepPoint:
        threshold: float
        detection_rate: float
        summary: _Summary  # averaged pseudo-summary

    points: list[_SweepPoint] = []
    for t, sums in sorted(by_threshold.items()):
        n = len(sums)
        det_rate = sum(s.monitor_detected for s in sums) / n
        avg = _Summary(
            protocol_name="stewardship_monitoring",
            brief_id="averaged",
            accepted=any(s.accepted for s in sums),
            quality_score=sum(s.quality_score for s in sums) / n,
            tool_cost=int(sum(s.tool_cost for s in sums) / n),
            effective_yield=sum(s.effective_yield for s in sums) / n,
            safety_penalty=sum(s.safety_penalty for s in sums) / n,
            suspicious_flagged=any(s.suspicious_flagged for s in sums),
            monitor_detected=det_rate > 0,
            monitor_block_count=sum(s.monitor_block_count for s in sums) / n,
            monitor_nudge_count=sum(s.monitor_nudge_count for s in sums) / n,
            threshold=t,
        )
        points.append(_SweepPoint(threshold=t, detection_rate=det_rate, summary=avg))

    return points


# ---------------------------------------------------------------------------
# Diversity: re-run episodes to collect actual LayoutState objects
# ---------------------------------------------------------------------------


def _compute_real_diversity() -> dict[str, "DiversityReport"]:  # noqa: F821
    """Run episodes per protocol+attack=none and compute diversity from
    actual final layout states.  Only accepted runs are included so that
    rejected bounded-control runs (with fewer elements) do not pollute
    the metric."""
    from layoutarena.env.models import CanvasSpec
    from layoutarena.experiments.batch_runner import build_episode_actions
    from layoutarena.experiments.briefs import hero_briefs
    from layoutarena.experiments.diversity import DiversityReport, compute_diversity
    from layoutarena.experiments.run_eval import (
        run_scripted_episode,
    )

    canvas = CanvasSpec()
    briefs = hero_briefs()
    seeds = list(range(10))
    protocols = ["enforcement", "bounded_control", "stewardship_monitoring"]

    diversity_by_proto: dict[str, DiversityReport] = {}

    for proto in protocols:
        states = []
        for brief in briefs:
            for seed in seeds:
                actions = build_episode_actions(canvas, brief, attack=None, seed=seed)
                try:
                    env, summary = run_scripted_episode(
                        brief=brief,
                        protocol_name=proto,
                        actions=actions,
                        canvas=canvas,
                        stewardship_threshold=0.7,
                    )
                    if summary.accepted:
                        states.append(env.state)
                except Exception:
                    continue

        if len(states) >= 2:
            diversity_by_proto[proto] = compute_diversity(states)

    return diversity_by_proto


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate LayoutArena figures.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "metrics.csv",
        help="Path to the metrics CSV file.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "figures",
        help="Directory to write figures into.",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: metrics CSV not found at {args.csv}", file=sys.stderr)
        print("Run experiments first, or pass --csv <path>.", file=sys.stderr)
        sys.exit(1)

    summaries = _load_csv(args.csv)
    if not summaries:
        print("ERROR: CSV contained no rows.", file=sys.stderr)
        sys.exit(1)

    out: Path = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    from layoutarena.viz.plots import (  # noqa: E402
        plot_attack_detection_rates,
        plot_diversity_comparison,
        plot_pareto_frontier,
        plot_safety_usefulness_table,
        plot_threshold_sweep,
        plot_tool_cost_distribution,
        summaries_to_pareto_points,
    )

    # 1. Pareto frontier — split stewardship by threshold so each shows
    #    as a separate point on the frontier.
    pareto_summaries = []
    for s in summaries:
        if s.protocol_name == "stewardship_monitoring" and s.threshold is not None:
            # Create a copy with a threshold-specific protocol name
            tagged = _Summary(
                protocol_name=f"stewardship (t={s.threshold})",
                brief_id=s.brief_id,
                accepted=s.accepted,
                quality_score=s.quality_score,
                tool_cost=s.tool_cost,
                effective_yield=s.effective_yield,
                safety_penalty=s.safety_penalty,
                suspicious_flagged=s.suspicious_flagged,
                monitor_detected=s.monitor_detected,
                monitor_block_count=s.monitor_block_count,
                monitor_nudge_count=s.monitor_nudge_count,
                threshold=s.threshold,
                seed=s.seed,
            )
            pareto_summaries.append(tagged)
        else:
            pareto_summaries.append(s)

    # Y-axis = protocol detection rate (monitor_detected), which is the
    # protocol-level safety proxy used in the current paper figures.
    # X-axis = quality_score * effective_yield (layout quality x efficiency).
    def _safety(s):
        return 100.0 * float(getattr(s, "monitor_detected", False))

    pareto_pts = summaries_to_pareto_points(
        pareto_summaries,
        safety_fn=_safety,
    )
    result = plot_pareto_frontier(pareto_pts, out / "pareto_frontier.png")
    if result:
        print(f"  [OK] {result}")

    # 2. Tool cost distribution
    result = plot_tool_cost_distribution(summaries, out / "tool_cost_distribution.png")
    if result:
        print(f"  [OK] {result}")

    # 3. Attack detection rates (group by attack_family)
    by_attack: dict[str, list[_Summary]] = defaultdict(list)
    for s in summaries:
        by_attack[s.attack_family].append(s)
    result = plot_attack_detection_rates(by_attack, out / "attack_detection_rates.png")
    if result:
        print(f"  [OK] {result}")

    # 4. Summary table
    result = plot_safety_usefulness_table(summaries, out / "summary_table.png")
    if result:
        print(f"  [OK] {result}")

    # 5. Threshold sweep — uses actual threshold column from CSV
    sweep = _build_threshold_sweep(summaries)
    if len(sweep) >= 2:
        result = plot_threshold_sweep(sweep, out / "threshold_sweep.png")
        if result:
            print(f"  [OK] {result}")
    else:
        print("  [SKIP] threshold_sweep: need >= 2 distinct thresholds in CSV")

    # 6. Diversity comparison — re-runs episodes to measure real layout diversity
    print("  Computing layout diversity from actual episodes...")
    diversity_by_proto = _compute_real_diversity()
    if diversity_by_proto:
        result = plot_diversity_comparison(
            diversity_by_proto,
            out / "diversity_comparison.png",
        )
        if result:
            print(f"  [OK] {result}")
    else:
        print("  [SKIP] diversity_comparison: insufficient data")

    print("Done.")


if __name__ == "__main__":
    main()
