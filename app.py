#!/usr/bin/env python3
"""
Tokenificator — local Flask server
Run:  python app.py
Then open http://localhost:5000
"""

import io
import uuid
import zipfile
from pathlib import Path
from PIL import Image
from flask import Flask, jsonify, send_from_directory, send_file, request
import tkinter
import tkinter.filedialog

from token_processor import (
    process_file, process_folder,
    SUPPORTED_EXT, MASKS_DIR, FRAMES_DIR, DEFAULT_SIZE, VALID_SIZES,
    remove_background, _has_transparency,
)

from _paths import BUNDLE_DIR, DATA_DIR  # noqa: E402

app = Flask(__name__, static_folder=None)
TEMPLATES_DIR   = BUNDLE_DIR / "templates"
MODE_IMAGES_DIR = DATA_DIR   / "mode_images"
ZOOM_IMAGES_DIR = DATA_DIR   / "zoom_images"
TMP_DIR         = DATA_DIR   / "tmp"
MODE_IMAGES_DIR.mkdir(exist_ok=True)
ZOOM_IMAGES_DIR.mkdir(exist_ok=True)
FRAMES_DIR.mkdir(exist_ok=True)
TMP_DIR.mkdir(exist_ok=True)
for _f in TMP_DIR.iterdir():
    _f.unlink(missing_ok=True)


@app.get("/")
def index():
    return send_from_directory(TEMPLATES_DIR, "index.html")


@app.get("/mode-images/<name>")
def serve_mode_image(name):
    return send_from_directory(MODE_IMAGES_DIR, name)


@app.get("/zoom-images/<name>")
def serve_zoom_image(name):
    return send_from_directory(ZOOM_IMAGES_DIR, name)


_MIME = {'.webp': 'image/webp', '.png': 'image/png',
         '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg'}

@app.get("/serve")
def serve_output():
    """Serve any local output file for in-page preview."""
    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "No path"}), 400
    p = Path(path)
    if not p.exists() or not p.is_file():
        return jsonify({"error": "File not found"}), 404
    return send_file(p, mimetype=_MIME.get(p.suffix.lower(), 'application/octet-stream'))


@app.post("/download-zip")
def download_zip():
    """Bundle a list of local files into a ZIP and stream it to the browser.
    Body: { "files": [{"path": "...", "name": "..."}, ...] }
    """
    files = request.get_json(force=True).get("files", [])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            p = Path(f.get("path", ""))
            if p.exists() and p.is_file():
                zf.write(p, f.get("name", p.name))
    buf.seek(0)
    return send_file(buf, mimetype="application/zip",
                     as_attachment=True, download_name="tokens.zip")


@app.get("/masks")
def list_masks():
    masks = sorted(p.name for p in MASKS_DIR.glob("*.png"))
    return jsonify({"masks": masks})


@app.get("/masks/<filename>")
def serve_mask(filename):
    return send_from_directory(MASKS_DIR, filename)


@app.get("/frames")
def list_frames():
    frames = sorted(p.name for p in FRAMES_DIR.iterdir()
                    if p.suffix.lower() in (".png", ".webp"))
    return jsonify({"frames": frames})


@app.get("/list-dir-frames")
def list_dir_frames():
    """List all PNG/WebP files in any folder on disk."""
    dir_path = request.args.get("dir", "").strip()
    if not dir_path:
        return jsonify({"error": "No dir"}), 400
    p = Path(dir_path)
    if not p.exists() or not p.is_dir():
        return jsonify({"error": "Not a directory"}), 400
    frames = sorted(str(f) for f in p.iterdir()
                    if f.suffix.lower() in (".png", ".webp"))
    return jsonify({"frames": frames})


@app.get("/frames/<filename>")
def serve_frame(filename):
    return send_from_directory(FRAMES_DIR, filename)


@app.get("/tmp/<filename>")
def serve_tmp(filename):
    return send_from_directory(TMP_DIR, filename)


@app.post("/prepare")
def prepare():
    """
    Remove the background from a single image and return a preview URL.
    Body: { "input": "<file path>" }
    Returns: { "url": "/tmp/...", "path": "<tmp file path>", "width": N, "height": N }
    """
    data       = request.get_json(force=True)
    input_path = Path(data.get("input", ""))

    if not input_path.exists() or not input_path.is_file():
        return jsonify({"error": f"File not found: {input_path}"}), 400
    if input_path.suffix.lower() not in SUPPORTED_EXT:
        return jsonify({"error": f"Unsupported format: {input_path.suffix}"}), 400

    print(f"\nPreparing: {input_path.name}")
    raw = Image.open(input_path).convert("RGBA")

    if _has_transparency(raw):
        print("  [skip] Already has alpha — skipping background removal")
        nobg = raw
    else:
        print("  [1/1] Removing background…")
        nobg = remove_background(raw)

    tmp_name = f"prep_{input_path.stem}_{uuid.uuid4().hex[:8]}.png"
    tmp_path = TMP_DIR / tmp_name
    nobg.save(tmp_path, format="PNG")
    print(f"  ✓ Saved preview → {tmp_name}")

    return jsonify({
        "url":    f"/tmp/{tmp_name}",
        "path":   str(tmp_path),
        "width":  nobg.width,
        "height": nobg.height,
    })


@app.get("/open-folder")
def open_folder():
    """Open a native OS folder-picker dialog and return the chosen path."""
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    chosen = tkinter.filedialog.askdirectory(title="Select folder")
    root.destroy()
    if not chosen:
        return jsonify({"path": None})
    return jsonify({"path": str(Path(chosen))})


@app.get("/open-file")
def open_file():
    """Open a native OS file-picker dialog and return the chosen path."""
    exts = " ".join(f"*{e}" for e in SUPPORTED_EXT)
    root = tkinter.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    chosen = tkinter.filedialog.askopenfilename(
        title="Select image",
        filetypes=[("Images", exts), ("All files", "*.*")],
    )
    root.destroy()
    if not chosen:
        return jsonify({"path": None})
    return jsonify({"path": str(Path(chosen))})


@app.post("/process")
def process():
    """
    Body: { "input": "...", "output": "...", ...options..., "transform": {...} | null }
    Returns: { "results": [...], "errors": [...] }
    """
    data       = request.get_json(force=True)
    input_path = Path(data.get("input", ""))
    output_str = data.get("output", "").strip()
    mode       = data.get("mode", "both")
    mask_name         = data.get("mask", "bottom-half.png")
    size              = int(data.get("size", DEFAULT_SIZE))
    crop_backend      = data.get("crop_backend", "none")
    crop_zoom         = int(data.get("crop_zoom", 1))
    remove_bg_portrait = bool(data.get("remove_bg_portrait", True))
    remove_bg_token    = bool(data.get("remove_bg_token", True))
    frame_name      = data.get("frame", "none")
    split_y         = float(data.get("split_y", 0.5))
    circle_mask_pct = max(0.1, min(1.0, float(data.get("circle_mask", 1.0))))
    transform       = data.get("transform", None)   # dict or None

    if size not in VALID_SIZES:
        size = DEFAULT_SIZE
    if crop_backend not in ("none", "top", "insightface"):
        crop_backend = "none"
    if crop_zoom not in (1, 3, 5):
        crop_zoom = 1
    split_y = max(0.1, min(0.9, split_y))

    out_dir   = Path(output_str) if output_str else None
    mask_path = MASKS_DIR / mask_name if mask_name else None
    if frame_name and frame_name != "none":
        fp = Path(frame_name)
        frame_path = fp if fp.is_absolute() else FRAMES_DIR / frame_name
    else:
        frame_path = None

    # Validate transform if provided — only discard if a nobg_path was given but the file is gone (stale).
    # An empty nobg_path is valid: the Python pipeline will run rembg inline.
    nobg_tmp_to_delete = None
    if transform:
        nobg_path_val = (transform.get("nobg_path") or "").strip()
        if nobg_path_val and not Path(nobg_path_val).exists():
            transform = None  # stale prep file; fall back to auto
        elif nobg_path_val:
            nobg_tmp_to_delete = Path(nobg_path_val)

    results = []
    errors  = []

    if not input_path.exists():
        return jsonify({"error": f"Path not found: {input_path}"}), 400

    try:
        if input_path.is_dir():
            file_results = process_folder(input_path, out_dir, mode, mask_path, size,
                                          crop_backend, crop_zoom,
                                          remove_bg_portrait, remove_bg_token,
                                          frame_path, split_y, None, circle_mask_pct)
        else:
            file_results = [process_file(input_path, out_dir, mode, mask_path, size,
                                         crop_backend, crop_zoom,
                                         remove_bg_portrait, remove_bg_token,
                                         frame_path, split_y, transform, circle_mask_pct)]

        for r in file_results:
            entry = {}
            for key in ("portrait", "token", "nobg"):
                if key in r:
                    p = r[key]
                    entry["name"] = p.stem.removesuffix("_token")
                    entry[key]    = str(p)
            results.append(entry)
    except Exception as exc:
        errors.append(str(exc))

    if nobg_tmp_to_delete:
        nobg_tmp_to_delete.unlink(missing_ok=True)

    return jsonify({"results": results, "errors": errors})


if __name__ == "__main__":
    print("Tokenificator running at http://localhost:5000")
    app.run(debug=False, port=5000)
