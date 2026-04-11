#!/usr/bin/env python3
"""Generate Plan A (LLM) and Plan B (ablation) figures.

Usage
-----
    python scripts/generate_new_plots.py                          # all defaults
    python scripts/generate_new_plots.py --llm-csv outputs/llm/metrics.csv
    python scripts/generate_new_plots.py --ablation-json outputs/ablation/summary.json
    python scripts/generate_new_plots.py --out-dir outputs/figures
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class _Summary:
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

            def _f(k, d=0.0):
                v = row.get(k, "")
                return float(v) if v and v.strip() else d

            summaries.append(_Summary(
                protocol_name=row.get("protocol_name", ""),
                brief_id=row.get("brief_id", ""),
                accepted=row.get("accepted", "true").lower() in ("true", "1", "yes"),
                quality_score=_f("quality_score"),
                tool_cost=int(_f("tool_cost")),
                effective_yield=_f("effective_yield"),
                safety_penalty=_f("safety_penalty"),
                suspicious_flagged=row.get("suspicious_flagged", "false").lower() in ("true", "1", "yes"),
                attack_family=row.get("attack_family", "") or row.get("attack", "unknown"),
                monitor_detected=row.get("monitor_detected", "false").lower() in ("true", "1", "yes"),
                monitor_block_count=_f("monitor_block_count"),
                monitor_nudge_count=_f("monitor_nudge_count"),
                threshold=threshold,
                seed=seed,
            ))
    return summaries


@dataclass
class _SweepPoint:
    threshold: float
    detection_rate: float
    fpr: float  # false positive rate on clean (attack=none) runs
    summary: _Summary


def _build_sweep(summaries: list[_Summary]) -> list[_SweepPoint]:
    """Build sweep with both TPR (attack detection) and FPR (clean-run block)."""
    steward = [s for s in summaries if s.protocol_name == "stewardship_monitoring" and s.threshold is not None]
    if not steward:
        return []

    by_t: dict[float, list[_Summary]] = defaultdict(list)
    for s in steward:
        by_t[s.threshold].append(s)

    points: list[_SweepPoint] = []
    for t, sums in sorted(by_t.items()):
        # TPR: detection rate on attack runs only
        attack_runs = [s for s in sums if s.attack_family not in ("none", "unknown", "")]
        clean_runs = [s for s in sums if s.attack_family in ("none", "")]
        tpr = sum(s.monitor_detected for s in attack_runs) / max(len(attack_runs), 1)
        # FPR: fraction of clean runs where monitor triggered (false alarm)
        fpr = sum(s.monitor_detected for s in clean_runs) / max(len(clean_runs), 1)
        n = len(sums)
        avg = _Summary(
            protocol_name="stewardship_monitoring",
            brief_id="averaged",
            accepted=any(s.accepted for s in sums),
            quality_score=sum(s.quality_score for s in sums) / n,
            tool_cost=int(sum(s.tool_cost for s in sums) / n),
            effective_yield=sum(s.effective_yield for s in sums) / n,
            safety_penalty=sum(s.safety_penalty for s in sums) / n,
            suspicious_flagged=any(s.suspicious_flagged for s in sums),
            monitor_detected=tpr > 0,
            threshold=t,
        )
        points.append(_SweepPoint(threshold=t, detection_rate=tpr, fpr=fpr, summary=avg))
    return points


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate Plan A and Plan B figures.")
    parser.add_argument("--llm-csv", type=Path, default=PROJECT_ROOT / "outputs" / "llm" / "metrics.csv")
    parser.add_argument("--scripted-csv", type=Path, default=PROJECT_ROOT / "outputs" / "metrics.csv")
    parser.add_argument("--ablation-json", type=Path, default=PROJECT_ROOT / "outputs" / "ablation" / "summary.json")
    parser.add_argument("--ablation-csv", type=Path, default=PROJECT_ROOT / "outputs" / "ablation" / "metrics.csv")
    parser.add_argument("--out-dir", type=Path, default=PROJECT_ROOT / "outputs" / "figures")
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    from layoutarena.viz.plots import (
        plot_ablation_bar_chart,
        plot_ablation_heatmap,
        plot_llm_false_positive_curve,
        plot_llm_threshold_curve,
        plot_llm_vs_scripted_table,
    )

    # -----------------------------------------------------------------------
    # Plan A: LLM experiments
    # -----------------------------------------------------------------------
    llm_summaries: list[_Summary] = []
    if args.llm_csv.exists():
        llm_summaries = _load_csv(args.llm_csv)
        print(f"Loaded {len(llm_summaries)} LLM rows from {args.llm_csv}")
    else:
        print(f"[SKIP] LLM CSV not found: {args.llm_csv}")

    scripted_summaries: list[_Summary] = []
    if args.scripted_csv.exists():
        scripted_summaries = _load_csv(args.scripted_csv)
        print(f"Loaded {len(scripted_summaries)} scripted rows from {args.scripted_csv}")

    if llm_summaries:
        llm_sweep = _build_sweep(llm_summaries)
        scripted_sweep = _build_sweep(scripted_summaries) if scripted_summaries else None

        if len(llm_sweep) >= 2:
            r = plot_llm_threshold_curve(llm_sweep, scripted_sweep,
                                          args.out_dir / "llm_threshold_curve.png")
            print(f"  [OK] {r}")

            r = plot_llm_false_positive_curve(llm_sweep, scripted_sweep,
                                               args.out_dir / "llm_roc_curve.png")
            print(f"  [OK] {r}")
        else:
            print(f"  [SKIP] threshold curve: only {len(llm_sweep)} threshold points in LLM data")

        if scripted_summaries:
            r = plot_llm_vs_scripted_table(llm_summaries, scripted_summaries,
                                            args.out_dir / "llm_vs_scripted_table.png")
            print(f"  [OK] {r}")

    # -----------------------------------------------------------------------
    # Plan B: Ablation study
    # -----------------------------------------------------------------------
    if args.ablation_json.exists():
        ablation_data: dict[str, dict[str, float]] = json.loads(
            args.ablation_json.read_text(encoding="utf-8")
        )
        print(f"Loaded ablation summary from {args.ablation_json}")

        r = plot_ablation_heatmap(ablation_data, args.out_dir / "ablation_heatmap.png")
        print(f"  [OK] {r}")

        r = plot_ablation_bar_chart(ablation_data, args.out_dir / "ablation_bar_chart.png")
        print(f"  [OK] {r}")
    else:
        print(f"[SKIP] Ablation JSON not found: {args.ablation_json}")

    print(f"\nAll outputs → {args.out_dir}")


if __name__ == "__main__":
    main()
