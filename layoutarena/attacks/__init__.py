"""Adversarial side-task templates for LayoutArena."""

from layoutarena.attacks.exploration_abuse import ExplorationAbuseAttack
from layoutarena.attacks.hidden_content import HiddenContentAttack
from layoutarena.attacks.quality_sabotage import QualitySabotageAttack

__all__ = [
    "ExplorationAbuseAttack",
    "HiddenContentAttack",
    "QualitySabotageAttack",
]
