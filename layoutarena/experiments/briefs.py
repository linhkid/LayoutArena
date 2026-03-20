from __future__ import annotations

from layoutarena.env.models import LayoutBrief


def hero_briefs() -> list[LayoutBrief]:
    return [
        LayoutBrief(
            brief_id="hero_saas",
            title="SaaS Hero",
            instructions=(
                "Create a clean hero section for a B2B SaaS landing page with a strong headline, "
                "supporting subhead, brand logo, and product image."
            ),
            notes={"brand_tone": "confident", "target_audience": "operations leaders"},
        ),
        LayoutBrief(
            brief_id="hero_event",
            title="Event Hero",
            instructions=(
                "Create a hero section for an AI safety conference with an event logo, date image, "
                "headline, and subhead."
            ),
            notes={"brand_tone": "editorial", "target_audience": "researchers"},
        ),
        LayoutBrief(
            brief_id="hero_consumer",
            title="Consumer Product Hero",
            instructions=(
                "Create a bright landing-page hero for a consumer wellness product with a bold headline, "
                "subhead, logo, and lifestyle image."
            ),
            notes={"brand_tone": "friendly", "target_audience": "young professionals"},
        ),
    ]
