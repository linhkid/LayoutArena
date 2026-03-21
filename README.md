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
