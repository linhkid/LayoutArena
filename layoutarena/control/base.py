from __future__ import annotations

from abc import ABC
from typing import Union

from layoutarena.env.models import (
    LayoutState,
    MonitorDecision,
    ProposedAction,
    SubmissionResult,
    ToolCallRecord,
)

Outcome = Union[ToolCallRecord, SubmissionResult]


class ControlProtocol(ABC):
    """Lifecycle hooks for monitoring and action shaping."""

    name = "base"

    def reset(self, state: LayoutState) -> None:
        del state

    def before_action(
        self,
        state: LayoutState,
        action: ProposedAction,
    ) -> MonitorDecision:
        del state, action
        return MonitorDecision()

    def before_submit(
        self,
        state: LayoutState,
        action: ProposedAction,
    ) -> MonitorDecision:
        return self.before_action(state, action)

    def after_action(
        self,
        state: LayoutState,
        action: ProposedAction,
        outcome: Outcome,
        decision: MonitorDecision,
    ) -> None:
        del state, action, outcome, decision
