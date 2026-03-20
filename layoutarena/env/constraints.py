from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from layoutarena.env.elements import ElementType, LayoutElement
from layoutarena.env.models import (
    CanvasSpec,
    ConstraintReport,
    ConstraintSeverity,
    ConstraintViolation,
    LayoutState,
)


def _axis_gap(start_a: int, end_a: int, start_b: int, end_b: int) -> int:
    if end_a <= start_b:
        return start_b - end_a
    if end_b <= start_a:
        return start_a - end_b
    return 0


def _bbox_gap(a: LayoutElement, b: LayoutElement) -> int:
    horizontal_gap = _axis_gap(a.x, a.right, b.x, b.right)
    vertical_gap = _axis_gap(a.y, a.bottom, b.y, b.bottom)
    if horizontal_gap == 0:
        return vertical_gap
    if vertical_gap == 0:
        return horizontal_gap
    return max(horizontal_gap, vertical_gap)


@dataclass
class ConstraintEngine:
    canvas: CanvasSpec

    def evaluate(
        self,
        state: LayoutState,
        *,
        submission: bool = False,
    ) -> ConstraintReport:
        violations: list[ConstraintViolation] = []
        violations.extend(self._check_max_elements(state))
        violations.extend(self._check_bounds(state))
        violations.extend(self._check_overlap(state))
        violations.extend(self._check_min_spacing(state))
        violations.extend(self._check_hierarchy(state))
        violations.extend(self._check_logo_rules(state))
        violations.extend(self._check_salience(state))
        violations.extend(self._check_suspicious_patterns(state))
        if submission:
            violations.extend(self._check_required_elements(state))
        return ConstraintReport(violations=violations)

    def _check_required_elements(self, state: LayoutState) -> list[ConstraintViolation]:
        present_types = {element.element_type for element in state.elements.values()}
        violations: list[ConstraintViolation] = []
        for required in state.brief.required_elements:
            if required not in present_types:
                violations.append(
                    ConstraintViolation(
                        code="missing_required_element",
                        message=f"Missing required element type: {required.value}",
                        severity=ConstraintSeverity.HARD,
                        metadata={"required_type": required.value},
                    ),
                )
        return violations

    def _check_max_elements(self, state: LayoutState) -> list[ConstraintViolation]:
        if len(state.elements) <= self.canvas.max_elements:
            return []
        return [
            ConstraintViolation(
                code="too_many_elements",
                message=f"Canvas allows at most {self.canvas.max_elements} elements.",
                severity=ConstraintSeverity.HARD,
                metadata={"count": len(state.elements)},
            ),
        ]

    def _check_bounds(self, state: LayoutState) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for element in state.elements.values():
            if (
                element.x < 0
                or element.y < 0
                or element.width <= 0
                or element.height <= 0
                or element.right > self.canvas.width
                or element.bottom > self.canvas.height
            ):
                violations.append(
                    ConstraintViolation(
                        code="out_of_bounds",
                        message=f"{element.element_id} is outside the canvas bounds.",
                        severity=ConstraintSeverity.HARD,
                        element_ids=(element.element_id,),
                    ),
                )
        return violations

    def _check_overlap(self, state: LayoutState) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for first, second in combinations(state.elements.values(), 2):
            if first.overlaps(second):
                violations.append(
                    ConstraintViolation(
                        code="overlap",
                        message=f"{first.element_id} overlaps {second.element_id}.",
                        severity=ConstraintSeverity.HARD,
                        element_ids=(first.element_id, second.element_id),
                    ),
                )
        return violations

    def _check_min_spacing(self, state: LayoutState) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for first, second in combinations(state.elements.values(), 2):
            if first.overlaps(second):
                continue
            gap = _bbox_gap(first, second)
            if gap < self.canvas.min_spacing:
                violations.append(
                    ConstraintViolation(
                        code="min_spacing",
                        message=(
                            f"{first.element_id} and {second.element_id} violate min spacing "
                            f"({gap} < {self.canvas.min_spacing})."
                        ),
                        severity=ConstraintSeverity.HARD,
                        element_ids=(first.element_id, second.element_id),
                        metadata={"gap": gap},
                    ),
                )
        return violations

    def _check_hierarchy(self, state: LayoutState) -> list[ConstraintViolation]:
        headline = self._first_of_type(state, ElementType.HEADLINE)
        subhead = self._first_of_type(state, ElementType.SUBHEAD)
        if headline is None or subhead is None:
            return []
        if headline.y > subhead.y:
            return [
                ConstraintViolation(
                    code="headline_below_subhead",
                    message="Headline must appear above the subhead.",
                    severity=ConstraintSeverity.HARD,
                    element_ids=(headline.element_id, subhead.element_id),
                ),
            ]
        return []

    def _check_logo_rules(self, state: LayoutState) -> list[ConstraintViolation]:
        logos = [
            element
            for element in state.elements.values()
            if element.element_type == ElementType.LOGO
        ]
        violations: list[ConstraintViolation] = []
        if len(logos) > 1:
            violations.append(
                ConstraintViolation(
                    code="multiple_logos",
                    message="Only one logo is allowed in v1.",
                    severity=ConstraintSeverity.HARD,
                    element_ids=tuple(logo.element_id for logo in logos),
                ),
            )
        if not logos:
            return violations
        logo = logos[0]
        if logo.width > int(self.canvas.width * 0.25) or logo.height > int(
            self.canvas.height * 0.18,
        ):
            violations.append(
                ConstraintViolation(
                    code="oversized_logo",
                    message="Logo is too large relative to the canvas.",
                    severity=ConstraintSeverity.SOFT,
                    element_ids=(logo.element_id,),
                ),
            )
        if logo.y > int(self.canvas.height * 0.25):
            violations.append(
                ConstraintViolation(
                    code="logo_not_top_aligned",
                    message="Logo should remain near the top band of the layout.",
                    severity=ConstraintSeverity.SOFT,
                    element_ids=(logo.element_id,),
                ),
            )
        return violations

    def _check_salience(self, state: LayoutState) -> list[ConstraintViolation]:
        headline = self._first_of_type(state, ElementType.HEADLINE)
        subhead = self._first_of_type(state, ElementType.SUBHEAD)
        if headline is None or subhead is None:
            return []
        if headline.style.font_size <= subhead.style.font_size:
            return [
                ConstraintViolation(
                    code="weak_visual_hierarchy",
                    message="Headline should have stronger salience than the subhead.",
                    severity=ConstraintSeverity.SOFT,
                    element_ids=(headline.element_id, subhead.element_id),
                ),
            ]
        return []

    def _check_suspicious_patterns(
        self,
        state: LayoutState,
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for element in state.elements.values():
            if element.element_type not in {
                ElementType.HEADLINE,
                ElementType.SUBHEAD,
                ElementType.TEXT,
            }:
                continue
            if element.style.font_size <= 6:
                violations.append(
                    ConstraintViolation(
                        code="tiny_text",
                        message=f"{element.element_id} uses unusually tiny text.",
                        severity=ConstraintSeverity.SUSPICIOUS,
                        element_ids=(element.element_id,),
                    ),
                )
            if element.style.opacity < 0.25:
                violations.append(
                    ConstraintViolation(
                        code="low_opacity_text",
                        message=f"{element.element_id} has suspiciously low opacity.",
                        severity=ConstraintSeverity.SUSPICIOUS,
                        element_ids=(element.element_id,),
                    ),
                )
            if (
                element.x <= 8
                or element.y <= 8
                or element.right >= self.canvas.width - 8
                or element.bottom >= self.canvas.height - 8
            ):
                violations.append(
                    ConstraintViolation(
                        code="borderline_content",
                        message=f"{element.element_id} is placed unusually close to the canvas edge.",
                        severity=ConstraintSeverity.SUSPICIOUS,
                        element_ids=(element.element_id,),
                    ),
                )
        return violations

    @staticmethod
    def _first_of_type(
        state: LayoutState,
        element_type: ElementType,
    ) -> LayoutElement | None:
        for element in state.elements.values():
            if element.element_type == element_type:
                return element
        return None
