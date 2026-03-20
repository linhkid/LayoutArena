from __future__ import annotations

import base64
import io
import os
import re
from dataclasses import dataclass
from typing import Any, Literal, Optional

from langchain_core.messages import BaseMessage


@dataclass(frozen=True)
class ImageSanitizeStats:
    total_images: int = 0
    changed_images: int = 0
    dropped_images: int = 0
    resized_images: int = 0


def is_gemini_model(model: str) -> bool:
    model_lower = (model or "").lower()
    if model_lower.startswith("gemini/"):
        return True
    if model_lower.startswith("vertex_ai/") and "gemini" in model_lower:
        return True
    if model_lower.startswith("google/") and "gemini" in model_lower:
        return True
    return False


def looks_like_gemini_image_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    # Common Gemini error messages across LiteLLM + Google API variants.
    if "unable to process input image" in msg:
        return True
    if "unable to process input" in msg and "image" in msg:
        return True
    if "invalid_argument" in msg and "process input image" in msg:
        return True
    return False


_DATA_URL_PREFIX = "data:"
_DATA_URL_BASE64_MARKER = ";base64,"


def _parse_data_url(data_url: str) -> Optional[tuple[str, str]]:
    if not isinstance(data_url, str) or not data_url.startswith(_DATA_URL_PREFIX):
        return None
    if _DATA_URL_BASE64_MARKER not in data_url:
        return None
    header, b64 = data_url.split(",", 1)
    # header: data:<mime>;base64
    mime = header[len(_DATA_URL_PREFIX) :].split(";", 1)[0].strip().lower()
    if not mime:
        mime = "application/octet-stream"
    return mime, b64


def _b64decode_loose(b64_data: str) -> bytes:
    # Some datasets include whitespace/newlines; strip them before decoding.
    compact = re.sub(r"\s+", "", b64_data)
    try:
        return base64.b64decode(compact, validate=True)
    except Exception:
        # Fall back to urlsafe decoding / non-validated decode.
        try:
            return base64.urlsafe_b64decode(compact)
        except Exception:
            return base64.b64decode(compact)


def _image_has_alpha(pil_image: Any) -> bool:
    mode = getattr(pil_image, "mode", "")
    if mode in ("RGBA", "LA"):
        return True
    if mode == "P":
        info = getattr(pil_image, "info", {}) or {}
        return "transparency" in info
    return False


def _safe_pil_resample() -> Any:
    try:
        from PIL import Image  # type: ignore

        return getattr(Image, "Resampling", Image).LANCZOS
    except Exception:
        return None


def _encode_image_bytes(
    pil_image: Any,
    fmt: Literal["PNG", "JPEG"],
    **save_kwargs: Any,
) -> bytes:
    buf = io.BytesIO()
    pil_image.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


def sanitize_image_data_url_for_gemini(
    data_url: str,
    *,
    max_edge_px: int,
    max_bytes: int,
    prefer_lossless: bool = True,
) -> tuple[Optional[str], Optional[str], bool]:
    """Return (new_data_url | None, warning | None, resized)."""
    parsed = _parse_data_url(data_url)
    if parsed is None:
        return data_url, None, False
    mime, b64 = parsed

    try:
        raw = _b64decode_loose(b64)
    except Exception as e:  # noqa: BLE001
        return None, f"invalid base64 ({type(e).__name__})", False

    # Lazy import PIL only when needed.
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError  # type: ignore
    except Exception as e:  # noqa: BLE001
        return None, f"PIL not available ({type(e).__name__})", False

    def _open_image(image_bytes: bytes) -> Any:
        im = Image.open(io.BytesIO(image_bytes))
        im = ImageOps.exif_transpose(im)
        im.load()
        return im

    resized = False
    try:
        image = _open_image(raw)
    except UnidentifiedImageError:
        # Heuristic: sometimes content is SVG/XML mislabeled as raster.
        head = raw[:2048].lstrip()
        is_svgish = (
            head.startswith(b"<svg")
            or b"<svg" in head[:512]
            or b'xmlns="http://www.w3.org/2000/svg"' in head
        )
        if mime.endswith("svg+xml") or is_svgish:
            try:
                import cairosvg  # type: ignore

                raw = cairosvg.svg2png(bytestring=raw)
                image = _open_image(raw)
            except ImportError:
                return None, "SVG input (cairosvg not installed)", False
            except Exception as e:  # noqa: BLE001
                return None, f"SVG conversion failed ({type(e).__name__})", False
        else:
            return None, "unrecognized image bytes", False
    except Exception as e:  # noqa: BLE001
        return None, f"image decode failed ({type(e).__name__})", False

    # Resize to keep requests reliably within provider limits.
    if max_edge_px > 0:
        try:
            w, h = image.size
            if max(w, h) > max_edge_px:
                resample = _safe_pil_resample()
                if resample is not None:
                    image.thumbnail((max_edge_px, max_edge_px), resample=resample)
                else:
                    image.thumbnail((max_edge_px, max_edge_px))
                resized = True
        except Exception:
            # If sizing fails, keep original.
            pass

    has_alpha = _image_has_alpha(image)

    # Prefer a canonical, widely-supported encoding.
    out_bytes: Optional[bytes] = None
    out_mime: Optional[str] = None

    # First try PNG (lossless) if requested or alpha is present.
    if prefer_lossless or has_alpha:
        try:
            out_bytes = _encode_image_bytes(image, "PNG")
            out_mime = "image/png"
        except Exception:
            out_bytes = None
            out_mime = None

    # If PNG is too large, fall back to JPEG (no alpha).
    if (
        out_bytes is not None
        and max_bytes > 0
        and len(out_bytes) > max_bytes
        and not has_alpha
    ):
        out_bytes = None
        out_mime = None

    if out_bytes is None:
        try:
            rgb = image.convert("RGB")
            # Try a few qualities to get under max_bytes when configured.
            for quality in (90, 85, 75, 65):
                candidate = _encode_image_bytes(
                    rgb,
                    "JPEG",
                    quality=quality,
                    optimize=True,
                    progressive=False,
                )
                if max_bytes <= 0 or len(candidate) <= max_bytes:
                    out_bytes = candidate
                    out_mime = "image/jpeg"
                    break
            if out_bytes is None:
                out_bytes = candidate  # type: ignore[has-type]
                out_mime = "image/jpeg"
        except Exception as e:  # noqa: BLE001
            return None, f"image encode failed ({type(e).__name__})", resized

    new_b64 = base64.b64encode(out_bytes).decode("ascii")
    new_url = f"data:{out_mime};base64,{new_b64}"

    warning = None
    if mime != out_mime:
        warning = f"mime corrected {mime} -> {out_mime}"
    return new_url, warning, resized


def sanitize_openai_messages_for_gemini(
    messages: list[dict[str, Any]],
    *,
    max_edge_px: int = 2048,
    max_bytes: int = 4_000_000,
    max_images: int = 0,
    prefer_lossless: bool = True,
    drop_images: bool = False,
) -> ImageSanitizeStats:
    """Sanitize OpenAI-format multimodal messages in-place for Gemini."""
    total = 0
    changed = 0
    dropped = 0
    resized = 0

    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue

        new_parts: list[Any] = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "image_url":
                new_parts.append(part)
                continue

            total += 1
            if drop_images or (max_images > 0 and total > max_images):
                dropped += 1
                new_parts.append({"type": "text", "text": "(image omitted)"})
                continue

            image_url = part.get("image_url", {})
            url = image_url.get("url") if isinstance(image_url, dict) else None
            if not isinstance(url, str):
                dropped += 1
                new_parts.append(
                    {"type": "text", "text": "(image omitted: missing url)"},
                )
                continue

            new_url, warning, did_resize = sanitize_image_data_url_for_gemini(
                url,
                max_edge_px=max_edge_px,
                max_bytes=max_bytes,
                prefer_lossless=prefer_lossless,
            )
            if did_resize:
                resized += 1

            if new_url is None:
                dropped += 1
                new_parts.append(
                    {
                        "type": "text",
                        "text": f"(image omitted: {warning or 'invalid'})",
                    },
                )
                continue

            if new_url != url:
                changed += 1

            part["image_url"] = (
                {**image_url, "url": new_url}
                if isinstance(image_url, dict)
                else {"url": new_url}
            )
            new_parts.append(part)

        msg["content"] = new_parts

    return ImageSanitizeStats(
        total_images=total,
        changed_images=changed,
        dropped_images=dropped,
        resized_images=resized,
    )


def sanitize_langchain_messages_for_gemini(
    messages: list[BaseMessage],
    *,
    max_edge_px: int = 2048,
    max_bytes: int = 4_000_000,
    max_images: int = 0,
    prefer_lossless: bool = True,
    drop_images: bool = False,
) -> ImageSanitizeStats:
    """Sanitize LangChain-format multimodal messages in-place for Gemini."""
    total = 0
    changed = 0
    dropped = 0
    resized = 0

    for msg in messages:
        content = getattr(msg, "content", None)
        if not isinstance(content, list):
            continue

        new_parts: list[Any] = []
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "image_url":
                new_parts.append(part)
                continue

            total += 1
            if drop_images or (max_images > 0 and total > max_images):
                dropped += 1
                new_parts.append({"type": "text", "text": "(image omitted)"})
                continue

            image_url = part.get("image_url", {})
            url = image_url.get("url") if isinstance(image_url, dict) else None
            if not isinstance(url, str):
                dropped += 1
                new_parts.append(
                    {"type": "text", "text": "(image omitted: missing url)"},
                )
                continue

            new_url, warning, did_resize = sanitize_image_data_url_for_gemini(
                url,
                max_edge_px=max_edge_px,
                max_bytes=max_bytes,
                prefer_lossless=prefer_lossless,
            )
            if did_resize:
                resized += 1

            if new_url is None:
                dropped += 1
                new_parts.append(
                    {
                        "type": "text",
                        "text": f"(image omitted: {warning or 'invalid'})",
                    },
                )
                continue

            if new_url != url:
                changed += 1

            part["image_url"] = (
                {**image_url, "url": new_url}
                if isinstance(image_url, dict)
                else {"url": new_url}
            )
            new_parts.append(part)

        msg.content = new_parts  # type: ignore[attr-defined]

    return ImageSanitizeStats(
        total_images=total,
        changed_images=changed,
        dropped_images=dropped,
        resized_images=resized,
    )


def get_gemini_sanitize_mode() -> Literal["off", "auto", "always"]:
    raw = os.getenv("MPS_GEMINI_SANITIZE_IMAGES", "auto").strip().lower()
    if raw in {"0", "false", "no", "off", "disable", "disabled"}:
        return "off"
    if raw in {"1", "true", "yes", "on", "always"}:
        return "always"
    return "auto"
