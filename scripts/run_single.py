"""Run a single LayoutArena episode from the command line."""

from __future__ import annotations

import argparse
import logging

from layoutarena.env.models import CanvasSpec
from layoutarena.experiments.batch_runner import _make_attack, build_episode_actions
from layoutarena.experiments.briefs import hero_briefs
from layoutarena.experiments.output_writer import RunOutputWriter
from layoutarena.experiments.run_eval import run_llm_episode, run_scripted_episode


def _find_brief(brief_id: str):
    for brief in hero_briefs():
        if brief.brief_id == brief_id:
            return brief
    raise ValueError(
        f"Unknown brief: {brief_id}. Available: {[b.brief_id for b in hero_briefs()]}",
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run a single LayoutArena episode.")
    parser.add_argument(
        "--protocol",
        default="enforcement",
        choices=["enforcement", "bounded_control", "stewardship_monitoring"],
        help="Control protocol to use.",
    )
    parser.add_argument(
        "--brief",
        default="hero_saas",
        help="Brief ID (hero_saas, hero_event, hero_consumer).",
    )
    parser.add_argument(
        "--attack",
        default="none",
        choices=[
            "none",
            "hidden_content",
            "quality_sabotage",
            "exploration_abuse",
            "stealth_waste",
            "adaptive_evasion",
        ],
        help="Attack strategy to interleave.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed (for jitter and run ID).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.9,
        help="Stewardship threshold.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model name (None = scripted).",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=15,
        help="Max steps for LLM mode.",
    )
    parser.add_argument("--output-dir", default="outputs", help="Output directory.")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    brief = _find_brief(args.brief)
    canvas = CanvasSpec()
    attack = _make_attack(args.attack)

    threshold_tag = (
        f"_t{args.threshold}" if args.protocol == "stewardship_monitoring" else ""
    )
    run_id = f"{args.protocol}_{args.brief}_{args.attack}_s{args.seed}{threshold_tag}"

    if args.model is not None:
        env, summary = run_llm_episode(
            brief=brief,
            protocol_name=args.protocol,
            model=args.model,
            max_steps=args.max_steps,
            canvas=canvas,
            stewardship_threshold=args.threshold,
            attack=attack,
            seed=args.seed,
        )
    else:
        actions = build_episode_actions(canvas, brief, attack, seed=args.seed)
        env, summary = run_scripted_episode(
            brief=brief,
            protocol_name=args.protocol,
            actions=actions,
            canvas=canvas,
            stewardship_threshold=args.threshold,
        )

    writer = RunOutputWriter(args.output_dir)
    extra = {"attack": args.attack, "seed": args.seed, "threshold": args.threshold}
    writer.write_run(env, summary, run_id, extra_metadata=extra)
    writer.append_to_metrics_csv(summary, run_id, extra=extra)

    print(f"\nRun ID : {run_id}")
    print(f"Accepted : {summary.accepted}")
    print(f"Quality  : {summary.quality_score:.3f}")
    print(f"Tool cost: {summary.tool_cost}")
    print(f"Yield    : {summary.effective_yield:.3f}")
    print(f"Safety   : {summary.safety_penalty:.3f}")
    print(f"Flagged  : {summary.suspicious_flagged}")
    print(f"\nArtifacts: {args.output_dir}/runs/{run_id}/")


if __name__ == "__main__":
    main()
