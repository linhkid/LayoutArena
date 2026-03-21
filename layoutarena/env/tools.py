from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from layoutarena.env.constraints import ConstraintEngine
from layoutarena.env.elements import ElementStyle, ElementType, LayoutElement
from layoutarena.env.models import (
    ConstraintReport,
    ConstraintSeverity,
    ConstraintViolation,
    LayoutState,
    SubmissionResult,
    ToolCallRecord,
)
from layoutarena.env.scoring import ScoringPolicy


@dataclass
class ToolExecutor:
    """
    Executes the low-level canvas tools.

    Behavior in v1:
    - every attempted tool call costs compute
    - hard constraint violations reject the action and revert the mutation
    - soft and suspicious findings are logged but do not block the action
    """

    state: LayoutState
    constraints: ConstraintEngine
    scoring: ScoringPolicy
    cost_per_call: int = 1
    id_prefixes: dict[ElementType, str] = field(
        default_factory=lambda: {
            ElementType.HEADLINE: "hdl",
            ElementType.SUBHEAD: "sub",
            ElementType.IMAGE: "img",
            ElementType.LOGO: "logo",
            ElementType.TEXT: "txt",
            ElementType.SHAPE: "shp",
        },
    )
    _element_counter: int = field(default=0, init=False)

    def execute(
        self,
        tool_name: str,
        **params: object,
    ) -> ToolCallRecord | SubmissionResult:
        if tool_name == "place_element":
            return self.place_element(**params)
        if tool_name == "move_element":
            return self.move_element(**params)
        if tool_name == "resize_element":
            return self.resize_element(**params)
        if tool_name == "style_element":
            return self.style_element(**params)
        if tool_name == "delete_element":
            return self.delete_element(**params)
        if tool_name == "submit_layout":
            return self.submit_layout()
        return self._record(
            tool_name=tool_name,
            parameters=dict(params),
            succeeded=False,
            status="error",
            message=f"Unknown tool: {tool_name}",
            report=ConstraintReport(
                violations=[
                    ConstraintViolation(
                        code="unknown_tool",
                        message=f"Unknown tool: {tool_name}",
                        severity=ConstraintSeverity.HARD,
                    ),
                ],
            ),
        )

    def place_element(
        self,
        *,
        element_type: ElementType | str,
        x: int,
        y: int,
        width: int,
        height: int,
        content: str | None = None,
        asset_id: str | None = None,
        style_patch: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ToolCallRecord:
        try:
            normalized_type = self._normalize_element_type(element_type)
        except ValueError:
            return self._record_invalid_tool_input(
                tool_name="place_element",
                parameters={
                    "element_type": element_type,
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                },
                message=f"Invalid element type: {element_type}",
            )

        def mutate(elements: dict[str, LayoutElement]) -> ConstraintReport | None:
            element_id = self._new_element_id(normalized_type)
            style = ElementStyle(**(style_patch or {}))
            elements[element_id] = LayoutElement(
                element_id=element_id,
                element_type=normalized_type,
                x=x,
                y=y,
                width=width,
                height=height,
                content=content,
                asset_id=asset_id,
                style=style,
                metadata=dict(metadata or {}),
            )
            return None

        return self._apply_mutation(
            tool_name="place_element",
            parameters={
                "element_type": normalized_type.value,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "content": content,
                "asset_id": asset_id,
                "style_patch": dict(style_patch or {}),
            },
            mutate=mutate,
        )

    def move_element(self, *, element_id: str, x: int, y: int) -> ToolCallRecord:
        def mutate(elements: dict[str, LayoutElement]) -> ConstraintReport | None:
            element = elements.get(element_id)
            if element is None:
                return self._missing_element_report(element_id)
            elements[element_id] = LayoutElement(
                element_id=element.element_id,
                element_type=element.element_type,
                x=x,
                y=y,
                width=element.width,
                height=element.height,
                content=element.content,
                asset_id=element.asset_id,
                style=element.style,
                metadata=dict(element.metadata),
            )
            return None

        return self._apply_mutation(
            tool_name="move_element",
            parameters={"element_id": element_id, "x": x, "y": y},
            mutate=mutate,
        )

    def resize_element(
        self,
        *,
        element_id: str,
        width: int,
        height: int,
    ) -> ToolCallRecord:
        def mutate(elements: dict[str, LayoutElement]) -> ConstraintReport | None:
            element = elements.get(element_id)
            if element is None:
                return self._missing_element_report(element_id)
            elements[element_id] = LayoutElement(
                element_id=element.element_id,
                element_type=element.element_type,
                x=element.x,
                y=element.y,
                width=width,
                height=height,
                content=element.content,
                asset_id=element.asset_id,
                style=element.style,
                metadata=dict(element.metadata),
            )
            return None

        return self._apply_mutation(
            tool_name="resize_element",
            parameters={"element_id": element_id, "width": width, "height": height},
            mutate=mutate,
        )

    def style_element(
        self,
        *,
        element_id: str,
        style_patch: dict[str, object],
    ) -> ToolCallRecord:
        def mutate(elements: dict[str, LayoutElement]) -> ConstraintReport | None:
            element = elements.get(element_id)
            if element is None:
                return self._missing_element_report(element_id)
            elements[element_id] = element.copy_with_style_patch(style_patch)
            return None

        return self._apply_mutation(
            tool_name="style_element",
            parameters={"element_id": element_id, "style_patch": dict(style_patch)},
            mutate=mutate,
        )

    def delete_element(self, *, element_id: str) -> ToolCallRecord:
        def mutate(elements: dict[str, LayoutElement]) -> ConstraintReport | None:
            if element_id not in elements:
                return self._missing_element_report(element_id)
            del elements[element_id]
            return None

        return self._apply_mutation(
            tool_name="delete_element",
            parameters={"element_id": element_id},
            mutate=mutate,
        )

    def submit_layout(self) -> SubmissionResult:
        step_index = self.state.next_step_index
        record = ToolCallRecord(
            step_index=step_index,
            tool_name="submit_layout",
            parameters={},
            status="pending",
            cost=self.cost_per_call,
            succeeded=False,
        )
        self.state.tool_history.append(record)

        report = self.constraints.evaluate(self.state, submission=True)
        accepted = not report.has_hard_violation
        message = (
            "Layout accepted."
            if accepted
            else "Layout rejected due to hard violations."
        )

        record.status = "accepted" if accepted else "rejected"
        record.succeeded = accepted
        record.message = message
        record.violation_codes = report.all_codes()

        if report.suspicious:
            self.state.flagged_suspicious = True

        score = self.scoring.score(self.state, report)
        self.state.record_snapshot(
            step_index=step_index,
            tool_name="submit_layout",
            status=record.status,
            message=message,
        )
        return SubmissionResult(
            accepted=accepted,
            score=score,
            report=report,
            message=message,
        )

    def _apply_mutation(
        self,
        *,
        tool_name: str,
        parameters: dict[str, object],
        mutate: callable,
    ) -> ToolCallRecord:
        working_elements = deepcopy(self.state.elements)
        early_report = mutate(working_elements)
        if early_report is not None:
            return self._record(
                tool_name=tool_name,
                parameters=parameters,
                succeeded=False,
                status="error",
                message="Tool input rejected before constraint evaluation.",
                report=early_report,
            )

        candidate_state = self.state.clone_with_elements(working_elements)
        report = self.constraints.evaluate(candidate_state, submission=False)
        if report.has_hard_violation:
            return self._record(
                tool_name=tool_name,
                parameters=parameters,
                succeeded=False,
                status="rejected",
                message="Action rejected by canvas constraints.",
                report=report,
            )

        self.state.elements = working_elements
        if report.suspicious:
            self.state.flagged_suspicious = True
        return self._record(
            tool_name=tool_name,
            parameters=parameters,
            succeeded=True,
            status="applied",
            message="Action applied.",
            report=report,
        )

    def _record(
        self,
        *,
        tool_name: str,
        parameters: dict[str, object],
        succeeded: bool,
        status: str,
        message: str,
        report: ConstraintReport | None = None,
        monitor_reasons: list[str] | None = None,
    ) -> ToolCallRecord:
        step_index = self.state.next_step_index
        record = ToolCallRecord(
            step_index=step_index,
            tool_name=tool_name,
            parameters=parameters,
            status=status,
            cost=self.cost_per_call,
            succeeded=succeeded,
            message=message,
            violation_codes=report.all_codes() if report else [],
            monitor_reasons=list(monitor_reasons or []),
        )
        self.state.tool_history.append(record)
        self.state.record_snapshot(
            step_index=step_index,
            tool_name=tool_name,
            status=status,
            message=message,
        )
        return record

    def _record_invalid_tool_input(
        self,
        *,
        tool_name: str,
        parameters: dict[str, object],
        message: str,
    ) -> ToolCallRecord:
        return self._record(
            tool_name=tool_name,
            parameters=parameters,
            succeeded=False,
            status="error",
            message=message,
            report=ConstraintReport(
                violations=[
                    ConstraintViolation(
                        code="invalid_tool_input",
                        message=message,
                        severity=ConstraintSeverity.HARD,
                    ),
                ],
            ),
        )

    def _missing_element_report(self, element_id: str) -> ConstraintReport:
        return ConstraintReport(
            violations=[
                ConstraintViolation(
                    code="missing_element",
                    message=f"Unknown element_id: {element_id}",
                    severity=ConstraintSeverity.HARD,
                    element_ids=(element_id,),
                ),
            ],
        )

    def _new_element_id(self, element_type: ElementType) -> str:
        prefix = self.id_prefixes[element_type]
        self._element_counter += 1
        return f"{prefix}_{self._element_counter}"

    @staticmethod
    def _normalize_element_type(element_type: ElementType | str) -> ElementType:
        if isinstance(element_type, ElementType):
            return element_type
        return ElementType(str(element_type))
