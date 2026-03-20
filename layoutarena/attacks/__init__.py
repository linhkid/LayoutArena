"""Adversarial side-task templates for LayoutArena."""

from layoutarena.attacks.adaptive_evasion import AdaptiveEvasionAttack
from layoutarena.attacks.exploration_abuse import ExplorationAbuseAttack
from layoutarena.attacks.hidden_content import HiddenContentAttack
from layoutarena.attacks.quality_sabotage import QualitySabotageAttack
from layoutarena.attacks.stealth_waste import StealthWasteAttack

__all__ = [
    "AdaptiveEvasionAttack",
    "ExplorationAbuseAttack",
    "HiddenContentAttack",
    "QualitySabotageAttack",
    "StealthWasteAttack",
]
