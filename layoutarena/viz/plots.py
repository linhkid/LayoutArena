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


# ---------------------------------------------------------------------------
# Protocol color palette
# ---------------------------------------------------------------------------
PROTOCOL_COLORS: dict[str, str] = {
    "enforcement": "#e74c3c",
    "bounded_control": "#f39c12",
    "stewardship_monitoring": "#2ecc71",
}

_DEFAULT_FIGSIZE = (10, 7)
_DEFAULT_DPI = 300


def _apply_style() -> None:
    """Apply a clean plot style, falling back gracefully."""
    import matplotlib.pyplot as plt  # noqa: F811

    for style in ("seaborn-v0_8-whitegrid", "seaborn-whitegrid", "ggplot"):
        try:
            plt.style.use(style)
            return
        except OSError:
            continue


def _protocol_color(name: str) -> str:
    return PROTOCOL_COLORS.get(name, "#3498db")


# ---------------------------------------------------------------------------
# 6. summaries_to_pareto_points  (helper, no matplotlib needed)
# ---------------------------------------------------------------------------


def summaries_to_pareto_points(
    summaries: list,
    safety_fn=None,
    usefulness_fn=None,
) -> list[ParetoPoint]:
    """Convert a list of *EpisodeSummary* objects into averaged *ParetoPoint*s.

    Parameters
    ----------
    summaries:
        Iterable of ``EpisodeSummary`` (imported from run_eval).
    safety_fn:
        ``(EpisodeSummary) -> float``.  Default: ``max(0, min(100, 100 - s.safety_penalty))``.
    usefulness_fn:
        ``(EpisodeSummary) -> float``.  Default: ``s.quality_score * s.effective_yield``.

    Returns one *ParetoPoint* per unique ``protocol_name``, averaged over all
    summaries that share the same protocol.
    """
    if safety_fn is None:

        def safety_fn(s):  # type: ignore[misc]
            return max(0.0, min(100.0, 100.0 - s.safety_penalty))

    if usefulness_fn is None:

        def usefulness_fn(s):  # type: ignore[misc]
            return s.quality_score * s.effective_yield

    from collections import defaultdict

    buckets: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for s in summaries:
        buckets[s.protocol_name].append((safety_fn(s), usefulness_fn(s)))

    points: list[ParetoPoint] = []
    for proto, pairs in buckets.items():
        avg_safety = sum(p[0] for p in pairs) / len(pairs)
        avg_useful = sum(p[1] for p in pairs) / len(pairs)
        points.append(
            ParetoPoint(protocol_name=proto, safety=avg_safety, usefulness=avg_useful),
        )
    return points


# ---------------------------------------------------------------------------
# 1. plot_pareto_frontier
# ---------------------------------------------------------------------------


def plot_pareto_frontier(
    points: list[ParetoPoint],
    output_path: str | Path,
    title: str | None = None,
) -> Path | None:
    """Scatter plot of safety vs. usefulness with Pareto frontier overlay."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    _apply_style()
    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)

    # Group points by protocol
    from collections import defaultdict

    groups: dict[str, list[ParetoPoint]] = defaultdict(list)
    for pt in points:
        groups[pt.protocol_name].append(pt)

    for proto, pts in groups.items():
        xs = [p.usefulness for p in pts]
        ys = [p.safety for p in pts]
        ax.scatter(
            xs,
            ys,
            color=_protocol_color(proto),
            label=proto,
            s=60,
            alpha=0.7,
            edgecolors="white",
            linewidths=0.5,
        )

    # Compute and draw frontier
    frontier = pareto_frontier(points)
    if frontier:
        fx = [p.usefulness for p in frontier]
        fy = [p.safety for p in frontier]
        ax.plot(
            fx,
            fy,
            color="#2c3e50",
            linewidth=2,
            linestyle="--",
            label="Pareto frontier",
            zorder=5,
        )
        ax.scatter(
            fx,
            fy,
            color="#2c3e50",
            s=120,
            marker="D",
            zorder=6,
            edgecolors="white",
            linewidths=0.8,
        )

    ax.set_xlabel("Usefulness", fontsize=13)
    ax.set_ylabel("Safety", fontsize=13)
    ax.set_title(title or "Safety vs. Usefulness (Pareto Frontier)", fontsize=15)
    ax.legend(frameon=True, fontsize=10)
    ax.grid(True, alpha=0.3)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=_DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    return target


# ---------------------------------------------------------------------------
# 2. plot_tool_cost_distribution
# ---------------------------------------------------------------------------


def plot_tool_cost_distribution(
    summaries: list,
    output_path: str | Path,
    title: str | None = None,
) -> Path | None:
    """Box plot of tool-cost distribution grouped by protocol."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    _apply_style()
    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)

    from collections import defaultdict

    costs: dict[str, list[int]] = defaultdict(list)
    for s in summaries:
        costs[s.protocol_name].append(s.tool_cost)

    protocols = sorted(costs.keys())
    data = [costs[p] for p in protocols]
    colors = [_protocol_color(p) for p in protocols]

    bp = ax.boxplot(
        data,
        labels=protocols,
        patch_artist=True,
        widths=0.5,
        showmeans=True,
        meanprops={
            "marker": "o",
            "markerfacecolor": "white",
            "markeredgecolor": "black",
            "markersize": 6,
        },
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    ax.set_xlabel("Protocol", fontsize=13)
    ax.set_ylabel("Tool Cost", fontsize=13)
    ax.set_title(title or "Tool Cost Distribution by Protocol", fontsize=15)
    ax.grid(True, axis="y", alpha=0.3)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=_DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    return target


# ---------------------------------------------------------------------------
# 3. plot_attack_detection_rates
# ---------------------------------------------------------------------------


def plot_attack_detection_rates(
    summaries_by_attack: dict[str, list],
    output_path: str | Path,
    title: str | None = None,
) -> Path | None:
    """Grouped bar chart of detection rates by attack family and protocol.

    Parameters
    ----------
    summaries_by_attack:
        ``{attack_family: [EpisodeSummary, ...]}``.
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return None

    _apply_style()
    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)

    from collections import defaultdict

    # Gather all protocols across all attacks
    all_protocols: set[str] = set()
    for sums in summaries_by_attack.values():
        for s in sums:
            all_protocols.add(s.protocol_name)
    protocols = sorted(all_protocols)
    attacks = sorted(summaries_by_attack.keys())

    # Compute detection rates
    rates: dict[str, dict[str, float]] = {}
    for attack in attacks:
        buckets: dict[str, list[bool]] = defaultdict(list)
        for s in summaries_by_attack[attack]:
            buckets[s.protocol_name].append(s.suspicious_flagged)
        rates[attack] = {}
        for proto in protocols:
            flags = buckets.get(proto, [])
            rates[attack][proto] = (sum(flags) / len(flags)) if flags else 0.0

    x = np.arange(len(attacks))
    width = 0.8 / max(len(protocols), 1)

    for i, proto in enumerate(protocols):
        vals = [rates[a][proto] for a in attacks]
        offset = (i - (len(protocols) - 1) / 2) * width
        ax.bar(
            x + offset,
            vals,
            width=width * 0.9,
            label=proto,
            color=_protocol_color(proto),
            edgecolor="white",
            linewidth=0.5,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(attacks, rotation=30, ha="right")
    ax.set_xlabel("Attack Family", fontsize=13)
    ax.set_ylabel("Detection Rate", fontsize=13)
    ax.set_ylim(0, 1.05)
    ax.set_title(title or "Attack Detection Rates by Protocol", fontsize=15)
    ax.legend(frameon=True, fontsize=10)
    ax.grid(True, axis="y", alpha=0.3)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=_DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    return target


# ---------------------------------------------------------------------------
# 4. plot_safety_usefulness_table
# ---------------------------------------------------------------------------


def plot_safety_usefulness_table(
    summaries: list,
    output_path: str | Path,
) -> Path | None:
    """Render a summary table as a PNG figure.

    Rows: protocols.  Columns: avg quality, avg cost, avg yield, detection
    rate, avg safety penalty.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    _apply_style()

    from collections import defaultdict

    buckets: dict[str, list] = defaultdict(list)
    for s in summaries:
        buckets[s.protocol_name].append(s)

    protocols = sorted(buckets.keys())
    columns = [
        "Avg Quality",
        "Avg Cost",
        "Avg Yield",
        "Detection Rate",
        "Avg Safety Penalty",
    ]

    cell_text: list[list[str]] = []
    row_colors: list[str] = []
    for proto in protocols:
        sums = buckets[proto]
        n = len(sums)
        avg_q = sum(s.quality_score for s in sums) / n
        avg_c = sum(s.tool_cost for s in sums) / n
        avg_y = sum(s.effective_yield for s in sums) / n
        det_r = sum(s.suspicious_flagged for s in sums) / n
        avg_sp = sum(s.safety_penalty for s in sums) / n
        cell_text.append(
            [
                f"{avg_q:.2f}",
                f"{avg_c:.1f}",
                f"{avg_y:.2f}",
                f"{det_r:.2%}",
                f"{avg_sp:.2f}",
            ],
        )
        row_colors.append(_protocol_color(proto))

    fig, ax = plt.subplots(figsize=(10, 2 + 0.6 * len(protocols)))
    ax.axis("off")

    table = ax.table(
        cellText=cell_text,
        rowLabels=protocols,
        colLabels=columns,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.0, 1.6)

    # Color row labels
    for i, color in enumerate(row_colors):
        table[i + 1, -1].set_facecolor(color)
        table[i + 1, -1].set_text_props(color="white", fontweight="bold")

    # Header styling
    for j in range(len(columns)):
        table[0, j].set_facecolor("#2c3e50")
        table[0, j].set_text_props(color="white", fontweight="bold")

    ax.set_title("Protocol Performance Summary", fontsize=14, pad=20)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=_DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    return target


# ---------------------------------------------------------------------------
# 5. plot_threshold_sweep
# ---------------------------------------------------------------------------


def plot_threshold_sweep(
    sweep_results: list,
    output_path: str | Path,
    title: str | None = None,
) -> Path | None:
    """Dual-axis line plot: safety and usefulness as a function of threshold.

    Parameters
    ----------
    sweep_results:
        List of ``ThresholdSweepResult`` (from ``sweep_thresholds``).
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    _apply_style()
    fig, ax_safety = plt.subplots(figsize=_DEFAULT_FIGSIZE)
    ax_useful = ax_safety.twinx()

    thresholds = [r.threshold for r in sweep_results]
    safety_vals = [
        max(0.0, min(100.0, 100.0 - r.summary.safety_penalty)) for r in sweep_results
    ]
    useful_vals = [
        r.summary.quality_score * r.summary.effective_yield for r in sweep_results
    ]

    (line_s,) = ax_safety.plot(
        thresholds,
        safety_vals,
        color="#2ecc71",
        marker="o",
        linewidth=2,
        label="Safety",
    )
    (line_u,) = ax_useful.plot(
        thresholds,
        useful_vals,
        color="#3498db",
        marker="s",
        linewidth=2,
        label="Usefulness",
    )

    ax_safety.set_xlabel("Stewardship Threshold", fontsize=13)
    ax_safety.set_ylabel("Safety (100 - penalty)", fontsize=13, color="#2ecc71")
    ax_useful.set_ylabel("Usefulness (quality x yield)", fontsize=13, color="#3498db")
    ax_safety.tick_params(axis="y", labelcolor="#2ecc71")
    ax_useful.tick_params(axis="y", labelcolor="#3498db")

    lines = [line_s, line_u]
    labels = [l.get_label() for l in lines]
    ax_safety.legend(lines, labels, loc="lower right", frameon=True, fontsize=10)

    ax_safety.set_title(title or "Threshold Sweep: Safety vs. Usefulness", fontsize=15)
    ax_safety.grid(True, alpha=0.3)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=_DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    return target


# ---------------------------------------------------------------------------
# 7. plot_diversity_comparison
# ---------------------------------------------------------------------------


def plot_diversity_comparison(
    diversity_by_protocol: dict[str, "DiversityReport"],  # noqa: F821
    output_path: str | Path,
    title: str | None = None,
) -> Path | None:
    """Grouped bar chart comparing diversity metrics across protocols.

    Parameters
    ----------
    diversity_by_protocol:
        ``{protocol_name: DiversityReport}`` from ``diversity.compute_diversity``.
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return None

    _apply_style()
    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)

    protocols = sorted(diversity_by_protocol.keys())
    metric_names = [
        "Spatial Coverage",
        "Style Variance",
        "Arrangement Entropy",
        "Combined Index",
    ]

    x = np.arange(len(metric_names))
    width = 0.8 / max(len(protocols), 1)

    for i, proto in enumerate(protocols):
        dr = diversity_by_protocol[proto]
        # Normalise spatial coverage for visual comparability
        norm_spatial = min(dr.spatial_coverage / 1000.0, 1.0)
        vals = [
            norm_spatial,
            min(dr.style_variance, 1.0),
            min(dr.arrangement_entropy / 4.58, 1.0),
            dr.combined_index,
        ]
        offset = (i - (len(protocols) - 1) / 2) * width
        ax.bar(
            x + offset,
            vals,
            width=width * 0.9,
            label=proto,
            color=_protocol_color(proto),
            edgecolor="white",
            linewidth=0.5,
        )

    ax.set_xticks(x)
    ax.set_xticklabels(metric_names)
    ax.set_ylabel("Score (normalised)", fontsize=13)
    ax.set_ylim(0, 1.05)
    ax.set_title(title or "Layout Diversity by Protocol", fontsize=15)
    ax.legend(frameon=True, fontsize=10)
    ax.grid(True, axis="y", alpha=0.3)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=_DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    return target
