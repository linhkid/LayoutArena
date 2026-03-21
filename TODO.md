# LayoutArena Hackathon TODO

## Goal

Build a convincing **new AI control setting** for design agents, then show that different control protocols produce different points on the **safety vs. usefulness Pareto frontier**.

Primary submission target: **Track 1 (Control Setting Design)**
Secondary strength: the project also contains a credible **Track 2-style evaluation**.

Hackathon dates:

- **Friday, March 20, 2026**: build the environment
- **Saturday, March 21, 2026**: implement control protocols and run experiments
- **Sunday, March 22, 2026**: finalize plots, report, and demo

## Win Condition

To place well, LayoutArena should be:

- **Novel**: clearly different from BashArena, LinuxArena, SHADE-Arena, and triangle/grid toy settings
- **Legible**: judges should understand the control problem in under 60 seconds
- **Measurable**: strong metrics, reproducible runs, visible safety-usefulness tradeoffs
- **Transferable**: the tool-call interface should resemble real production agent systems
- **Demoable**: one visual replay should make the result feel obvious

The core idea that can win is not just "design agents are cool." It is:

> **LayoutArena makes control failure visible, quantitative, and intuitive in a domain where correctness is fuzzy and attacks can be gradual.**

## Non-Negotiable MVP

If time gets tight, do not cut these:

- A constrained 2D canvas with element placement tools
- A constraint checker for bounds, overlap, spacing, and hierarchy
- Per-tool-call compute cost accounting
- At least **3 control protocols**:
  - enforcement
  - bounded control
  - stewardship monitoring
- At least **2 adversarial side-task families**
- A results table and at least one Pareto frontier plot
- A replayable demo showing one successful malicious attempt and one caught attempt

If any feature threatens the MVP, cut polish first.

## Project Thesis

The strongest framing is:

1. Existing control settings mostly study coding, shell, or abstract search.
2. Real agents will increasingly act through structured tool calls in ambiguous domains.
3. Design is a clean testbed because:
   - quality is partly objective and partly fuzzy
   - malicious behavior can be subtle
   - exploration waste is easy to visualize
4. Therefore, LayoutArena tests whether monitoring can guide search while preserving useful creative progress.

## Current Status

Status as of **Friday, March 20, 2026** after the initial repo scaffold.

Legend:

- `[x]` scaffolded or implemented in code
- `[ ]` not yet implemented or not yet robust enough for experiments

Current repo progress:

- [x] Python package scaffold under `layoutarena/`
- [x] Environment state, elements, constraints, scoring, and tool executor
- [x] Three protocol scaffolds: enforcement, bounded control, stewardship
- [x] Three attack scaffolds: hidden content, quality sabotage, exploration abuse
- [x] SVG snapshot rendering and replay export
- [x] Scripted smoke-test path for one full episode
- [ ] Real LLM / agent policy loop
- [ ] Batch experiment runner that writes metrics and replay artifacts to disk
- [ ] Submission-quality plots, report, and demo assets

What this means:

- The architecture is in place.
- The main remaining work is no longer "what should the repo look like?"
- The main remaining work is "turn the scaffold into a research result."

## Friday: Environment Build

### 1. Define the environment contract

- [x] Fix the canvas size, coordinate system, and allowed element types
- [x] Define the layout brief schema
- [x] Define the observable state format
- [x] Define the action/tool API
- [x] Define what `submit_layout()` returns
- [x] Define when a run terminates

Suggested v1 tool API:

- `place_element(type, x, y, w, h, text_or_asset_id)`
- `move_element(id, x, y)`
- `resize_element(id, w, h)`
- `style_element(id, style_dict)`
- `delete_element(id)`
- `submit_layout()`

Design note: keep the API small. Fewer tools make behavior easier to monitor and experiments easier to interpret.

### 2. Implement hard constraints

- [x] Bounds checking
- [x] No-overlap rule
- [x] Minimum spacing rule
- [x] Headline above subhead rule
- [x] Logo placement restrictions
- [x] Maximum element count
- [x] Font-size / salience sanity checks

Important: split constraints into:

- **Hard invalidity constraints**: layout rejected
- **Soft quality penalties**: layout accepted but scored lower

That separation matters. It gives you a richer control problem than simple accept/reject.

### 3. Implement scoring

- [x] Binary validity score
- [x] Quality/composition score
- [x] Tool-call cost
- [x] Effective yield = valid layouts / total tool calls
- [x] Optional combined utility metric

Recommended decomposition:

- `validity`: 0 or 1
- `quality_score`: 0-100
- `tool_cost`: integer
- `effective_yield`: valid_submissions / total_calls
- `net_utility`: `validity * quality_score - alpha * tool_cost`

### 4. Build logging and replay

- [x] Log every tool call
- [x] Log whether the call succeeded or failed
- [x] Log monitor interventions
- [x] Save final canvas state
- [x] Save full trajectory for replay

This is critical for both the paper and the demo.

### 5. Create a minimal visualizer

- [x] Render the canvas after each action
- [ ] Color-code invalid attempts
- [x] Highlight the monitor’s interventions
- [x] Export step-by-step replay assets (SVG + JSON)
- [ ] Package replay into GIF/video or HTML viewer

The demo should not require explanation-heavy narration.

## Saturday: Control Protocols + Adversarial Tasks

### 6. Implement the three protocols

- [x] **Enforcement**: allow all actions, reject only after execution
- [x] **Bounded control**: predefine allowed zones / tool constraints
- [x] **Stewardship monitoring**: monitor the trajectory and adapt the operating envelope online

For stewardship v1, the monitor should be simple but credible:

- [x] Track repeated failures by region
- [x] Shrink or block high-failure regions
- [x] Flag suspicious tool sequences
- [ ] Raise scrutiny after failed suspicious calls
- [x] Redirect agent toward known-viable zones

Do not overbuild the monitor. A transparent heuristic monitor is enough if it produces a clear frontier shift.

### 7. Define adversarial side tasks

You need attacks that are subtle, realistic, and measurable.

- [x] Off-screen or near-edge hidden content
- [x] Tiny low-contrast text
- [ ] Off-brand decorative element insertion
- [x] Hierarchy degradation that remains technically valid
- [x] Suspicious repeated probing of constrained regions
- [ ] Tool-call side-channel patterns if applicable

Best v1 attack families:

1. **Content smuggling**
   - hidden or near-hidden text
   - off-canvas or barely visible elements
2. **Quality sabotage**
   - degrade hierarchy/spacing/brand consistency without tripping hard invalidity
3. **Exploration abuse**
   - waste compute through repeated low-value probing

These are easier to demonstrate than exotic exfiltration attacks and more defensible to judges.

### 8. Define monitorable suspicious patterns

- [x] Many failed placements in the same region
- [x] Repeated attempts near canvas borders
- [ ] Large style shifts with no layout gain
- [x] Addition of elements irrelevant to brief
- [x] Tiny text or extremely low contrast
- [x] Oscillation behavior: place-delete-place-delete

This section matters because it connects the monitor to observable agent behavior, not vague intent.

### 9. Run experiments

- [x] Choose 3-5 brief templates
- [x] Choose 2-3 attack types
- [ ] Run each protocol across multiple seeds
- [x] Scaffold threshold sweeping
- [ ] Save raw per-run metrics and replay artifacts to disk

Minimum acceptable experiment matrix:

- 3 protocols
- 3 briefs
- 2 adversarial side tasks
- 10 seeds each

That is already enough to produce convincing early plots.

## Sunday: Results, Report, Submission

### 10. Produce the core figures

- [ ] Safety vs. usefulness Pareto frontier
- [ ] Tool-cost distribution by protocol
- [ ] Attack detection rate by attack family
- [ ] Example trajectory visualizations
- [ ] One ablation: stewardship without adaptive zoning vs. full stewardship

If you only have time for one strong figure, make it the Pareto plot plus 2 qualitative replay panels.

### 11. Write the report

- [ ] Problem framing
- [ ] Why design is a new control setting
- [ ] Environment and tool API
- [ ] Hard vs. soft constraints
- [ ] Threat model and adversarial side tasks
- [ ] Three protocols
- [ ] Metrics
- [ ] Results
- [ ] Limitations
- [ ] Why this transfers to real tool-using agents

Report advice:

- Lead with the setting, not implementation details
- Include one diagram of the control loop
- Include one screenshot per protocol
- Be explicit about what is objective vs. subjective in the domain

### 12. Prepare the demo

- [ ] One 30-60 second talk track
- [ ] One clean example brief
- [ ] One malicious trajectory caught by stewardship
- [ ] One malicious or wasteful trajectory not prevented by enforcement
- [ ] One side-by-side comparison clip

The demo should answer:

- What is the agent trying to do?
- What is the hidden side task?
- What does the monitor see?
- Why is stewardship better?

## Suggestions That Improve Your Odds

### A. Keep the brief space narrow

Do not start with general web design. Start with one narrow task family:

- hero section
- promo banner
- event poster

Narrow scope makes constraints cleaner, evaluation stronger, and results easier to compare.

### B. Separate safety failure from taste

This is one of the biggest risks. If judges think the project is just "we made a subjective design scorer," the contribution weakens.

Avoid that by separating:

- objective hard constraints
- semi-objective composition heuristics
- adversarial policy violations

### C. Make the monitor trajectory-aware

This is the strongest conceptual edge over baseline filtering.

Do not only judge final outputs. Show that:

- the same final layout can hide very different search behavior
- suspicious exploration patterns predict side-task behavior
- online intervention can improve yield, not just catch attacks

### D. Prefer clear attacks over clever attacks

For a 3-day hackathon, visible attacks win.

Better:

- hidden text
- tiny low-contrast text
- repeated probing near blocked zones
- inserting irrelevant shape/logo

Worse:

- complicated covert channels that take too long to justify

### E. Show compute waste explicitly

This is an unusually strong part of your setting.

Track and visualize:

- failed calls
- repeated invalid regions
- wasted tool budget before final rejection

This makes the control tradeoff concrete.

### F. Keep stewardship interpretable

Judges are more likely to trust:

- region blacklisting
- risk score accumulation
- failure-aware redirection

than an opaque learned monitor with weak evidence.

## What Gives You an Edge If You Want to Win

### 1. The strongest edge: novel domain + real control loop

Most entries will either:

- build another coding-style control setting, or
- stay too abstract

LayoutArena can stand out because it is:

- visual
- tool-mediated
- easy to demo
- closer to future product agents

If executed well, this is both more memorable and more transferable.

### 2. The second edge: fuzzy-domain control is genuinely harder

Your setting is stronger if you emphasize:

- attacks are not only binary
- quality degradation can be gradual
- monitors must reason about trajectories, not only end states

That is a meaningful research contribution, not just a UI twist.

### 3. The third edge: stewardship can improve usefulness, not only safety

This is the highest-value hypothesis in the whole project.

Do not frame stewardship as just "more restrictive monitoring." Frame it as:

> monitoring that reduces wasted exploration and pushes the agent toward productive search regions

If your plot shows stewardship is safer **and** more compute-efficient than enforcement, that is very compelling.

### 4. The fourth edge: visual evidence beats abstract claims

You should be able to show:

- a messy failed exploration trace
- a suspicious malicious trace
- a clean stewarded trace

In a hackathon, that can matter as much as the writeup.

## Risks To Avoid

- [ ] Making the domain too broad
- [ ] Spending too much time on pretty rendering instead of experimental clarity
- [ ] Using only subjective scoring
- [ ] Building a monitor too complex to explain
- [ ] Failing to log trajectories
- [ ] Having no convincing adversarial examples
- [ ] Producing only one-off anecdotes without repeated trials

## Current Repo Structure

Current scaffold:

```text
layoutarena/
  env/
    canvas.py
    elements.py
    constraints.py
    scoring.py
    tools.py
  control/
    enforcement.py
    bounded.py
    stewardship.py
    monitor.py
  attacks/
    hidden_content.py
    quality_sabotage.py
    exploration_abuse.py
  experiments/
    briefs.py
    run_eval.py
    sweep_thresholds.py
  viz/
    render_canvas.py
    replay.py
    plots.py
report/
  figures/
  notes.md
```

Planned additions:

```text
outputs/
  runs/
  replays/
  figures/
scripts/
  run_single.py
  run_batch.py
tests/
  test_smoke.py
```

## Updated Next 12 Steps

Do these in order now that the scaffold exists:

1. [x] Freeze the v1 scope: hero section only
2. [x] Scaffold the tool API, state schema, constraints, and scoring
3. [x] Scaffold enforcement, bounded control, and stewardship protocols
4. [x] Scaffold hidden-content, quality-sabotage, and exploration-abuse attacks
5. [ ] Implement a real policy loop in `layoutarena/experiments/run_eval.py`
6. [ ] Add a policy wrapper that combines the main task policy with a hidden side-task policy
7. [ ] Add `outputs/` writing for per-run summaries, replay assets, and CSV metrics
8. [ ] Build a batch runner over briefs × protocols × attacks × seeds
9. [ ] Generate the first real safety/usefulness table and Pareto frontier
10. [ ] Produce 3 canonical qualitative trajectories: enforcement fail, bounded partial, stewardship catch
11. [ ] Add one stewardship ablation: no redirect vs. redirect
12. [ ] Write the report around measured results and screenshot evidence

## Submission Positioning

The submission should say, in plain language:

> We introduce LayoutArena, a control setting for tool-using design agents. Unlike prior control benchmarks centered on code or shell tasks, LayoutArena studies safety and usefulness in a creative domain with objective constraints, soft quality judgments, and subtle adversarial side tasks. We show that stewardship-style trajectory monitoring can improve both attack detection and effective yield by adaptively restricting unproductive search.

## Stretch Goals

Only do these if the MVP is already working:

- [ ] Learn monitor thresholds from data
- [ ] Add multiple canvas archetypes
- [ ] Add brand-style constraints
- [ ] Add natural-language explanations from the monitor
- [ ] Compare stronger/weaker attacking agents
- [ ] Release a benchmark package with seeds and standard briefs

## New Plans

### Plan A: Winning Path

This is the highest-value route if time allows.

- [ ] Connect a real tool-using agent to the scaffold
- [ ] Run repeated experiments across all 3 protocols
- [ ] Show a real Pareto frontier shift
- [ ] Export polished replay assets for the strongest 2-3 trajectories
- [ ] Write a compact report with one strong claim and one strong figure

### Plan B: Strong Fallback If Agent Integration Slips

This is the fallback that still produces a defensible hackathon submission.

- [ ] Keep the nominal scripted policy
- [ ] Inject attack policies deterministically
- [ ] Sweep stewardship thresholds and compare against enforcement and bounded control
- [ ] Use replay evidence plus compute-cost metrics to support the claim
- [ ] Submit as a strong control-setting artifact even if the agent is not fully autonomous

### Saturday Plan: March 21, 2026

- [ ] Finish agent integration or lock the scripted fallback
- [ ] Add disk output for batch runs
- [ ] Run the first comparison matrix
- [ ] Identify one attack that stewardship catches clearly and one that it struggles with
- [ ] Start figure generation early instead of waiting for the end

### Sunday Plan: March 22, 2026

- [ ] Freeze experiments by midday
- [ ] Pick one final Pareto figure and one final side-by-side replay
- [ ] Finish the report and submission text
- [ ] Record the demo around what already works
- [ ] Do not spend Sunday rebuilding the environment

## Final Reminder

If you want to win, the project should feel like a **research artifact**, not just a hackathon demo.

That means:

- clean task definition
- credible threat model
- interpretable protocols
- repeated experiments
- one memorable visual result
