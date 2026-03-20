# Render API Reference

This document describes the JSON → PNG rendering API exposed by the Next.js app.

Base URL (dev): http://localhost:3000

If the dev server auto-selects another port (e.g., 3001), adjust URLs accordingly.

## Endpoints

### POST /api/render/preview
Render a single JSON payload and return a base64 PNG data URL.

- Content-Type: application/json
- Request body: a JSON object representing the template. If your object does not contain a top-level `data` property, it will be wrapped as `{ data: <yourObject> }` automatically.

Minimal example payload:

```json
{
  "data": {
    "width": 1080,
    "height": 1080,
    "background": "#ffffff",
    "children": []
  }
}
```

Response:

```json
{ "dataUrl": "data:image/png;base64,...." }
```

Example (curl → file):

```bash
curl -sS -X POST \
  -H 'Content-Type: application/json' \
  -d '{"data":{"width":1080,"height":1080,"background":"#fff","children":[]}}' \
  http://localhost:3000/api/render/preview \
| jq -r .dataUrl \
| sed 's#^data:image/png;base64,##' \
| base64 --decode > preview.png
```

Notes/limits:
- Max body size: ~5MB
- Renders at the canvas’ native size (1080×1080 unless your JSON sets otherwise)

### POST /api/render/batch
Upload multiple JSON files and receive a ZIP of PNG renders.

- Content-Type: multipart/form-data
- Form field: `files` (repeatable). Each item must be a `.json` file containing an object as described above.
- Response: `application/zip` stream, filename: `renders.zip`
- Output names: derived from each JSON filename, replacing `.json` with `.png` (or `render_N.png` if unknown)

Example:

```bash
curl -sS -X POST \
  -F 'files=@/path/layout1.json' \
  -F 'files=@/path/layout2.json' \
  http://localhost:3000/api/render/batch \
  -o renders.zip
```

Notes/limits:
- Max file size per JSON: ~10MB
- Total request size depends on your server limits

## Template structure (overview)
The renderer expects an object with:

```json
{
  "data": {
    "width": 1080,
    "height": 1080,
    "background": "#ffffff",
    "children": [
      // elements in back-to-front order (or use `index` for z-order)
    ]
  }
}
```

Common child element fields (subset):
- visibility/z-index: `visible: true`, `index: 0`
- geometry: `x`, `y`, `width`, `height`
- transform: `rotation`, `flipHorizontal`, `flipVertical`, `opacity`
- corners: `cornerRadiusTopLeft`, `cornerRadiusTopRight`, `cornerRadiusBottomRight`, `cornerRadiusBottomLeft`
- fills/strokes: `fill`, `stroke`, `strokeWidth`, `dash`
- crop (images): `cropX`, `cropY`, `cropWidth`, `cropHeight` (0..1 fractional or absolute px)
- text: `text`, `richTextArr`, `textFill`, `fontFamily`, `fontStyle`, `fontSize`, `lineHeight`, `align`, `verticalAlign`, `textTransform`, `s3FilePath` (font URL)
  - Text background: `fill` (solid color or 'transparent'), `gradient` (optional gradient object)
  - Rounded corners: `cornerRadiusTopLeft`, `cornerRadiusTopRight`, `cornerRadiusBottomRight`, `cornerRadiusBottomLeft`
- image/logo: `src`, optional `overlayFill` + `alpha`
- CTA: `elementType: 'cta'`, uses background fill + auto-fit text
- Line: `elementType: 'line'`, `points: [x0,y0,x1,y1,...]`

Types (by discriminator):
- Images: `type: 'image' | 'svg'`
- Text: `type: 'text'` or `elementType: 'headline'`
- Shapes/lines: `type: 'shape'` or `elementType: 'graphicShape' | 'line'`
- Logo: `elementType: 'logo'` (special padding handling)
- CTA: `elementType: 'cta'`

Tip: Remote assets (images/fonts) must be publicly reachable with CORS enabled.

## Errors
- 400 Invalid JSON or missing files
- 405 Method not allowed (use POST)
- 500 General rendering error (see server logs)

## Implementation details
- Rendering is done by navigating a headless browser to `public/renderer.html`, injecting your JSON, and reading `canvas.toDataURL()`.
- The renderer attempts to load custom fonts via `FontFace`; if unavailable, it falls back to system fonts.
