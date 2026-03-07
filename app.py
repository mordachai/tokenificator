#!/usr/bin/env python3
"""
Tokenificator — local Flask server
Run:  python app.py
Then open http://localhost:5000
"""

from pathlib import Path
from flask import Flask, jsonify, send_from_directory, send_file, request
import tkinter
import tkinter.filedialog

from token_processor import process_file, process_folder, SUPPORTED_EXT, MASKS_DIR, DEFAULT_SIZE, VALID_SIZES

app = Flask(__name__, static_folder=None)
TEMPLATES_DIR   = Path(__file__).parent / "templates"
MODE_IMAGES_DIR = Path(__file__).parent / "mode_images"
ZOOM_IMAGES_DIR = Path(__file__).parent / "zoom_images"
MODE_IMAGES_DIR.mkdir(exist_ok=True)
ZOOM_IMAGES_DIR.mkdir(exist_ok=True)


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


@app.get("/masks")
def list_masks():
    masks = sorted(p.name for p in MASKS_DIR.glob("*.png"))
    return jsonify({"masks": masks})


@app.get("/masks/<filename>")
def serve_mask(filename):
    return send_from_directory(MASKS_DIR, filename)


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
    Body: { "input": "<file or folder path>", "output": "<folder path>" }
    Returns: { "results": [ { "name": str, "portrait": str, "token": str } ], "errors": [...] }
    """
    data       = request.get_json(force=True)
    input_path = Path(data.get("input", ""))
    output_str = data.get("output", "").strip()
    mode       = data.get("mode", "both")
    mask_name    = data.get("mask", "bottom-half.png")
    size         = int(data.get("size", DEFAULT_SIZE))
    crop_backend        = data.get("crop_backend", "none")
    crop_zoom           = int(data.get("crop_zoom", 1))
    remove_bg_portrait  = bool(data.get("remove_bg_portrait", True))
    remove_bg_token     = bool(data.get("remove_bg_token", True))
    if size not in VALID_SIZES:
        size = DEFAULT_SIZE
    if crop_backend not in ("none", "top", "mediapipe", "insightface"):
        crop_backend = "none"
    if crop_zoom not in (1, 3, 5):
        crop_zoom = 1
    out_dir    = Path(output_str) if output_str else None
    mask_path  = MASKS_DIR / mask_name if mask_name else None

    results = []
    errors  = []

    if not input_path.exists():
        return jsonify({"error": f"Path not found: {input_path}"}), 400

    try:
        if input_path.is_dir():
            file_results = process_folder(input_path, out_dir, mode, mask_path, size,
                                          crop_backend, crop_zoom,
                                          remove_bg_portrait, remove_bg_token)
        else:
            file_results = [process_file(input_path, out_dir, mode, mask_path, size,
                                         crop_backend, crop_zoom,
                                         remove_bg_portrait, remove_bg_token)]

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

    return jsonify({"results": results, "errors": errors})


if __name__ == "__main__":
    print("Tokenificator running at http://localhost:5000")
    app.run(debug=False, port=5000)
