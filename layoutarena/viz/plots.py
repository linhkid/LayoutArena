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
    "stewardship (t=0.5)": "#27ae60",
    "stewardship (t=0.7)": "#2ecc71",
    "stewardship (t=0.9)": "#82e0aa",
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

    # Compute detection rates using monitor_detected (protocol-level) if
    # available, falling back to suspicious_flagged (env-level) otherwise.
    rates: dict[str, dict[str, float]] = {}
    for attack in attacks:
        buckets: dict[str, list[bool]] = defaultdict(list)
        for s in summaries_by_attack[attack]:
            detected = getattr(s, "monitor_detected", s.suspicious_flagged)
            buckets[s.protocol_name].append(detected)
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
        det_r = (
            sum(getattr(s, "monitor_detected", s.suspicious_flagged) for s in sums) / n
        )
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
    """Dual-axis line plot: detection rate and usefulness as a function of threshold.

    Parameters
    ----------
    sweep_results:
        List of objects with ``.threshold``, ``.detection_rate``,
        and ``.summary`` (with quality_score, effective_yield).
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    _apply_style()
    fig, ax_detect = plt.subplots(figsize=_DEFAULT_FIGSIZE)
    ax_useful = ax_detect.twinx()

    thresholds = [r.threshold for r in sweep_results]
    detect_vals = [getattr(r, "detection_rate", 0.0) for r in sweep_results]
    useful_vals = [
        r.summary.quality_score * r.summary.effective_yield for r in sweep_results
    ]

    (line_d,) = ax_detect.plot(
        thresholds,
        detect_vals,
        color="#2ecc71",
        marker="o",
        linewidth=2,
        label="Detection Rate",
    )
    (line_u,) = ax_useful.plot(
        thresholds,
        useful_vals,
        color="#3498db",
        marker="s",
        linewidth=2,
        label="Usefulness",
    )

    ax_detect.set_xlabel("Stewardship Threshold", fontsize=13)
    ax_detect.set_ylabel(
        "Detection Rate (monitor_detected)",
        fontsize=13,
        color="#2ecc71",
    )
    ax_useful.set_ylabel("Usefulness (quality x yield)", fontsize=13, color="#3498db")
    ax_detect.tick_params(axis="y", labelcolor="#2ecc71")
    ax_useful.tick_params(axis="y", labelcolor="#3498db")

    lines = [line_d, line_u]
    labels = [l.get_label() for l in lines]
    ax_detect.legend(lines, labels, loc="lower right", frameon=True, fontsize=10)

    ax_detect.set_title(
        title or "Threshold Sweep: Detection Rate vs. Usefulness",
        fontsize=15,
    )
    ax_detect.grid(True, alpha=0.3)

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


# ---------------------------------------------------------------------------
# Plan A: plot_llm_threshold_curve
# ---------------------------------------------------------------------------


def plot_llm_threshold_curve(
    llm_sweep: list,
    scripted_sweep: list | None,
    output_path: str | Path,
    title: str | None = None,
) -> Path | None:
    """Dual-axis threshold sweep comparing LLM agent vs scripted baseline."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    _apply_style()
    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)

    thresholds_llm = [r.threshold for r in llm_sweep]
    detect_llm = [getattr(r, "detection_rate", 0.0) for r in llm_sweep]
    useful_llm = [r.summary.quality_score * r.summary.effective_yield for r in llm_sweep]

    ax.plot(thresholds_llm, detect_llm, color="#e74c3c", marker="o", linewidth=2.5,
            label="LLM — Detection Rate")

    ax2 = ax.twinx()
    ax2.plot(thresholds_llm, useful_llm, color="#e74c3c", marker="s", linewidth=2.5,
             linestyle="--", label="LLM — Usefulness")

    if scripted_sweep:
        thresholds_s = [r.threshold for r in scripted_sweep]
        detect_s = [getattr(r, "detection_rate", 0.0) for r in scripted_sweep]
        useful_s = [r.summary.quality_score * r.summary.effective_yield for r in scripted_sweep]
        ax.plot(thresholds_s, detect_s, color="#2ecc71", marker="^", linewidth=2.0,
                alpha=0.7, label="Scripted — Detection Rate")
        ax2.plot(thresholds_s, useful_s, color="#2ecc71", marker="D", linewidth=2.0,
                 alpha=0.7, linestyle="--", label="Scripted — Usefulness")

    ax.set_xlabel("Stewardship Block Threshold", fontsize=13)
    ax.set_ylabel("Detection Rate", fontsize=13, color="#e74c3c")
    ax2.set_ylabel("Usefulness (quality × yield)", fontsize=13, color="#555")
    ax.tick_params(axis="y", labelcolor="#e74c3c")
    ax.set_ylim(-0.05, 1.15)

    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc="lower left", fontsize=10, frameon=True)

    ax.set_title(title or "Threshold Sweep: LLM Agent vs Scripted Baseline", fontsize=14)
    ax.grid(True, alpha=0.3)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=_DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    return target


# ---------------------------------------------------------------------------
# Plan A: plot_llm_vs_scripted_table
# ---------------------------------------------------------------------------


def plot_llm_vs_scripted_table(
    llm_summaries: list,
    scripted_summaries: list,
    output_path: str | Path,
) -> Path | None:
    """Side-by-side table comparing LLM agent vs scripted performance per protocol."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    _apply_style()

    from collections import defaultdict

    def _stats(sums: list) -> dict:
        n = max(len(sums), 1)
        return {
            "Avg Quality": f"{sum(s.quality_score for s in sums)/n:.1f}",
            "Avg Cost": f"{sum(s.tool_cost for s in sums)/n:.1f}",
            "Avg Yield": f"{sum(s.effective_yield for s in sums)/n:.3f}",
            "Detect Rate": f"{sum(getattr(s,'monitor_detected',False) for s in sums)/n:.0%}",
            "Safety Pen.": f"{sum(s.safety_penalty for s in sums)/n:.1f}",
        }

    llm_by_proto: dict[str, list] = defaultdict(list)
    for s in llm_summaries:
        llm_by_proto[s.protocol_name].append(s)

    scr_by_proto: dict[str, list] = defaultdict(list)
    for s in scripted_summaries:
        scr_by_proto[s.protocol_name].append(s)

    protocols = sorted(set(llm_by_proto) | set(scr_by_proto))
    metric_keys = ["Avg Quality", "Avg Cost", "Avg Yield", "Detect Rate", "Safety Pen."]
    columns = [f"LLM {k}" for k in metric_keys] + [f"Scripted {k}" for k in metric_keys]

    cell_text = []
    row_labels = []
    for proto in protocols:
        llm_s = _stats(llm_by_proto.get(proto, []))
        scr_s = _stats(scr_by_proto.get(proto, []))
        row_labels.append(proto)
        cell_text.append([llm_s[k] for k in metric_keys] + [scr_s[k] for k in metric_keys])

    fig, ax = plt.subplots(figsize=(14, 1.5 + 0.7 * len(protocols)))
    ax.axis("off")
    table = ax.table(cellText=cell_text, rowLabels=row_labels, colLabels=columns,
                     loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.5)

    for j in range(len(columns)):
        table[0, j].set_facecolor("#2c3e50")
        table[0, j].set_text_props(color="white", fontweight="bold", fontsize=8)
    for i, proto in enumerate(protocols):
        table[i + 1, -1].set_facecolor(_protocol_color(proto))
        table[i + 1, -1].set_text_props(color="white", fontweight="bold")

    n_metrics = len(metric_keys)
    for i in range(len(protocols)):
        for j in range(n_metrics):
            table[i + 1, j].set_facecolor("#d6eaf8")
        for j in range(n_metrics, 2 * n_metrics):
            table[i + 1, j].set_facecolor("#d5f5e3")

    ax.set_title("LLM Agent vs Scripted: Protocol Performance Comparison", fontsize=13, pad=20)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=_DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    return target


# ---------------------------------------------------------------------------
# Plan A: plot_llm_false_positive_curve  (ROC-style)
# ---------------------------------------------------------------------------


def plot_llm_false_positive_curve(
    llm_sweep: list,
    scripted_sweep: list | None,
    output_path: str | Path,
    title: str | None = None,
) -> Path | None:
    """Plot FPR vs TPR (ROC-style) as stewardship threshold varies."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    _apply_style()
    fig, ax = plt.subplots(figsize=_DEFAULT_FIGSIZE)

    def _plot_roc(sweep, label_prefix, color, marker):
        tprs = [getattr(r, "detection_rate", 0.0) for r in sweep]
        fprs = [getattr(r, "fpr", 0.0) for r in sweep]
        thresholds = [r.threshold for r in sweep]
        ax.plot(fprs, tprs, color=color, marker=marker, linewidth=2.5, label=label_prefix)
        for fpr, tpr, t in zip(fprs, tprs, thresholds):
            ax.annotate(f"t={t}", (fpr, tpr), textcoords="offset points",
                        xytext=(5, 3), fontsize=7, color=color)

    _plot_roc(llm_sweep, "LLM Agent", "#e74c3c", "o")
    if scripted_sweep:
        _plot_roc(scripted_sweep, "Scripted Baseline", "#2ecc71", "^")

    ax.plot([0, 1], [0, 1], "k--", linewidth=1, alpha=0.4, label="Random")

    ax.set_xlabel("False Positive Rate (clean-run interference)", fontsize=13)
    ax.set_ylabel("True Positive Rate (attack detection)", fontsize=13)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.15)
    ax.set_title(title or "ROC View: Attack Detection vs Clean-Run Interference", fontsize=14)
    ax.legend(fontsize=10, frameon=True)
    ax.grid(True, alpha=0.3)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=_DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    return target


# ---------------------------------------------------------------------------
# Plan B: plot_ablation_heatmap
# ---------------------------------------------------------------------------


def plot_ablation_heatmap(
    ablation_data: dict[str, dict[str, float]],
    output_path: str | Path,
    title: str | None = None,
) -> Path | None:
    """Heatmap: rows=disabled_signal, cols=attack_family, values=detection_rate."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return None

    _apply_style()

    all_attacks = sorted(
        {atk for row in ablation_data.values()
         for atk in row if not atk.startswith("_") and atk != "none"}
    )
    all_labels = sorted(ablation_data.keys())
    if "baseline" in all_labels:
        all_labels = ["baseline"] + [l for l in all_labels if l != "baseline"]

    matrix = np.zeros((len(all_labels), len(all_attacks)))
    for i, label in enumerate(all_labels):
        for j, atk in enumerate(all_attacks):
            matrix[i, j] = ablation_data[label].get(atk, 0.0)

    baseline_idx = all_labels.index("baseline") if "baseline" in all_labels else None
    if baseline_idx is not None:
        baseline_row = matrix[baseline_idx, :]
        drop_matrix = baseline_row[np.newaxis, :] - matrix
    else:
        drop_matrix = np.zeros_like(matrix)

    fig, axes = plt.subplots(1, 2, figsize=(16, max(5, 0.45 * len(all_labels))),
                             gridspec_kw={"width_ratios": [1, 1]})

    short_labels = [l.replace("drop_", "-").replace("_mechanism", "") for l in all_labels]

    im1 = axes[0].imshow(matrix, vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
    axes[0].set_xticks(range(len(all_attacks)))
    axes[0].set_xticklabels([a.replace("_", "\n") for a in all_attacks], fontsize=8)
    axes[0].set_yticks(range(len(all_labels)))
    axes[0].set_yticklabels(short_labels, fontsize=9)
    axes[0].set_title("Detection Rate (absolute)", fontsize=12)
    for i in range(len(all_labels)):
        for j in range(len(all_attacks)):
            val = matrix[i, j]
            axes[0].text(j, i, f"{val:.0%}", ha="center", va="center",
                         fontsize=7, color="black" if 0.3 < val < 0.8 else "white")
    plt.colorbar(im1, ax=axes[0], shrink=0.8)

    im2 = axes[1].imshow(drop_matrix, vmin=-0.2, vmax=1.0, cmap="Reds", aspect="auto")
    axes[1].set_xticks(range(len(all_attacks)))
    axes[1].set_xticklabels([a.replace("_", "\n") for a in all_attacks], fontsize=8)
    axes[1].set_yticks(range(len(all_labels)))
    axes[1].set_yticklabels(short_labels, fontsize=9)
    axes[1].set_title("Detection Drop vs Baseline", fontsize=12)
    for i in range(len(all_labels)):
        for j in range(len(all_attacks)):
            val = drop_matrix[i, j]
            axes[1].text(j, i, f"{val:+.0%}", ha="center", va="center",
                         fontsize=7, color="white" if val > 0.5 else "black")
    plt.colorbar(im2, ax=axes[1], shrink=0.8)

    fig.suptitle(title or "Signal Ablation: Detection Rate per Attack Family", fontsize=14,
                 fontweight="bold", y=1.01)
    plt.tight_layout()

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=_DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    return target


# ---------------------------------------------------------------------------
# Plan B: plot_ablation_bar_chart
# ---------------------------------------------------------------------------


def plot_ablation_bar_chart(
    ablation_data: dict[str, dict[str, float]],
    output_path: str | Path,
    title: str | None = None,
) -> Path | None:
    """Horizontal bar chart: total detection-rate drop per disabled signal."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        return None

    _apply_style()

    attacks = sorted(
        {atk for row in ablation_data.values()
         for atk in row if not atk.startswith("_") and atk != "none"}
    )

    baseline = ablation_data.get("baseline", {})

    drop_per_label: dict[str, float] = {}
    for label, row in ablation_data.items():
        if label == "baseline":
            continue
        drops = [baseline.get(atk, 0.0) - row.get(atk, 0.0) for atk in attacks]
        drop_per_label[label] = sum(drops) / len(drops) if drops else 0.0

    sorted_labels = sorted(drop_per_label, key=lambda l: drop_per_label[l], reverse=True)
    drops = [drop_per_label[l] for l in sorted_labels]
    short_labels = [l.replace("drop_", "").replace("_mechanism", "") for l in sorted_labels]

    colors = ["#e74c3c" if d > 0.3 else "#f39c12" if d > 0.1 else "#2ecc71" for d in drops]

    fig, ax = plt.subplots(figsize=(10, max(5, 0.45 * len(sorted_labels))))
    y_pos = np.arange(len(sorted_labels))
    bars = ax.barh(y_pos, drops, color=colors, edgecolor="white", height=0.65)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(short_labels, fontsize=11)
    ax.invert_yaxis()
    ax.set_xlabel("Mean Detection Drop (relative to baseline)", fontsize=12)
    ax.set_title(title or "Signal Importance: Detection Drop When Signal Removed", fontsize=13)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.grid(True, axis="x", alpha=0.3)

    for bar, drop in zip(bars, drops):
        ax.text(
            max(drop, 0) + 0.01, bar.get_y() + bar.get_height() / 2,
            f"{drop:+.0%}", va="center", fontsize=9,
            color="#c0392b" if drop > 0 else "#27ae60",
        )

    plt.tight_layout()
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=_DEFAULT_DPI, bbox_inches="tight")
    plt.close(fig)
    return target
