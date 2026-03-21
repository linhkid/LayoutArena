from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from layoutarena.env.elements import ElementType, LayoutElement

Region = tuple[int, int, int, int]


@dataclass
class CanvasSpec:
    width: int = 1200
    height: int = 800
    min_spacing: int = 24
    max_elements: int = 6


@dataclass
class LayoutBrief:
    brief_id: str
    title: str
    instructions: str
    required_elements: tuple[ElementType, ...] = (
        ElementType.HEADLINE,
        ElementType.SUBHEAD,
        ElementType.IMAGE,
        ElementType.LOGO,
    )
    optional_elements: tuple[ElementType, ...] = (
        ElementType.TEXT,
        ElementType.SHAPE,
    )
    notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProposedAction:
    tool_name: str
    params: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""


class ConstraintSeverity(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    SUSPICIOUS = "suspicious"


@dataclass
class ConstraintViolation:
    code: str
    message: str
    severity: ConstraintSeverity
    element_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstraintReport:
    violations: list[ConstraintViolation] = field(default_factory=list)

    @property
    def hard(self) -> list[ConstraintViolation]:
        return [
            violation
            for violation in self.violations
            if violation.severity == ConstraintSeverity.HARD
        ]

    @property
    def soft(self) -> list[ConstraintViolation]:
        return [
            violation
            for violation in self.violations
            if violation.severity == ConstraintSeverity.SOFT
        ]

    @property
    def suspicious(self) -> list[ConstraintViolation]:
        return [
            violation
            for violation in self.violations
            if violation.severity == ConstraintSeverity.SUSPICIOUS
        ]

    @property
    def has_hard_violation(self) -> bool:
        return bool(self.hard)

    def all_codes(self) -> list[str]:
        return [violation.code for violation in self.violations]


@dataclass
class ToolCallRecord:
    step_index: int
    tool_name: str
    parameters: dict[str, Any]
    status: str
    cost: int
    succeeded: bool
    message: str = ""
    violation_codes: list[str] = field(default_factory=list)
    monitor_reasons: list[str] = field(default_factory=list)


@dataclass
class MonitorDecision:
    allow: bool = True
    redirect: dict[str, Any] | None = None
    reasons: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    flag_suspicious: bool = False
    blocked_regions: list[Region] = field(default_factory=list)


@dataclass
class LayoutScore:
    validity: int
    quality_score: float
    tool_cost: int
    safety_penalty: float
    effective_yield: float
    net_utility: float
    component_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class SubmissionResult:
    accepted: bool
    score: LayoutScore
    report: ConstraintReport
    message: str


@dataclass
class LayoutSnapshot:
    step_index: int
    tool_name: str
    status: str
    message: str
    canvas_width: int
    canvas_height: int
    elements: dict[str, LayoutElement] = field(default_factory=dict)
    blocked_regions: list[Region] = field(default_factory=list)
    risk_score: float = 0.0


@dataclass
class LayoutState:
    brief: LayoutBrief
    canvas: CanvasSpec
    elements: dict[str, LayoutElement] = field(default_factory=dict)
    tool_history: list[ToolCallRecord] = field(default_factory=list)
    snapshots: list[LayoutSnapshot] = field(default_factory=list)
    blocked_regions: list[Region] = field(default_factory=list)
    risk_score: float = 0.0
    flagged_suspicious: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def next_step_index(self) -> int:
        return len(self.tool_history) + 1

    @property
    def current_tool_cost(self) -> int:
        return sum(record.cost for record in self.tool_history)

    def clone_with_elements(self, elements: dict[str, LayoutElement]) -> "LayoutState":
        return LayoutState(
            brief=self.brief,
            canvas=self.canvas,
            elements=deepcopy(elements),
            tool_history=list(self.tool_history),
            snapshots=list(self.snapshots),
            blocked_regions=list(self.blocked_regions),
            risk_score=self.risk_score,
            flagged_suspicious=self.flagged_suspicious,
            metadata=deepcopy(self.metadata),
        )

    def record_snapshot(
        self,
        *,
        step_index: int,
        tool_name: str,
        status: str,
        message: str,
    ) -> None:
        self.snapshots.append(
            LayoutSnapshot(
                step_index=step_index,
                tool_name=tool_name,
                status=status,
                message=message,
                canvas_width=self.canvas.width,
                canvas_height=self.canvas.height,
                elements=deepcopy(self.elements),
                blocked_regions=list(self.blocked_regions),
                risk_score=self.risk_score,
            ),
        )
