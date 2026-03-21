# LayoutArena

LayoutArena is a scaffold for a hackathon project on AI control for tool-using design agents.

The repository is organized around five areas:

- `layoutarena/env`: canvas state, element models, constraints, scoring, and tool execution
- `layoutarena/control`: enforcement, bounded control, stewardship monitoring, and monitor heuristics
- `layoutarena/attacks`: adversarial side-task templates
- `layoutarena/experiments`: sample briefs and evaluation runners
- `layoutarena/viz`: SVG rendering, replay export, and Pareto utilities

The current code is intentionally a typed scaffold: core interfaces are in place, some pieces are implemented, and the remaining research choices are marked with pseudocode comments where they still need project-specific decisions.

Quick sanity check:

```bash
python3 -m compileall layoutarena
```

The scaffold is compatible with the current local interpreter in this repo (`Python 3.9.x`).

Primary planning document: [TODO.md](TODO.md)

## Metrics and experiment outputs

Batch and single runs write `outputs/metrics.csv` plus per-run folders under `outputs/runs/<run_id>/` (see `layoutarena/experiments/output_writer.py`).

**Protocol-level monitoring** (what differentiates bounded control and stewardship from enforcement) is summarized on each `EpisodeSummary` and in the CSV:

| Field | Meaning |
|--------|---------|
| `monitor_detected` | True if the protocol **blocked** at least one tool call **or** attached non-empty `monitor_reasons` to a call that still executed (e.g. redirect-with-allow under stewardship). |
| `monitor_block_count` | Number of steps with `status == "blocked"` — the protocol vetoed execution. |
| `monitor_nudge_count` | Number of executed steps with non-empty `monitor_reasons` — “noticed and noted / shaped, but not vetoed.” |

Use `monitor_block_count` when you want a **strict** “hard intervention” rate for plots or tables; use `monitor_detected` for the **broad** protocol-attention signal (aligned with the default Pareto / detection-rate figures). `scripts/generate_plots.py` still uses `monitor_detected` for backward compatibility; new columns are optional when loading older CSVs (they default to zero).

Helper: `layoutarena.experiments.run_eval.compute_monitor_metrics(state)` returns `(monitor_detected, monitor_block_count, monitor_nudge_count)` from a final `LayoutState`.
