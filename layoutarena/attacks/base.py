from __future__ import annotations

from abc import ABC, abstractmethod

from layoutarena.env.models import LayoutState, ProposedAction


class AttackStrategy(ABC):
    """
    Side-task interface.

    Attack strategies do not need to own the whole policy. In experiments, they can
    be interleaved with a nominal agent policy to model hidden objectives.
    """

    name = "base_attack"

    @abstractmethod
    def describe(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_actions(self, state: LayoutState) -> list[ProposedAction]:
        raise NotImplementedError
