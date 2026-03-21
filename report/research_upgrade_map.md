# Research Upgrade Map

## TL;DR

If the goal is to replace the scripted matrix with something paper-worthy, do **not** just swap in a VLM everywhere.

The highest-value stack is:

1. Keep the current scripted policy only as a sanity-check baseline.
2. Add a **text-only agent baseline** that reads the serialized state and outputs tool calls.
3. Add a **vision-grounded agent baseline** that sees both the canvas image and the serialized state.
4. Replace scripted attacks with an **adversarial side-goal policy** driven by the same model family.
5. Keep the current heuristic stewardship monitor as the main baseline.
6. Add one **learned or model-based monitor** that scores action relevance and trajectory anomaly.
7. Keep the current heuristic score for compatibility.
8. Add one **independent quality judge** that scores screenshots against the brief.

That gives a much stronger research story than "scripted vs VLM". The story becomes:

- Does vision change agent behavior in this setting?
- Does trajectory-aware monitoring still help once the policy is a real multimodal model?
- Can a learned or judge-based monitor catch failures that the hardcoded thresholds miss?
- Can an output judge and a trace judge disagree in informative ways?

## What Is Already Hardcoded

The repo is already a strong scaffold, but several important components are fixed by hand. Some of those are good and should stay fixed because they define the setting. Others are exactly where research value can be added.

### Components that should remain fixed

These are part of the benchmark definition, not the weak point:

| Component | Where | Why keeping it fixed is good |
|---|---|---|
| Canvas geometry and element vocabulary | `layoutarena/env/models.py`, `layoutarena/env/elements.py` | Gives the setting a stable task interface. |
| Tool API | `layoutarena/env/tools.py` | Keeps agent behavior legible and trajectories interpretable. |
| Hard constraints | `layoutarena/env/constraints.py` | Provides a clean validity boundary that papers can compare against. |
| Replay export and visualization | `layoutarena/viz/replay.py`, `layoutarena/viz/render_canvas.py` | Already one of the strongest demo assets in the repo. |

### Components that are currently hardcoded and worth upgrading

| Component | Current implementation | Where | Why it limits the paper | High-value replacement |
|---|---|---|---|---|
| Nominal policy | Fixed 4-element template plus bounded jitter | `layoutarena/experiments/run_eval.py::nominal_hero_actions` | Makes the matrix mostly a scripted perturbation study instead of an agent-control study | Add text-only LLM policy and vision-grounded LLM/VLM policy |
| Brief dataset | 3 hand-written hero briefs | `layoutarena/experiments/briefs.py::hero_briefs` | Small coverage; easy for hardcoded priors to overfit | Parametric brief generator or larger brief bank with varied brand/layout intents |
| Attack library | Hand-authored attacks with fixed parameters | `layoutarena/attacks/*.py` | Too easy to match with hand-designed heuristics; limited adversarial pressure | Prompted adversary, best-of-N adversary, or search-based attack optimizer |
| Scripted attack scheduling | Appended or injected at fixed points | `layoutarena/experiments/batch_runner.py`, `layoutarena/experiments/run_eval.py`, `scripts/generate_trajectories.py` | Does not model adaptive side-task pursuit | Event-conditioned or policy-driven interleaving |
| Stewardship thresholds | Fixed margins, opacity/font thresholds, failure limits, escalation bonuses | `layoutarena/control/monitor.py::MonitorConfig` | Current monitor is easy to game and difficult to justify as general | Learned calibration over signals or a model-based action scorer |
| Risk composition | Sum of signal weights with 2 thresholds | `layoutarena/control/monitor.py::TrajectoryMonitor.suggest_decision` | No learned composition, no uncertainty, no interaction effects | Logistic regressor, boosted trees, small sequence model, or judge model |
| Optional element detection | Any `TEXT` or `SHAPE` placement contributes risk | `layoutarena/control/monitor.py` | Conflates creativity with suspiciousness | Brief-conditioned relevance model for optional elements |
| Redirect policy | Canonical hardcoded x/y/w/h defaults | `layoutarena/control/stewardship.py::_canonical_positions` | Makes stewardship partly a hidden template policy | Retrieval-based redirect, learned proposal, or brief-conditioned layout prior |
| Bounded-control regions | Static zone map for each element type | `layoutarena/control/bounded.py::build_default_zone_map` | Baseline is overly template-specific | Learn or synthesize envelopes from brief/template priors |
| Quality scoring | Penalty counts over soft/suspicious rules | `layoutarena/env/scoring.py` | Not visually grounded; can miss real design degradation | Pairwise VLM judge, reward model, or human preference eval |
| Salience and suspicious rules | Handwritten font/opacity/border heuristics | `layoutarena/env/constraints.py` | Captures only a narrow slice of real layout failures | OCR visibility checks, salience model, or image-based content judge |
| Agent observation | Text serialization only | `layoutarena/experiments/run_eval.py::_serialize_state_for_llm` | Current "LLM agent" is not actually vision-grounded | Pass screenshot + structured text state together |
| Metrics/plots | Safety often collapses to `monitor_detected`; usefulness to heuristic quality x yield | `scripts/generate_plots.py`, `layoutarena/viz/plots.py` | Broad detection mixes blocks and nudges; quality is still heuristic | Separate output-only vs trace-only metrics and add judge-based quality |
| Output artifacts | CSV lacks richer evaluator metadata | `layoutarena/experiments/output_writer.py` | Harder to compare policy/judge/monitor variants cleanly | Add model id, observation mode, judge source, attack policy id, trace labels |

## Components Already Close to Supporting VLMs

The repo already has useful multimodal plumbing. That lowers the cost of a vision-grounded upgrade.

| Existing capability | Where | Why it matters |
|---|---|---|
| `call_llm()` accepts multimodal `user_prompt` payloads | `layoutarena/llm/call_llm.py` | You do not need a brand-new model interface to send images. |
| SVG-to-PNG conversion support exists | `layoutarena/llm/multimodal.py` | Current SVG replays can become VLM-ready raster images with minimal extra work. |
| Canvas snapshots are already rendered every step | `layoutarena/viz/render_canvas.py`, `layoutarena/viz/replay.py` | The environment already produces the visual state you want the model to see. |

This means the fastest VLM path is:

1. Render the current canvas snapshot.
2. Convert SVG to PNG if needed.
3. Send `[{"type": "text", ...}, {"type": "image_url", ...}]` to `call_llm()`.
4. Keep the exact same tool-call JSON output format.

## Recommended Replacement for the Scripted Matrix

### Policy stack

Use three policy conditions:

1. `scripted_nominal`
   - Keep the current nominal policy as a non-learning lower baseline.
2. `text_agent`
   - Same tool interface, same brief, same state serializer.
   - No screenshot.
   - Purpose: isolate the value of reasoning over structured state alone.
3. `vision_agent`
   - Same prompt plus a rendered canvas image.
   - Purpose: test whether visual grounding changes search quality, attack behavior, and monitor interaction.

This is the cleanest paper question:

> Does multimodal perception make tool-using design agents better, riskier, or both?

### Attack stack

Use two attack modes:

1. `scripted_attack`
   - Keep the current attack templates for controlled regression tests.
2. `prompted_adversary`
   - Same model family as the main policy, but add a hidden objective:
     - hide payload content
     - degrade hierarchy while staying accepted
     - waste tool budget while preserving final layout

This makes the benchmark much more realistic. It also stops the monitor from benefiting from attacks that were designed with the monitor in mind.

### Monitor stack

Use two monitor conditions:

1. `heuristic_stewardship`
   - Current monitor unchanged.
   - Good baseline because it is transparent and interpretable.
2. `judge_or_learned_monitor`
   - Score each proposed action and the recent trajectory using:
     - brief
     - current visual state
     - current structured state
     - proposed action
     - recent action history

The monitor output should stay simple:

- `allow`
- `warn`
- `block`
- `risk_score`
- `reason_tags`

This preserves comparability with the current setting.

### Judge stack

Use two output evaluators:

1. `heuristic_score`
   - Current rule-based score for backward compatibility.
2. `independent_quality_judge`
   - Screenshot + brief in, score out.
   - Prefer pairwise comparison over absolute score if possible.

The judge should score at least:

- visual hierarchy
- readability
- brand/brief relevance
- hidden or suspicious content
- overall usefulness

## Best Algorithmic Upgrades by Return on Time

### 1. Vision-grounded policy

This is the single most obvious replacement for the scripted matrix.

Why it matters:

- The paper is about design agents.
- A text-only state dump is not how real design agents operate.
- The repo already has most of the plumbing required.

Minimal version:

- give the model one image of the current canvas
- also include the serialized state and recent history
- keep tool output format exactly the same

### 2. Brief-conditioned relevance monitor

This is likely the highest-value monitor upgrade.

Current weakness:

- `TEXT` and `SHAPE` are treated as suspicious too often
- relevance is not conditioned on the brief or on the visible layout

Minimal version:

- input: brief + current canvas + candidate action
- output: relevance score and explanation tags

Good research framing:

> Can a monitor distinguish optional-but-legitimate creative actions from covert side-task behavior?

### 3. Trajectory anomaly model

This is the best way to strengthen the "trajectory-aware control" contribution.

Current weakness:

- the monitor only sums local heuristics
- it does not really model trajectory shape

Useful approaches:

- feature-based logistic regression over recent-action stats
- gradient-boosted trees over hand-engineered trace features
- small transformer or RNN over tool-call sequences
- contrastive embedding of clean vs attacked trajectories

This does not need to be giant. Even a modest learned anomaly scorer is a strong upgrade over hand-tuned thresholds.

### 4. Pairwise VLM quality judge

This is the cleanest fix for the current heuristic quality score.

Current weakness:

- the quality score is rule-based
- it can miss bad but valid layouts
- it does not validate the "fuzzy domain" claim very well

Minimal version:

- compare two screenshots for the same brief
- ask which layout better satisfies the brief
- aggregate pairwise wins into a score

Even a small manually reviewed subset would make the paper much more defensible.

### 5. Adaptive adversary

This makes the benchmark look much more like control research and much less like unit tests.

Good options:

- same model as the policy with a hidden side task
- best-of-N attacker over candidate tool actions
- search-based evasion attack over monitor thresholds

This is especially valuable for the adaptive-evasion section.

## Suggested Minimal Winning Matrix

If time is tight, do this instead of a huge grid:

| Axis | Conditions |
|---|---|
| Policy | scripted, text-agent, vision-agent |
| Protocol | enforcement, bounded, stewardship-heuristic, stewardship-learned |
| Attack | none, hidden-content, hierarchy-sabotage, stealth-waste |
| Seeds | 3 to 5 |

That is already enough to show:

- policy capability changes with vision
- safety/usefulness tradeoffs across protocols
- whether learned monitoring beats threshold rules
- whether trace-aware control matters once the agent is real

## Suggested Experimental Narrative

If the submission is centered on research value, the cleanest narrative is:

1. Scripted runs validate the environment and make failure modes legible.
2. Text-only agents show that structured state is useful but incomplete.
3. Vision-grounded agents improve layout quality and/or change attack surface.
4. Heuristic monitoring catches easy attacks but misses brief-conditioned and near-threshold cases.
5. A learned or judge-based monitor improves detection without collapsing creativity.
6. Output-only judging and trace-aware judging disagree on matched-final-state attacks.

That last point is the most paper-worthy part.

## What Not to Overbuild Yet

These are interesting, but not the best next step:

- full framework port to a new benchmark library
- many more tool types
- responsive layout or multi-page layout
- fully learned layout generation from scratch
- large-scale fine-tuning

Those add surface area faster than they add paper value.

## Concretely Recommended Next Steps

1. Fix the stale-ID and non-interleaving bugs in the scripted pipeline.
2. Add `observation_mode = text | text+image` to the LLM runner.
3. Run a small text-vs-vision policy matrix.
4. Add one independent screenshot-based judge.
5. Replace the `optional_element_injection` shortcut with a brief-conditioned relevance scorer.
6. Only after that, consider a more general framework or external benchmark adapter.
