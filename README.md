# Tokenificator

Turn portrait images into Foundry VTT-ready tokens — fully offline, no subscriptions, no uploads.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Quickstart — pre-built binary

Download the latest release for your platform from the **[Releases page](https://github.com/mordachai/tokenificator/releases/latest)**.

### Windows

1. Download `Tokenificator-...-windows.zip`
2. Unzip anywhere
3. Double-click `Tokenificator.exe`
4. The browser opens automatically at `http://localhost:5000`

### macOS

1. Download `Tokenificator-...-macos.zip`
2. Unzip anywhere
3. **First launch only:** right-click `Tokenificator` → **Open** → confirm in the Gatekeeper dialog (unsigned app warning)
4. After that, double-click to launch normally
5. The browser opens automatically at `http://localhost:5000`

### Linux

1. Download `Tokenificator-...-linux.zip`
2. Unzip anywhere
3. Open a terminal in the folder and run:

   ```bash
   chmod +x Tokenificator
   ./Tokenificator
   ```

4. Open `http://localhost:5000` in your browser

---

Custom masks and frames go in the `masks/` and `frames/` folders next to the binary — they appear in the UI instantly.

---

## Quickstart — from source

```bash
git clone https://github.com/mordachai/tokenificator.git
cd tokenificator
pip install "rembg[cpu]" pillow flask
python app.py
```

Open `http://localhost:5000`.

### Optional extras

**GPU background removal** (NVIDIA/CUDA only — faster for large batches):

```bash
pip install "rembg[gpu]"   # replaces rembg[cpu]
```

**AI face detection** (InsightFace — improves the crop/zoom feature):

```bash
pip install insightface
```

> InsightFace also benefits from a GPU. If you installed `rembg[gpu]`, onnxruntime-gpu is already present and InsightFace will use it automatically.

---

## What it does

Drop in a portrait. Get back a clean token.

- **Removes the background** with an AI model ([rembg](https://github.com/danielgatis/rembg))
- **Applies a mask** — circle, bottom-half, grunge, hex, or your own PNG
- **Overlays a decorative frame** (optional, browse any folder on disk)
- **Outputs WebP** at 256 / 512 / 1024 / 2048 px — portrait and token in one pass

Everything runs locally. The AI model downloads once (~100 MB) and is cached.

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
- **Frame** — decorative ring composited over the token; browse any folder for frames
- **Size** — output canvas in pixels
- **Crop** — optional AI face-detection crop (None / Top / InsightFace)
- **Zoom** — crop tightness: Wide / Medium / Tight
- **Circle mask** — additional circular crop applied on top of the token mask (10–100%, 100% = off)
- **Remove BG** — independent toggles for portrait and token

### Results panel

- Thumbnails appear after each generate run
- Click a thumbnail to preview full-size
- Download individual files or **all as a single ZIP**

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
  --crop insightface \
  --zoom 3 \
  --frame frames/gold-ring.png

# Whole folder
python token_processor.py --folder ./portraits --output-dir ./tokens
```

| Flag | Default | Options |
| --- | --- | --- |
| `--mode` | `both` | `both` `portrait` `token` `nobg` |
| `--size` | `512` | `256` `512` `1024` `2048` |
| `--crop` | `none` | `none` `top` `insightface` |
| `--zoom` | `1` | `1` `3` `5` |
| `--frame` | — | path to an RGBA PNG |
| `--split-y` | `0.5` | 0.0 – 1.0 (frame overflow point) |

---

## Custom masks and frames

Any L-mode (grayscale) PNG dropped into the `masks/` folder appears as a mask option.
Any RGBA PNG or WebP in `frames/` appears as a frame option — or browse any folder on disk via the folder icon next to the Frame picker.
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
