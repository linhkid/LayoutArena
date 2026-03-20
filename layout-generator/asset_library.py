"""Query interface over the extracted asset library."""

from __future__ import annotations

import json
from pathlib import Path

ASSETS_DIR = Path(__file__).parent / "assets"


class AssetLibrary:
    def __init__(self, assets_dir: Path = ASSETS_DIR):
        self.dir = assets_dir
        self.manifest = json.loads((assets_dir / "manifest.json").read_text())

    @property
    def assets(self) -> list[dict]:
        return self.manifest["assets"]

    @property
    def fonts(self) -> list[str]:
        return self.manifest["fonts"]

    @property
    def colors(self) -> list[str]:
        return self.manifest["colors"]

    @property
    def text_samples(self) -> list[dict]:
        return self.manifest["text_samples"]

    @property
    def canvases(self) -> list[dict]:
        return self.manifest["canvases"]

    def by_category(self, category: str) -> list[dict]:
        return [a for a in self.assets if a["category"] == category]

    @property
    def images(self) -> list[dict]:
        return self.by_category("images")

    @property
    def logos(self) -> list[dict]:
        return self.by_category("logos")

    @property
    def shapes(self) -> list[dict]:
        return self.by_category("shapes")

    def get_asset(self, asset_id: str) -> dict | None:
        return next((a for a in self.assets if a["id"] == asset_id), None)

    def get_data_url(self, asset_id: str) -> str | None:
        asset = self.get_asset(asset_id)
        return asset["data_url"] if asset else None

    def describe(self) -> str:
        """Return a concise description of the library for LLM prompts."""
        lines = [f"Asset Library ({len(self.assets)} visual assets):"]
        for cat in ["images", "logos", "shapes"]:
            items = self.by_category(cat)
            if items:
                lines.append(f"\n  {cat.upper()} ({len(items)}):")
                for a in items:
                    lines.append(f"    - {a['id']}: {a['original_width']:.0f}x{a['original_height']:.0f}")
        lines.append(f"\n  FONTS ({len(self.fonts)}): {', '.join(self.fonts)}")
        lines.append(f"\n  COLORS ({len(self.colors)}): {', '.join(self.colors)}")
        lines.append(f"\n  TEXT SAMPLES ({len(self.text_samples)}):")
        for t in self.text_samples[:10]:
            lines.append(f"    - [{t['elementType']}] \"{t['text'][:50]}\" ({t['font']}, {t['fontSize']:.1f}px)")
        if len(self.text_samples) > 10:
            lines.append(f"    ... and {len(self.text_samples) - 10} more")
        return "\n".join(lines)
