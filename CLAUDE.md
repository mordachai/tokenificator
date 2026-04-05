# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

RPG Token Processor — a Python CLI tool that converts portrait images into Foundry VTT-ready tokens. Runs fully offline after the first use.

## Setup & Running

```bash
# Install dependencies (one-time)
pip install rembg pillow flask

# Optional face-detection backend
pip install insightface      # for --crop insightface

# Web UI (recommended)
python app.py            # → open http://localhost:5000

# CLI — single file
python token_processor.py portrait.jpg
python token_processor.py portrait.jpg --output-dir ./tokens --mode both --size 512 --crop insightface --zoom 3 --frame frames/gold-ring.png --split-y 0.5

# CLI — whole folder
python token_processor.py --folder ./portraits --output-dir ./tokens
```

> First run downloads the rembg AI segmentation model (~100 MB, cached locally).

## File Structure

```text
token_processor.py   — image pipeline + CLI
face_crop.py         — face-detection / smart-crop backends
app.py               — Flask server (UI backend)
templates/
  index.html         — local web UI
masks/               — PNG mask files (L-mode) selected at runtime
models/              — auto-downloaded AI model files (e.g. blaze_face_short_range.tflite)
mode_images/         — UI preview images for each output mode
zoom_images/         — UI preview images for each zoom level
```

## Architecture

### Outputs per image

Each source image produces WebP files depending on `--mode`:

| Mode | Output files |
| ---- | ----------- |
| `both` (default) | `{stem}.webp` (portrait) + `{stem}_token.webp` (masked token) |
| `portrait` | `{stem}.webp` only |
| `token` | `{stem}_token.webp` only |
| `nobg` | `{stem}.webp` — background removed, original dimensions |

Portraits are saved as lossy WebP (`quality=90`, `alpha_quality=100`). Tokens are saved **lossless** to preserve hard mask edges.

### Image pipeline (`token_processor.py`)

`remove_background` runs **once** per source image; portrait and token branches share the same `nobg` base. Background removal is skipped automatically if the source already has a meaningful alpha channel.

1. `remove_background(img)` — rembg AI strips background → RGBA
2. **Portrait branch** — optional `smart_crop(..., zoom=1)` (always loose), then `scale_to_canvas(top_bias=True)`
3. **Token branch** — optional `smart_crop(..., zoom=crop_zoom)`, then `scale_to_canvas(top_bias=False)`, then `apply_mask`
4. `apply_mask` — intersects an L-mode PNG mask with the image alpha; zeroes out RGB on fully transparent pixels to avoid premultiplied-alpha bleed in PIXI.js / Foundry WebGL

**Key constants:**

```python
DEFAULT_SIZE  = 512
VALID_SIZES   = (256, 512, 1024, 2048)
WEBP_QUALITY  = 90
MASK_FILE     = masks/bottom-half.png   # default; runtime-selectable via --mask or UI
SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}
```

### Path resolution (`_paths.py`)

`BUNDLE_DIR` (read-only assets — templates, mode/zoom images) and `DATA_DIR` (writable — masks, frames, tmp) resolve differently depending on context:

- **Dev / from source**: both point to the project root (`__file__` parent)
- **Frozen (PyInstaller)**: `BUNDLE_DIR` = `sys._MEIPASS` (unpacked bundle), `DATA_DIR` = folder containing the `.exe`

All path-sensitive code imports from `_paths` so it works in both contexts.

### Face crop (`face_crop.py`)

`smart_crop(img, backend, zoom)` — called by `process_file`; returns a cropped PIL Image.

- `"none"` — passthrough
- `"top"` — simple top-square crop, no AI
- `"insightface"` — InsightFace RetinaFace (`buffalo_sc`, CPU); singleton loaded once per process

AI backends fall back to `top` crop if no face is detected. `ImportError` (backend not installed) is re-raised to surface to the caller.

Zoom levels control padding around the detected face bounding box:

- `1` = loose (head + torso)
- `3` = medium (head + shoulders)
- `5` = strong (bust / upper chest)

### Flask server (`app.py`)

| Endpoint | Description |
| -------- | ----------- |
| `GET /` | Serves `templates/index.html` |
| `GET /masks` | Lists available mask PNGs → `{"masks": [...]}` |
| `GET /masks/<filename>` | Serves a mask PNG for UI preview |
| `GET /frames` | Lists available frame PNGs/WebPs → `{"frames": [...]}` |
| `GET /frames/<filename>` | Serves a frame from `frames/` |
| `GET /list-dir-frames?dir=...` | Lists PNG/WebP files in any folder on disk |
| `GET /mode-images/<name>` | Serves mode preview images |
| `GET /zoom-images/<name>` | Serves zoom preview images |
| `GET /serve?path=...` | Serves any local output file for in-page preview |
| `GET /tmp/<filename>` | Serves a temp file from `TMP_DIR` |
| `GET /open-folder` | Native OS folder picker (tkinter) → `{"path": "..."}` |
| `GET /open-file` | Native OS file picker (tkinter) → `{"path": "..."}` |
| `POST /prepare` | Strips background from one image; saves PNG to `tmp/`; returns `{url, path, width, height}` |
| `POST /upload-temp` | Accepts image blob upload; saves to `tmp/`; returns `{path, url, name}` |
| `POST /process` | Runs the full pipeline; body: `{input, output, mode, mask, size, crop_backend, crop_zoom, remove_bg_portrait, remove_bg_token, frame, split_y, circle_mask, transform, rembg_model}` |
| `POST /download-zip` | Bundles a list of local files into a ZIP; body: `{files: [{path, name}]}` |

**`transform` object** (passed to `/process` for interactive canvas adjustments): `{nobg_path, offset_x, offset_y, scale, flip_h}`. If `nobg_path` points to a stale temp file, the server falls back to running rembg automatically.
