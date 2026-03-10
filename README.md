# Tokenificator

Turn portrait images into Foundry VTT-ready tokens — fully offline, no subscriptions, no uploads.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## What it does

Drop in a portrait. Get back a clean token.

- **Removes the background** with an AI model ([rembg](https://github.com/danielgatis/rembg))
- **Applies a mask** — circle, bottom-half, grunge, hex, or your own PNG
- **Overlays a decorative frame** (optional)
- **Outputs WebP** at 256 / 512 / 1024 / 2048 px — portrait and token in one pass

Everything runs locally. The AI model downloads once (~100 MB) and is cached.

---

## Quickstart — .exe

1. Download the latest release: **[Tokenificator-v1.0-windows.zip](https://github.com/mordachai/tokenificator/releases/latest)**
2. Unzip anywhere
3. Double-click `Tokenificator.exe`
4. The browser opens automatically at `http://localhost:5000`

Custom masks and frames go in the `masks/` and `frames/` folders next to the exe — they appear in the UI instantly.

---

## Quickstart — from source

```bash
git clone https://github.com/mordachai/tokenificator.git
cd tokenificator
pip install rembg pillow flask
python main.py
```

Open `http://localhost:5000`.

Optional face-detection backends:

```bash
pip install mediapipe    # lightweight, auto-downloads model
pip install insightface  # more accurate, heavier
```

---

## Web UI

The UI is a single page with three columns:

```text
[ Preview canvas ]  [ Controls ]  [ Results ]
```

### Preview canvas

- Shows the image as you work — drag to pan, scroll to zoom
- The mask is a fixed window; the image moves behind it
- **Remove BG & Preview** strips the background and locks in the prepared image
- **Apply Mask** bakes the current mask shape into the image
- **Reset** restores the original raw image and clears all adjustments

### Controls

- **Input** — single file or folder (browse buttons open a native file picker)
- **Output** — leave empty to save next to the source
- **Mode** — Portrait + Token / Portrait only / Token only / BG removed only
- **Mask** — shape applied to the token
- **Frame** — decorative ring composited over the token (character overflows above it)
- **Size** — output canvas in pixels
- **Crop** — optional AI face-detection crop (None / Top / MediaPipe / InsightFace)
- **Zoom** — crop tightness: Wide / Medium / Tight
- **Remove BG** — independent toggles for portrait and token

### Results panel

- Thumbnails appear after each generate run
- Click a thumbnail to preview full-size
- Download individual files or all at once

---

## Outputs

Each source image produces WebP files depending on the mode:

| Mode | Files |
| --- | --- |
| Portrait + Token | `name.webp` + `name_token.webp` |
| Portrait | `name.webp` |
| Token | `name_token.webp` |
| BG removed | `name.webp` (original size, transparent) |

Portraits are lossy WebP (quality 90). Tokens are lossless to preserve hard mask edges.

---

## CLI

```bash
# Single file
python token_processor.py portrait.jpg

# Single file with options
python token_processor.py portrait.jpg \
  --output-dir ./tokens \
  --mode both \
  --size 512 \
  --crop mediapipe \
  --zoom 3 \
  --frame frames/gold-ring.png

# Whole folder
python token_processor.py --folder ./portraits --output-dir ./tokens
```

| Flag | Default | Options |
| --- | --- | --- |
| `--mode` | `both` | `both` `portrait` `token` `nobg` |
| `--size` | `512` | `256` `512` `1024` `2048` |
| `--crop` | `none` | `none` `top` `mediapipe` `insightface` |
| `--zoom` | `1` | `1` `3` `5` |
| `--frame` | — | path to an RGBA PNG |
| `--split-y` | `0.5` | 0.0 – 1.0 (frame overflow point) |

---

## Custom masks and frames

Any L-mode (grayscale) PNG dropped into the `masks/` folder appears as a mask option.
Any RGBA PNG in `frames/` appears as a frame option.
Restart not required — the UI reads the folders on every picker open.

---

## Building

```bash
pip install pyinstaller
build.bat
```

Outputs to `dist\Tokenificator\`. Distribute the entire folder — users double-click the exe.
Masks and frames sit next to it so they can add their own.

---

## License

MIT — free to use, modify, and distribute.
