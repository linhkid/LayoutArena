"""Tests for TrajectoryMonitor: signals, escalation, large style-shift."""
from __future__ import annotations

from layoutarena.control.monitor import MonitorConfig, TrajectoryMonitor
from layoutarena.env.elements import ElementType
from layoutarena.env.models import (
    CanvasSpec,
    LayoutBrief,
    LayoutState,
    ProposedAction,
    ToolCallRecord,
)


def _state():
    canvas = CanvasSpec()
    brief = LayoutBrief(brief_id="t", title="T", instructions="test")
    return LayoutState(brief=brief, canvas=canvas)


def _place_action(element_type, x, y, w, h, **kwargs):
    return ProposedAction(
        tool_name="place_element",
        params={"element_type": element_type, "x": x, "y": y,
                "width": w, "height": h, **kwargs},
    )


def _style_action(element_id, **style_patch):
    return ProposedAction(
        tool_name="style_element",
        params={"element_id": element_id, "style_patch": style_patch},
    )


def _failed_record():
    return ToolCallRecord(
        step_index=1, tool_name="place_element",
        parameters={}, status="rejected", cost=1, succeeded=False,
    )


class TestBorderProbeSignal:
    def test_near_left_edge_flagged(self):
        monitor = TrajectoryMonitor()
        state = _state()
        action = _place_action(ElementType.SHAPE, 5, 100, 80, 60)
        decision = monitor.suggest_decision(state, action)
        assert any("border" in r.lower() for r in decision.reasons)

    def test_mid_canvas_not_flagged(self):
        monitor = TrajectoryMonitor()
        state = _state()
        action = _place_action(ElementType.SHAPE, 200, 200, 80, 60)
        decision = monitor.suggest_decision(state, action)
        assert not any("border" in r.lower() for r in decision.reasons)


class TestTinyTextSignal:
    def test_tiny_font_flagged(self):
        monitor = TrajectoryMonitor()
        state = _state()
        action = _place_action(ElementType.TEXT, 200, 200, 80, 30,
                                style_patch={"font_size": 4})
        decision = monitor.suggest_decision(state, action)
        assert any("tiny" in r.lower() for r in decision.reasons)

    def test_normal_font_not_flagged(self):
        monitor = TrajectoryMonitor()
        state = _state()
        action = _place_action(ElementType.TEXT, 200, 200, 80, 30,
                                style_patch={"font_size": 18})
        decision = monitor.suggest_decision(state, action)
        assert not any("tiny" in r.lower() for r in decision.reasons)


class TestLowOpacitySignal:
    def test_low_opacity_flagged(self):
        monitor = TrajectoryMonitor()
        state = _state()
        action = _place_action(ElementType.TEXT, 200, 200, 80, 30,
                                style_patch={"opacity": 0.1})
        decision = monitor.suggest_decision(state, action)
        assert any("opacity" in r.lower() for r in decision.reasons)

    def test_full_opacity_not_flagged(self):
        monitor = TrajectoryMonitor()
        state = _state()
        action = _place_action(ElementType.TEXT, 200, 200, 80, 30,
                                style_patch={"opacity": 1.0})
        decision = monitor.suggest_decision(state, action)
        assert not any("opacity" in r.lower() for r in decision.reasons)


class TestOscillationSignal:
    def test_repeated_identical_action_flagged(self):
        monitor = TrajectoryMonitor()
        state = _state()
        action = _place_action(ElementType.SHAPE, 200, 200, 80, 60)
        # First call — not oscillating
        monitor.suggest_decision(state, action)
        monitor.observe_outcome(state, action, _failed_record())
        # Second identical call — should be flagged as oscillation
        decision = monitor.suggest_decision(state, action)
        assert any("repeat" in r.lower() or "oscillat" in r.lower()
                   for r in decision.reasons)


class TestLargeStyleShiftSignal:
    def _state_with_headline(self):
        """Return a state that has a headline element already placed."""
        from layoutarena.env.canvas import LayoutArenaEnv
        canvas = CanvasSpec()
        brief = LayoutBrief(brief_id="t", title="T", instructions="test")
        env = LayoutArenaEnv(brief=brief, canvas=canvas)
        env.step(_place_action(
            ElementType.HEADLINE, 80, 140, 400, 80,
            style_patch={"font_size": 40},
        ))
        return env.state

    def test_large_font_drop_flagged(self):
        state = self._state_with_headline()
        monitor = TrajectoryMonitor()
        headline_id = next(iter(state.elements))
        # Drop font_size from 40 → 10 (75% reduction — above 50% threshold)
        action = _style_action(headline_id, font_size=10)
        decision = monitor.suggest_decision(state, action)
        assert any("font" in r.lower() for r in decision.reasons)

    def test_small_font_adjustment_not_flagged(self):
        state = self._state_with_headline()
        monitor = TrajectoryMonitor()
        headline_id = next(iter(state.elements))
        # Change font_size from 40 → 44 (10% — below 50% threshold)
        action = _style_action(headline_id, font_size=44)
        decision = monitor.suggest_decision(state, action)
        assert not any("font" in r.lower() and "shift" in r.lower()
                       for r in decision.reasons)

    def test_large_opacity_drop_flagged(self):
        state = self._state_with_headline()
        monitor = TrajectoryMonitor()
        headline_id = next(iter(state.elements))
        # Drop opacity from 1.0 → 0.5 (0.5 drop — above 0.4 threshold)
        action = _style_action(headline_id, opacity=0.5)
        decision = monitor.suggest_decision(state, action)
        assert any("opacity" in r.lower() for r in decision.reasons)

    def test_style_action_on_unknown_element_does_not_crash(self):
        state = _state()
        monitor = TrajectoryMonitor()
        action = _style_action("nonexistent_id", font_size=10)
        # Should not raise; large-shift check only fires if element exists
        decision = monitor.suggest_decision(state, action)
        assert decision is not None


class TestRepeatFailedRegion:
    def test_region_blocked_after_repeat_failures(self):
        config = MonitorConfig(repeat_failure_limit=2)
        monitor = TrajectoryMonitor(config=config)
        state = _state()
        action = _place_action(ElementType.SHAPE, 200, 200, 80, 60)

        for _ in range(2):
            monitor.suggest_decision(state, action)
            monitor.observe_outcome(state, action, _failed_record())

        decision = monitor.suggest_decision(state, action)
        assert any("repeat" in r.lower() or "region" in r.lower()
                   for r in decision.reasons)
