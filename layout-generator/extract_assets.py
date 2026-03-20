"""Extract assets (images, logos, shapes, fonts, colors) from dataset samples into a library."""

import base64
import json
import os
import pickle
import sys
from pathlib import Path

DATASET_DIR = Path(__file__).parent.parent / "datasets" / "preprocessed_crello" / "test-slim"
ASSETS_DIR = Path(__file__).parent / "assets"


def decode_data_url(data_url: str) -> tuple[str, bytes]:
    """Return (mime_type, raw_bytes) from a data URL."""
    header, b64 = data_url.split(",", 1)
    mime = header.split(":")[1].split(";")[0]
    return mime, base64.b64decode(b64)


def extract_sample(path: Path, manifest: dict):
    """Extract all assets from one sample JSON into the library."""
    data = json.loads(path.read_text())
    sample_id = path.stem

    # Canvas metadata
    manifest["canvases"].append({
        "sample": sample_id,
        "width": data["width"],
        "height": data["height"],
        "background": data.get("background"),
    })

    for el in data.get("children", []):
        etype = el.get("elementType", el.get("type", "unknown"))
        el_id = el["id"]
        asset_id = f"{sample_id}_{el_id}"

        # Extract visual assets (images, shapes, logos)
        if "src" in el and el["src"].startswith("data:"):
            mime, raw = decode_data_url(el["src"])
            ext = "png" if "png" in mime else "svg" if "svg" in mime else "bin"
            category = {"logo": "logos", "image": "images", "shape": "shapes"}.get(etype, "shapes")

            filename = f"{asset_id}.{ext}"
            (ASSETS_DIR / category).mkdir(exist_ok=True)
            (ASSETS_DIR / category / filename).write_bytes(raw)

            manifest["assets"].append({
                "id": asset_id,
                "category": category,
                "filename": f"{category}/{filename}",
                "original_width": el["width"],
                "original_height": el["height"],
                "data_url": el["src"],  # keep for easy embedding
            })

        # Extract text/font info
        if el.get("type") == "text":
            font = el.get("fontFamily", "Arial")
            if font not in manifest["fonts"]:
                manifest["fonts"].append(font)
            color = el.get("textFill", "#000000")
            if color not in manifest["colors"]:
                manifest["colors"].append(color)
            manifest["text_samples"].append({
                "id": asset_id,
                "text": el["text"],
                "font": font,
                "fontSize": el.get("fontSize"),
                "elementType": etype,
                "color": color,
            })

    # Extract background colors
    bg = data.get("background")
    if bg and bg not in manifest["colors"]:
        manifest["colors"].append(bg)


def load_fonts_pickle() -> dict | None:
    """Load fonts.pickle from env path or HuggingFace."""
    path = os.environ.get("CRELLO_FONTS_PICKLE_PATH")
    if not path:
        try:
            import huggingface_hub
            path = huggingface_hub.hf_hub_download(
                repo_id="cyberagent/crello",
                filename="resources/fonts.pickle",
                repo_type="dataset",
                revision="5.0.0",
                cache_dir=os.environ.get("HF_HOME", "/tmp/hf_cache"),
            )
        except Exception as e:
            print(f"Could not download fonts.pickle: {e}")
            return None
    with open(path, "rb") as f:
        return pickle.load(f)


def extract_fonts(font_names: list[str], fonts_index: dict, manifest: dict):
    """Extract font files for the given font names from fonts.pickle."""
    fonts_dir = ASSETS_DIR / "fonts"
    fonts_dir.mkdir(exist_ok=True)

    for name in font_names:
        variants = fonts_index.get(name)
        if not variants:
            print(f"  Font '{name}' not found in fonts.pickle")
            continue
        for v in variants:
            ext = Path(v["path"]).suffix or ".ttf"
            weight = v.get("fontWeight", "regular")
            style = v.get("fontStyle", "regular")
            safe_name = name.replace(" ", "_")
            filename = f"{safe_name}_{weight}_{style}{ext}"
            (fonts_dir / filename).write_bytes(v["bytes"])

            font_data_url = f"data:font/{ext.lstrip('.')};base64,{base64.b64encode(v['bytes']).decode()}"
            manifest["font_files"].append({
                "family": name,
                "weight": weight,
                "style": style,
                "filename": f"fonts/{filename}",
                "data_url": font_data_url,
            })
    print(f"  Extracted {len(manifest['font_files'])} font variants")


def main():
    dataset_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DATASET_DIR
    ASSETS_DIR.mkdir(exist_ok=True)

    manifest = {"assets": [], "fonts": [], "font_files": [], "colors": [], "text_samples": [], "canvases": []}

    for path in sorted(dataset_dir.glob("*.json")):
        print(f"Extracting {path.name}...")
        extract_sample(path, manifest)

    # Extract actual font files
    print("Loading fonts.pickle...")
    fonts_index = load_fonts_pickle()
    if fonts_index:
        extract_fonts(manifest["fonts"], fonts_index, manifest)
    else:
        print("  Skipping font extraction (no fonts.pickle)")

    (ASSETS_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Done. {len(manifest['assets'])} assets, {len(manifest['fonts'])} fonts ({len(manifest['font_files'])} files), {len(manifest['colors'])} colors")
    print(f"Assets written to {ASSETS_DIR}")


if __name__ == "__main__":
    main()
