# Minimal Layout Generation Pipeline

LLM-driven layout generation: give it a design brief and assets, get back a rendered layout.

## How it works

1. **Asset library** (`asset_library.py`) — loads images/logos/shapes + fonts/colors from `assets/`
2. **LLM** (`llm.py`) — sends assets + brief to an LLM, gets back Python code
3. **Tools** (`tools.py`) — `HumanToolLayoutTransformer` executes the generated code to build a layout JSON
4. **Renderer** (`renderer.py`) — sends layout JSON to `api-render/` (Next.js) to produce a PNG
5. **Iterate** — renders the result, feeds it back to the LLM for refinement (default: 3 iterations)

## Usage

```bash
# Setup
cp .env.example .env  # add your API key
cd api-render && npm install && cd ..
pip install requests python-dotenv litellm

# Run
python main.py "Movie night flyer with bold headline and cinema vibes"

# Options
python main.py "Your brief" \
  --model gemini/gemini-3.1-flash-lite-preview \
  --width 1920 --height 1080 \
  --background "#ffffff" \
  --temperature 0.7 \
  --iterations 3 \
  --output ./my-output
```

Output goes to `runs/<timestamp>/` with each iteration's `code.py`, `layout.json`, and `render.png`.

## Files

| File | Purpose |
|---|---|
| `main.py` | CLI entry point + pipeline loop |
| `tools.py` | Layout transformer API (add/move/resize/style/group elements) |
| `llm.py` | LLM client (via litellm) |
| `renderer.py` | Calls api-render server to produce PNGs |
| `asset_library.py` | Loads and categorizes assets |
| `extract_assets.py` | Extracts assets from Obello layout JSON |
| `api-render/` | Next.js rendering server |
| `assets/` | Asset files (images, fonts, colors) |
