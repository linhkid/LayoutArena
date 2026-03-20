# Render API

A Next.js app to render PNG images from JSON templates using a headless browser and an HTML5 canvas renderer.

## Endpoints

### POST /api/render/preview
- Purpose: Render a single JSON payload and return a base64 PNG data URL.
- Content-Type: application/json
- Request body: a JSON object with the `data` shape expected by the renderer.
- Response:
  - 200: `{ "dataUrl": "data:image/png;base64,..." }`
  - 400/500 with `{ error: string }` on failure

Example (curl):

```bash
curl -sS -X POST \
  -H 'Content-Type: application/json' \
  -d '{"data":{"width":1080,"height":1080,"background":"#fff","children":[]}}' \
  http://localhost:3000/api/render/preview | jq -r .dataUrl | sed 's#^data:image/png;base64,##' | base64 --decode > preview.png
```

### POST /api/render/batch
- Purpose: Upload multiple JSON files and receive a ZIP of PNG renders.
- Content-Type: multipart/form-data
- Form field: `files` (one or more .json files)
- Response:
  - 200: `application/zip` streamed response (attachment: renders.zip)
  - 400/500 on failure

Example (curl):

```bash
curl -sS -X POST \
  -F 'files=@/path/layout1.json' \
  -F 'files=@/path/layout2.json' \
  http://localhost:3000/api/render/batch \
  -o renders.zip
```

## How it works
- A public page `public/renderer.html` contains the canvas drawing logic (adapted from your `index.html`).
- API routes start a headless Chromium (Puppeteer), navigate to `/renderer.html`, inject the JSON, and read the PNG via `canvas.toDataURL()`.

## Local development

```bash
npm install
npm run dev
# open http://localhost:3000
```

The landing page lets you preview a JSON and batch upload `.json` files to get a zip.

## Notes
- For servers where Chromium sandbox isn't available, `--no-sandbox` is already set.
- If your template loads remote fonts or images, ensure they are CORS-accessible.
- To deploy on platforms with Puppeteer, verify that Chromium can launch (or use alternatives like Playwright).
