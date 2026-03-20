from __future__ import annotations

from layoutarena.control.base import ControlProtocol
from layoutarena.env.models import LayoutState, MonitorDecision, ProposedAction


class EnforcementProtocol(ControlProtocol):
    """
    Baseline protocol.

    The agent is free to act; violations are only discovered when the tool call
    hits the environment.
    """

    name = "enforcement"

    def before_action(
        self,
        state: LayoutState,
        action: ProposedAction,
    ) -> MonitorDecision:
        del state, action
        return MonitorDecision(allow=True)
