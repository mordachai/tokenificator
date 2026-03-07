# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

RPG Token Processor — a Python CLI tool that converts portrait images into Foundry VTT-ready tokens. Runs fully offline after the first use.

## Setup & Running

```bash
# Install dependencies (one-time)
pip install rembg pillow flask

# Optional face-detection backends
pip install mediapipe        # for --crop mediapipe
pip install insightface      # for --crop insightface

# Web UI (recommended)
python app.py            # → open http://localhost:5000

# CLI — single file
python token_processor.py portrait.jpg
python token_processor.py portrait.jpg --output-dir ./tokens --mode both --size 512 --crop mediapipe --zoom 3

# CLI — whole folder
python token_processor.py --folder ./portraits --output-dir ./tokens
```

> First run downloads the rembg AI segmentation model (~100 MB, cached locally). MediaPipe also auto-downloads its model (~0.8 MB) on first use to `models/`.

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
```

### Face crop (`face_crop.py`)

`smart_crop(img, backend, zoom)` — called by `process_file`; returns a cropped PIL Image.

- `"none"` — passthrough
- `"top"` — simple top-square crop, no AI
- `"mediapipe"` — MediaPipe FaceDetector; auto-downloads TFLite model to `models/`
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
| `GET /mode-images/<name>` | Serves mode preview images |
| `GET /zoom-images/<name>` | Serves zoom preview images |
| `GET /serve?path=...` | Serves any local output file for in-page preview |
| `GET /open-folder` | Native OS folder picker (tkinter) → `{"path": "..."}` |
| `GET /open-file` | Native OS file picker (tkinter) → `{"path": "..."}` |
| `POST /process` | Runs the pipeline; body: `{input, output, mode, mask, size, crop_backend, crop_zoom, remove_bg_portrait, remove_bg_token}` |
