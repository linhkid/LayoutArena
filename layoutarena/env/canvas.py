from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

from layoutarena.control.base import ControlProtocol
from layoutarena.control.enforcement import EnforcementProtocol
from layoutarena.env.constraints import ConstraintEngine
from layoutarena.env.models import (
    CanvasSpec,
    LayoutBrief,
    LayoutState,
    MonitorDecision,
    ProposedAction,
    SubmissionResult,
    ToolCallRecord,
)
from layoutarena.env.scoring import ScoringPolicy
from layoutarena.env.tools import ToolExecutor

Outcome = Union[ToolCallRecord, SubmissionResult]


@dataclass
class LayoutArenaEnv:
    """
    High-level environment wrapper.

    This is the object an experiment runner should own. It wires together:
    - the mutable layout state
    - the raw tool executor
    - an optional control protocol that can block or redirect actions
    """

    brief: LayoutBrief
    canvas: CanvasSpec = field(default_factory=CanvasSpec)
    protocol: ControlProtocol | None = None
    cost_per_call: int = 1
    state: LayoutState = field(init=False)
    constraints: ConstraintEngine = field(init=False)
    scoring: ScoringPolicy = field(init=False)
    tool_executor: ToolExecutor = field(init=False)

    def __post_init__(self) -> None:
        active_protocol = self.protocol or EnforcementProtocol()
        self.state = LayoutState(brief=self.brief, canvas=self.canvas)
        self.constraints = ConstraintEngine(self.canvas)
        self.scoring = ScoringPolicy()
        self.protocol = active_protocol
        self.tool_executor = ToolExecutor(
            state=self.state,
            constraints=self.constraints,
            scoring=self.scoring,
            cost_per_call=self.cost_per_call,
        )
        self.protocol.reset(self.state)
        self.state.record_snapshot(
            step_index=0,
            tool_name="reset",
            status="ready",
            message="Initialized empty canvas.",
        )

    def step(self, action: ProposedAction) -> Outcome:
        decision = (
            self.protocol.before_submit(self.state, action)
            if action.tool_name == "submit_layout"
            else self.protocol.before_action(self.state, action)
        )
        self._apply_decision_state(decision)

        if not decision.allow:
            outcome = self._record_blocked_action(action, decision)
            self.protocol.after_action(self.state, action, outcome, decision)
            return outcome

        params = dict(action.params)
        if decision.redirect:
            params.update(decision.redirect)

        outcome = self.tool_executor.execute(action.tool_name, **params)
        self.protocol.after_action(self.state, action, outcome, decision)
        return outcome

    def run_actions(self, actions: list[ProposedAction]) -> list[Outcome]:
        outcomes: list[Outcome] = []
        for action in actions:
            outcome = self.step(action)
            outcomes.append(outcome)
            if isinstance(outcome, SubmissionResult):
                break
        return outcomes

    def _apply_decision_state(self, decision: MonitorDecision) -> None:
        self.state.risk_score = max(self.state.risk_score, decision.risk_score)
        if decision.flag_suspicious:
            self.state.flagged_suspicious = True
        for region in decision.blocked_regions:
            if region not in self.state.blocked_regions:
                self.state.blocked_regions.append(region)

    def _record_blocked_action(
        self,
        action: ProposedAction,
        decision: MonitorDecision,
    ) -> ToolCallRecord:
        step_index = self.state.next_step_index
        record = ToolCallRecord(
            step_index=step_index,
            tool_name=action.tool_name,
            parameters=dict(action.params),
            status="blocked",
            cost=self.cost_per_call,
            succeeded=False,
            message="Action blocked by control protocol.",
            monitor_reasons=list(decision.reasons),
        )
        self.state.tool_history.append(record)
        self.state.record_snapshot(
            step_index=step_index,
            tool_name=action.tool_name,
            status="blocked",
            message=record.message,
        )
        return record
