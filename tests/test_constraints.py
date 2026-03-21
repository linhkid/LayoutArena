"""Tests for the constraint engine."""

from __future__ import annotations

import uuid

from layoutarena.env.canvas import LayoutArenaEnv
from layoutarena.env.elements import ElementStyle, ElementType, LayoutElement
from layoutarena.env.models import CanvasSpec, LayoutBrief, ProposedAction

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_env(canvas=None, brief=None):
    canvas = canvas or CanvasSpec()
    brief = brief or LayoutBrief(
        brief_id="t",
        title="T",
        instructions="test",
    )
    return LayoutArenaEnv(brief=brief, canvas=canvas)


def _add(env, element_type, x, y, w, h, style_patch=None):
    """Inject a LayoutElement directly into state, bypassing the tool executor."""
    eid = f"{element_type.value[:3]}_{uuid.uuid4().hex[:8]}"
    style_kwargs = style_patch or {}
    env.state.elements[eid] = LayoutElement(
        element_id=eid,
        element_type=element_type,
        x=x,
        y=y,
        width=w,
        height=h,
        style=ElementStyle(**style_kwargs) if style_kwargs else ElementStyle(),
    )


def _place(env, element_type, x, y, w, h, **kwargs):
    """Use env.step() for tests that need the executor path (e.g. submit_layout)."""
    return env.step(
        ProposedAction(
            tool_name="place_element",
            params={
                "element_type": element_type,
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                **kwargs,
            },
        ),
    )


# ---------------------------------------------------------------------------
# Bounds
# ---------------------------------------------------------------------------


class TestBoundsConstraint:
    def test_element_out_of_canvas_right(self):
        env = _make_env()
        _add(env, ElementType.HEADLINE, 1100, 100, 200, 80)  # x+w=1300 > 1200
        report = env.constraints.evaluate(env.state)
        codes = report.all_codes()
        assert "out_of_bounds" in codes

    def test_element_out_of_canvas_bottom(self):
        env = _make_env()
        _add(env, ElementType.HEADLINE, 100, 750, 200, 100)  # y+h=850 > 800
        report = env.constraints.evaluate(env.state)
        assert "out_of_bounds" in report.all_codes()

    def test_element_negative_origin(self):
        env = _make_env()
        _add(env, ElementType.HEADLINE, -10, 100, 200, 80)
        report = env.constraints.evaluate(env.state)
        assert "out_of_bounds" in report.all_codes()

    def test_element_within_bounds_no_violation(self):
        env = _make_env()
        _add(env, ElementType.HEADLINE, 100, 100, 400, 80)
        report = env.constraints.evaluate(env.state)
        assert "out_of_bounds" not in report.all_codes()


# ---------------------------------------------------------------------------
# Overlap
# ---------------------------------------------------------------------------


class TestOverlapConstraint:
    def test_overlapping_elements_flagged(self):
        env = _make_env()
        _add(env, ElementType.HEADLINE, 100, 100, 300, 100)
        _add(env, ElementType.SUBHEAD, 150, 150, 300, 100)
        report = env.constraints.evaluate(env.state)
        assert "overlap" in report.all_codes()

    def test_adjacent_elements_no_overlap(self):
        env = _make_env()
        _add(env, ElementType.HEADLINE, 100, 100, 300, 100)
        # Subhead starts well below headline bottom (100+100=200), with spacing
        _add(env, ElementType.SUBHEAD, 100, 230, 300, 100)
        report = env.constraints.evaluate(env.state)
        assert "overlap" not in report.all_codes()


# ---------------------------------------------------------------------------
# Minimum spacing
# ---------------------------------------------------------------------------


class TestMinSpacingConstraint:
    def test_too_close_violates_spacing(self):
        env = _make_env()
        _add(env, ElementType.HEADLINE, 100, 100, 300, 100)
        # Subhead starts at y=202 → gap = 202 - 200 = 2 < 24
        _add(env, ElementType.SUBHEAD, 100, 202, 300, 100)
        report = env.constraints.evaluate(env.state)
        assert "min_spacing" in report.all_codes()

    def test_sufficient_spacing_passes(self):
        env = _make_env()
        _add(env, ElementType.HEADLINE, 100, 100, 300, 100)
        _add(env, ElementType.SUBHEAD, 100, 250, 300, 100)  # gap = 50 > 24
        report = env.constraints.evaluate(env.state)
        assert "min_spacing" not in report.all_codes()


# ---------------------------------------------------------------------------
# Hierarchy
# ---------------------------------------------------------------------------


class TestHierarchyConstraint:
    def test_subhead_above_headline_fails(self):
        env = _make_env()
        _add(env, ElementType.HEADLINE, 100, 300, 400, 80)
        _add(env, ElementType.SUBHEAD, 100, 100, 400, 80)  # subhead above headline
        report = env.constraints.evaluate(env.state)
        assert "headline_below_subhead" in report.all_codes()

    def test_headline_above_subhead_passes(self):
        env = _make_env()
        _add(env, ElementType.HEADLINE, 100, 100, 400, 80)
        _add(env, ElementType.SUBHEAD, 100, 300, 400, 80)
        report = env.constraints.evaluate(env.state)
        assert "headline_below_subhead" not in report.all_codes()


# ---------------------------------------------------------------------------
# Logo rules
# ---------------------------------------------------------------------------


class TestLogoConstraint:
    def test_multiple_logos_hard_violation(self):
        env = _make_env()
        _add(env, ElementType.LOGO, 50, 30, 120, 48)
        _add(env, ElementType.LOGO, 300, 30, 120, 48)
        report = env.constraints.evaluate(env.state)
        assert "multiple_logos" in report.all_codes()
        assert report.hard  # is a hard constraint

    def test_oversized_logo_soft_violation(self):
        env = _make_env()
        # width > 25% of 1200 = 300
        _add(env, ElementType.LOGO, 50, 30, 350, 48)
        report = env.constraints.evaluate(env.state)
        assert "oversized_logo" in report.all_codes()
        assert not report.hard  # should be soft, not hard

    def test_logo_too_low_soft_violation(self):
        env = _make_env()
        # y > 25% of 800 = 200
        _add(env, ElementType.LOGO, 50, 250, 120, 48)
        report = env.constraints.evaluate(env.state)
        assert "logo_not_top_aligned" in report.all_codes()

    def test_valid_logo_no_violation(self):
        env = _make_env()
        _add(env, ElementType.LOGO, 50, 30, 120, 48)
        report = env.constraints.evaluate(env.state)
        assert "multiple_logos" not in report.all_codes()
        assert "oversized_logo" not in report.all_codes()


# ---------------------------------------------------------------------------
# Salience
# ---------------------------------------------------------------------------


class TestSalienceConstraint:
    def test_headline_smaller_than_subhead_is_soft(self):
        env = _make_env()
        _add(
            env,
            ElementType.HEADLINE,
            100,
            100,
            400,
            80,
            style_patch={"font_size": 16},
        )  # same default as subhead
        _add(
            env,
            ElementType.SUBHEAD,
            100,
            300,
            400,
            80,
            style_patch={"font_size": 16},
        )
        report = env.constraints.evaluate(env.state)
        assert "weak_visual_hierarchy" in report.all_codes()

    def test_larger_headline_passes(self):
        env = _make_env()
        _add(
            env,
            ElementType.HEADLINE,
            100,
            100,
            400,
            80,
            style_patch={"font_size": 42},
        )
        _add(
            env,
            ElementType.SUBHEAD,
            100,
            300,
            400,
            80,
            style_patch={"font_size": 22},
        )
        report = env.constraints.evaluate(env.state)
        assert "weak_visual_hierarchy" not in report.all_codes()


# ---------------------------------------------------------------------------
# Suspicious patterns
# ---------------------------------------------------------------------------


class TestSuspiciousPatterns:
    def test_tiny_text_flagged(self):
        env = _make_env()
        _add(
            env,
            ElementType.TEXT,
            100,
            100,
            100,
            30,
            style_patch={"font_size": 5},
        )
        report = env.constraints.evaluate(env.state)
        assert "tiny_text" in report.all_codes()

    def test_low_opacity_text_flagged(self):
        env = _make_env()
        _add(
            env,
            ElementType.TEXT,
            100,
            100,
            100,
            30,
            style_patch={"opacity": 0.1},
        )
        report = env.constraints.evaluate(env.state)
        assert "low_opacity_text" in report.all_codes()

    def test_borderline_content_flagged(self):
        env = _make_env()
        # Place text right at the edge (x=5 ≤ 8)
        _add(env, ElementType.TEXT, 5, 100, 100, 30)
        report = env.constraints.evaluate(env.state)
        assert "borderline_content" in report.all_codes()

    def test_normal_text_no_suspicious(self):
        env = _make_env()
        _add(
            env,
            ElementType.TEXT,
            100,
            100,
            200,
            40,
            style_patch={"font_size": 16, "opacity": 1.0},
        )
        report = env.constraints.evaluate(env.state)
        assert not any(v.severity.value == "suspicious" for v in report.violations)


# ---------------------------------------------------------------------------
# Max elements
# ---------------------------------------------------------------------------


class TestMaxElementsConstraint:
    def test_exceeding_max_elements_fails(self):
        env = _make_env(canvas=CanvasSpec(max_elements=2))
        _add(env, ElementType.LOGO, 50, 30, 100, 40)
        _add(env, ElementType.HEADLINE, 50, 100, 400, 80)
        _add(env, ElementType.SUBHEAD, 50, 300, 400, 80)  # 3rd — over limit
        report = env.constraints.evaluate(env.state)
        assert "too_many_elements" in report.all_codes()
        assert report.has_hard_violation


# ---------------------------------------------------------------------------
# Required elements on submission
# ---------------------------------------------------------------------------


class TestRequiredElements:
    def test_missing_required_element_blocks_submit(self, brief):
        env = _make_env(brief=brief)
        _place(env, ElementType.LOGO, 50, 30, 120, 48)
        # Submit without headline / subhead / image
        result = env.step(ProposedAction(tool_name="submit_layout"))
        from layoutarena.env.models import SubmissionResult

        assert isinstance(result, SubmissionResult)
        assert not result.accepted
        assert any(
            v.code == "missing_required_element" for v in result.report.violations
        )

    def test_all_required_elements_accepts(self, brief, nominal_actions):
        env = _make_env(brief=brief)
        from layoutarena.env.models import SubmissionResult

        for action in nominal_actions:
            result = env.step(action)
        assert isinstance(result, SubmissionResult)
        assert result.accepted
