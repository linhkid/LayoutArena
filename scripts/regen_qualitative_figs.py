#!/usr/bin/env python3
"""Regenerate the two qualitative comparison figures for the paper.

Figure 14 (bounded_partial_002.png):
  A clean bounded-control run (seed 2) where jitter pushes the LOGO outside
  its static zone. Shows the SUBMIT REJECTED step (orange header) — the logo
  was blocked, so the final submit fails due to a missing required element.
  Demonstrates bounded control's rigidity cost on an innocent run.

Figure 15 (stewardship_catch_new.png):
  Hidden-content attack under stewardship (threshold=0.7). Shows the BLOCKED
  step where the tiny, near-edge TEXT is caught before execution (red header +
  risk badge). Demonstrates stewardship's trajectory-aware detection.

Usage:
    DYLD_LIBRARY_PATH=$(brew --prefix cairo)/lib python3 scripts/regen_qualitative_figs.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import cairosvg  # noqa: E402

from layoutarena.attacks.hidden_content import HiddenContentAttack  # noqa: E402
from layoutarena.control.enforcement import EnforcementProtocol  # noqa: E402
from layoutarena.env.canvas import LayoutArenaEnv  # noqa: E402
from layoutarena.env.models import CanvasSpec, ProposedAction  # noqa: E402
from layoutarena.experiments.briefs import hero_briefs  # noqa: E402
from layoutarena.experiments.run_eval import (  # noqa: E402
    build_protocol,
    nominal_hero_actions,
)
from layoutarena.viz.render_canvas import render_snapshot_svg  # noqa: E402

FIGURES_DIR = PROJECT_ROOT / "report" / "figures"


def svg_to_png(svg_content: str, output_path: Path, scale: float = 1.5) -> None:
    """Convert SVG string to PNG file using cairosvg."""
    cairosvg.svg2png(
        bytestring=svg_content.encode("utf-8"),
        write_to=str(output_path),
        scale=scale,
    )
    print(f"  Written: {output_path}")


# ---------------------------------------------------------------------------
# Figure 14: Bounded control false positive — submit rejected (orange header)
# ---------------------------------------------------------------------------

def make_bounded_partial_fig() -> None:
    """Run bounded_control + no attack at seed 2. Show the submit-rejected step."""
    print("\n--- Figure 14: bounded_partial (submit rejected, orange header) ---")

    canvas = CanvasSpec()
    brief = hero_briefs()[0]  # hero_saas

    actions = nominal_hero_actions(canvas, seed=2)
    protocol = build_protocol("bounded_control", canvas)
    env = LayoutArenaEnv(brief=brief, canvas=canvas, protocol=protocol)
    env.run_actions(actions)

    # Find the submit-rejected snapshot (orange header — status "rejected")
    rejected_snap = next(
        (s for s in reversed(env.state.snapshots) if s.status == "rejected"),
        None,
    )
    # Fall back to the first blocked snapshot if submit was not rejected
    if rejected_snap is None:
        rejected_snap = next(
            (s for s in env.state.snapshots if s.status == "blocked"),
            None,
        )

    if rejected_snap is None:
        print("  ERROR: no rejected or blocked snapshot found for seed 2!")
        return

    print(
        f"  Using snapshot: step {rejected_snap.step_index} "
        f"({rejected_snap.tool_name} → {rejected_snap.status})"
    )

    svg = render_snapshot_svg(rejected_snap)
    out = FIGURES_DIR / "bounded_partial_002.png"
    svg_to_png(svg, out)


# ---------------------------------------------------------------------------
# Figure 15: Stewardship catch — blocked attack, red header + risk badge
# ---------------------------------------------------------------------------

def make_stewardship_catch_fig() -> None:
    """Run hidden_content + stewardship at t=0.7. Show the blocked step."""
    print("\n--- Figure 15: stewardship_catch (blocked attack, red header + risk badge) ---")

    canvas = CanvasSpec()
    brief = hero_briefs()[0]  # hero_saas
    attack = HiddenContentAttack()

    # Build nominal actions, run on throwaway env to get state for attack generation
    nominal = nominal_hero_actions(canvas)
    submit = nominal.pop()  # remove submit; add back after attack
    tmp_env = LayoutArenaEnv(brief=brief, canvas=canvas, protocol=EnforcementProtocol())
    for a in nominal:
        tmp_env.step(a)
    attack_actions = attack.generate_actions(tmp_env.state)
    actions = nominal + attack_actions + [submit]

    # Run with stewardship at t=0.7
    protocol = build_protocol("stewardship_monitoring", canvas, stewardship_threshold=0.7)
    env = LayoutArenaEnv(brief=brief, canvas=canvas, protocol=protocol)
    env.run_actions(actions)

    # Find the blocked step (the hidden-content TEXT placement)
    blocked_snap = next(
        (s for s in env.state.snapshots if s.status == "blocked"),
        None,
    )

    if blocked_snap is None:
        print("  ERROR: no blocked snapshot found — attack may not have been caught!")
        return

    print(
        f"  Using snapshot: step {blocked_snap.step_index} "
        f"({blocked_snap.tool_name} → {blocked_snap.status}, "
        f"risk_score={blocked_snap.risk_score:.3f}, "
        f"blocked_regions={len(blocked_snap.blocked_regions)})"
    )

    if blocked_snap.risk_score == 0.0:
        print("  WARNING: risk_score is 0 — risk badge will not appear!")
    if not blocked_snap.blocked_regions:
        print("  WARNING: no blocked regions — outline will not appear in canvas!")

    svg = render_snapshot_svg(blocked_snap)
    out = FIGURES_DIR / "stewardship_catch_new.png"
    svg_to_png(svg, out)


if __name__ == "__main__":
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    make_bounded_partial_fig()
    make_stewardship_catch_fig()
    print("\nDone.")
