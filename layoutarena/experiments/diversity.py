"""Design-native diversity metric for comparing layout variance across seeds."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from layoutarena.env.models import LayoutState


@dataclass
class DiversityReport:
    """Diversity scores computed across a set of layout states."""

    spatial_coverage: float = 0.0
    style_variance: float = 0.0
    arrangement_entropy: float = 0.0
    combined_index: float = 0.0
    n_layouts: int = 0


def compute_diversity(states: list[LayoutState]) -> DiversityReport:
    """Compute diversity across a list of final layout states.

    Metrics:
    - **Spatial coverage**: Variance of element (x, y) centroids across layouts.
    - **Style variance**: Coefficient of variation of font_size and opacity.
    - **Arrangement entropy**: Discretize positions into a 6x4 grid and compute
      entropy of which cell each element type lands in.
    """
    if len(states) < 2:
        return DiversityReport(n_layouts=len(states))

    # Collect centroid positions per element type across layouts
    centroids_by_type: dict[str, list[tuple[float, float]]] = defaultdict(list)
    font_sizes: list[float] = []
    opacities: list[float] = []

    # Grid for arrangement entropy: 6 columns x 4 rows
    grid_cols, grid_rows = 6, 4
    cell_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for state in states:
        for el in state.elements.values():
            etype = el.element_type.value
            cx = el.x + el.width / 2
            cy = el.y + el.height / 2
            centroids_by_type[etype].append((cx, cy))

            font_sizes.append(float(el.style.font_size))
            opacities.append(float(el.style.opacity))

            # Grid cell
            col = min(int(cx / (state.canvas.width / grid_cols)), grid_cols - 1)
            row = min(int(cy / (state.canvas.height / grid_rows)), grid_rows - 1)
            cell_key = f"{col}:{row}"
            cell_counts[etype][cell_key] += 1

    # 1. Spatial coverage: mean variance of centroids
    variances: list[float] = []
    for _etype, coords in centroids_by_type.items():
        if len(coords) < 2:
            continue
        mean_x = sum(c[0] for c in coords) / len(coords)
        mean_y = sum(c[1] for c in coords) / len(coords)
        var = sum((c[0] - mean_x) ** 2 + (c[1] - mean_y) ** 2 for c in coords) / len(
            coords,
        )
        variances.append(var)
    spatial_coverage = (sum(variances) / len(variances)) if variances else 0.0

    # 2. Style variance: coefficient of variation for font_size and opacity
    def _cv(values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        if mean == 0:
            return 0.0
        var = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(var) / mean

    style_variance = (_cv(font_sizes) + _cv(opacities)) / 2

    # 3. Arrangement entropy: per-type entropy of grid cell distribution
    entropies: list[float] = []
    for _etype, cells in cell_counts.items():
        total = sum(cells.values())
        if total == 0:
            continue
        ent = 0.0
        for count in cells.values():
            p = count / total
            if p > 0:
                ent -= p * math.log2(p)
        entropies.append(ent)
    arrangement_entropy = (sum(entropies) / len(entropies)) if entropies else 0.0

    # Combined index: simple average of normalised scores
    # Spatial coverage can be large; normalise by dividing by 1000
    norm_spatial = min(spatial_coverage / 1000.0, 1.0)
    norm_style = min(style_variance, 1.0)
    # Entropy max for a 24-cell grid is ~4.58; normalise
    norm_entropy = min(arrangement_entropy / 4.58, 1.0)
    combined = (norm_spatial + norm_style + norm_entropy) / 3

    return DiversityReport(
        spatial_coverage=spatial_coverage,
        style_variance=style_variance,
        arrangement_entropy=arrangement_entropy,
        combined_index=combined,
        n_layouts=len(states),
    )
