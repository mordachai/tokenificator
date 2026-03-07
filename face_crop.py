"""
face_crop.py — Face-aware smart cropping for the Tokenificator pipeline.

Crop backends:
  "none"        — passthrough, no crop
  "top"         — simple top-square crop (no AI)
  "mediapipe"   — MediaPipe FaceDetector  (pip install mediapipe)
  "insightface" — InsightFace RetinaFace  (pip install insightface)

Zoom levels:
  1 — loose:  head + torso       (face bbox × ~8 total)
  3 — medium: head + shoulders   (face bbox × ~5 total)
  5 — strong: bust / upper chest (face bbox × ~3 total)
"""

import urllib.request
from pathlib import Path
from PIL import Image

# padding_factor = how many face-heights of context surround each side of the face.
# Total crop height = fh * (1 + 2 * padding).
# ×N zoom means the face appears N× larger vs ×1 → crop shrinks by factor N.
# ×1 baseline crop ≈ 8 × fh  →  ×3 ≈ 8/3 × fh  →  ×5 ≈ 8/5 × fh
_PADDING: dict[int, float] = {
    1: 3.5,   # ×1 loose:  total ≈ 8 × fh  (head + torso)
    3: 0.83,  # ×3 medium: total ≈ 2.6 × fh (head + shoulders)
    5: 0.3,   # ×5 strong: total ≈ 1.6 × fh (face fills ~62% of crop)
}

# InsightFace model loaded once per process (expensive)
_insightface_app = None

# MediaPipe Tasks model (auto-downloaded on first use, ~0.8 MB)
_MP_MODEL_PATH = Path(__file__).parent / "models" / "blaze_face_short_range.tflite"
_MP_MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
)


def _ensure_mp_model() -> str:
    if not _MP_MODEL_PATH.exists():
        _MP_MODEL_PATH.parent.mkdir(exist_ok=True)
        print("  Downloading MediaPipe face model (~0.8 MB)…")
        urllib.request.urlretrieve(_MP_MODEL_URL, _MP_MODEL_PATH)
    return str(_MP_MODEL_PATH)


def _bbox_to_crop(
    img: Image.Image,
    fx: int, fy: int, fw: int, fh: int,
    zoom: int,
) -> Image.Image:
    """Crop a square region centred on the face, padded by zoom level.

    Square crop maps cleanly onto the square canvas — no letterboxing.
    scale_to_canvas upscales the crop to fill the canvas, so at ×5
    the face fills the frame completely.
    """
    W, H = img.size
    pad  = _PADDING[zoom] * fh
    half = (fh + 2 * pad) / 2

    cx   = fx + fw / 2
    cy   = fy + fh / 2

    left  = max(0, int(cx - half))
    top   = max(0, int(cy - half))
    right = min(W, int(cx + half))
    bot   = min(H, int(cy + half))

    return img.crop((left, top, right, bot))


def _crop_top(img: Image.Image, zoom: int) -> Image.Image:
    """Crop from the top of the image keeping full width, height controlled by zoom."""
    W, H = img.size
    fracs = {1: 0.8, 3: 0.5, 5: 0.3}
    height = int(H * fracs[zoom])
    return img.crop((0, 0, W, height))


def _crop_mediapipe(img: Image.Image, zoom: int) -> Image.Image:
    """Detect face with MediaPipe Tasks API (0.10.x+) and crop."""
    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision
    except ImportError:
        raise ImportError("MediaPipe not installed. Run: pip install mediapipe")

    import numpy as np

    model_path   = _ensure_mp_model()
    base_options = mp_python.BaseOptions(model_asset_path=model_path)
    options      = mp_vision.FaceDetectorOptions(base_options=base_options)

    rgb      = img.convert("RGB")
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.array(rgb))

    with mp_vision.FaceDetector.create_from_options(options) as detector:
        result = detector.detect(mp_image)

    if not result.detections:
        raise RuntimeError("No face detected (MediaPipe)")

    det  = max(result.detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)
    bb   = det.bounding_box
    fx, fy, fw, fh = bb.origin_x, bb.origin_y, bb.width, bb.height

    return _bbox_to_crop(img, fx, fy, fw, fh, zoom)


def _crop_insightface(img: Image.Image, zoom: int) -> Image.Image:
    """Detect face with InsightFace and crop. Raises ImportError or RuntimeError."""
    global _insightface_app
    try:
        from insightface.app import FaceAnalysis
    except ImportError:
        raise ImportError("InsightFace not installed. Run: pip install insightface")

    import numpy as np

    if _insightface_app is None:
        _insightface_app = FaceAnalysis(
            name="buffalo_sc",
            allowed_modules=["detection"],
            providers=["CPUExecutionProvider"],
        )
        _insightface_app.prepare(ctx_id=0, det_size=(640, 640))

    # InsightFace expects BGR
    arr   = np.array(img.convert("RGB"))[:, :, ::-1]
    faces = _insightface_app.get(arr)

    if not faces:
        raise RuntimeError("No face detected (InsightFace)")

    face         = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    x1, y1, x2, y2 = [int(v) for v in face.bbox]
    fx, fy, fw, fh  = x1, y1, x2 - x1, y2 - y1

    return _bbox_to_crop(img, fx, fy, fw, fh, zoom)


def smart_crop(
    img: Image.Image,
    backend: str = "none",
    zoom: int = 1,
) -> Image.Image:
    """
    Crop img using the selected backend and zoom level.

    backend: "none" | "top" | "mediapipe" | "insightface"
    zoom:    1 (loose) | 2 (medium) | 3 (tight)

    AI backends fall back to top-crop if no face is detected.
    ImportError (backend not installed) is re-raised to surface to the caller.
    """
    if backend == "none":
        return img
    if backend == "top":
        return _crop_top(img, zoom)

    try:
        if backend == "mediapipe":
            return _crop_mediapipe(img, zoom)
        if backend == "insightface":
            return _crop_insightface(img, zoom)
        raise ValueError(f"Unknown crop backend: {backend!r}")
    except ImportError:
        raise
    except RuntimeError as exc:
        print(f"  ! {exc} — falling back to top crop")
        return _crop_top(img, zoom)
