#!/usr/bin/env python3
"""
RPG Token Processor
-------------------
Modes (--mode):
  both      (default) — portrait + token WebP
  portrait             — bg removed, scaled, no mask
  token                — bg removed, scaled, arc mask
  nobg                 — bg removed only, original size, WebP

Usage:
    python token_processor.py <input_image> [--output-dir DIR] [--mode MODE]
    python token_processor.py --folder <folder>  [--output-dir DIR] [--mode MODE]
"""

import io
import argparse
from pathlib import Path

from PIL import Image
import rembg
from face_crop import smart_crop


# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_SIZE  = 512
VALID_SIZES   = (256, 512, 1024, 2048)
WEBP_QUALITY  = 90
SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}
MASKS_DIR     = Path(__file__).parent / "masks"
MASK_FILE     = MASKS_DIR / "bottom-half.png"
FRAMES_DIR    = Path(__file__).parent / "frames"
# ─────────────────────────────────────────────────────────────────────────────


def remove_background(img: Image.Image) -> Image.Image:
    """Strip background using rembg (returns RGBA). Runs once per source image."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    out_bytes = rembg.remove(buf.read())
    return Image.open(io.BytesIO(out_bytes)).convert("RGBA")


def _has_transparency(img: Image.Image) -> bool:
    """Return True if the image already has a meaningful alpha channel."""
    if img.mode != "RGBA":
        return False
    return img.getextrema()[3][0] < 255  # min alpha < 255 → some transparent pixels


def scale_to_canvas(img: Image.Image, size: int, top_bias: bool = False) -> Image.Image:
    """Center-crop to a square using the shorter dimension, then scale to size×size.

    Horizontal position is derived from the alpha bounding box when available,
    so off-center characters (leaning left/right in the source) are auto-corrected.
    top_bias=True: biases the vertical crop toward the top for portrait output.
    """
    w, h = img.size
    side = min(w, h)

    # Horizontal: center on the content's alpha bbox, not the raw image center
    if img.mode == "RGBA":
        bbox = img.split()[3].getbbox()  # bounding box of non-transparent pixels
        if bbox:
            content_cx = (bbox[0] + bbox[2]) // 2
            left = max(0, min(content_cx - side // 2, w - side))
        else:
            left = (w - side) // 2
    else:
        left = (w - side) // 2

    top = (h - side) // 4 if top_bias else (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    return img.resize((size, size), Image.LANCZOS)


def load_token_mask(canvas_size: int, mask_path: Path | None = None) -> Image.Image:
    """Load a mask PNG (L-mode) scaled to canvas_size. Defaults to MASK_FILE."""
    mask = Image.open(mask_path or MASK_FILE).convert("L")
    if mask.size != (canvas_size, canvas_size):
        mask = mask.resize((canvas_size, canvas_size), Image.LANCZOS)
    return mask


def apply_mask(img: Image.Image, mask: Image.Image) -> Image.Image:
    """Intersect an L-mode shape mask with the image's existing alpha channel.

    Fully transparent pixels (alpha=0) have their RGB zeroed out to avoid
    premultiplied-alpha artifacts in WebGL renderers (e.g. Foundry / PIXI.js).
    """
    img = img.convert("RGBA")
    r, g, b, a = img.split()
    new_alpha = Image.new("L", img.size, 0)
    new_alpha.paste(a, mask=mask)
    # Zero out RGB where alpha==0 so no colour bleeds through in premult renderers.
    # invert_alpha: 255 where transparent, 0 where opaque.
    invert_alpha = new_alpha.point(lambda x: 0 if x else 255)
    black = Image.new("L", img.size, 0)
    r.paste(black, mask=invert_alpha)
    g.paste(black, mask=invert_alpha)
    b.paste(black, mask=invert_alpha)
    return Image.merge("RGBA", (r, g, b, new_alpha))


def apply_manual_transform(
    img: Image.Image,
    pan_x: float,
    pan_y: float,
    user_scale: float,
    canvas_size: int,
) -> Image.Image:
    """Place img onto a canvas_size×canvas_size canvas with manual positioning.

    pan_x, pan_y:  offset of image centre from canvas centre, as a fraction
                   of canvas_size (pan_pixels / CANVAS_PX from the browser).
    user_scale:    zoom multiplier (1.0 = shorter side of img fills canvas_size).
    """
    base_scale = canvas_size / min(img.width, img.height)
    effective  = base_scale * user_scale
    new_w = max(1, round(img.width  * effective))
    new_h = max(1, round(img.height * effective))
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    paste_x = canvas_size // 2 - new_w // 2 + round(pan_x * canvas_size)
    paste_y = canvas_size // 2 - new_h // 2 + round(pan_y * canvas_size)

    out = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    out.paste(resized, (paste_x, paste_y), resized)
    return out


def apply_frame(char: Image.Image, frame: Image.Image, split_y: float = 0.5) -> Image.Image:
    """Composite a decorative frame over a character token.

    Layer order (bottom → top):
      1. char          — fills the frame interior
      2. frame         — ring renders over char body
      3. char overflow — char pixels above split_y pop over the frame top

    split_y: vertical fraction where overflow begins (default 0.5 = midpoint).
    """
    size = char.size[0]
    frame = frame.resize((size, size), Image.LANCZOS)

    # Upper mask: white = top portion (where char overflows above the frame)
    upper_mask = Image.new("L", (size, size), 0)
    upper_mask.paste(255, (0, 0, size, int(size * split_y)))

    # char_overflow = char with alpha zeroed below split_y
    r, g, b, a = char.split()
    overflow_a = Image.new("L", (size, size), 0)
    overflow_a.paste(a, mask=upper_mask)
    char_overflow = Image.merge("RGBA", (r, g, b, overflow_a))

    # Composite: char → frame → char_overflow
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(char)
    canvas.alpha_composite(frame)
    canvas.alpha_composite(char_overflow)
    return canvas


def _save(img: Image.Image, path: Path, lossless: bool = False) -> None:
    if lossless:
        img.save(path, format="WEBP", lossless=True)
    elif img.mode == "RGBA":
        img.save(path, format="WEBP", quality=WEBP_QUALITY, alpha_quality=100)
    else:
        img.save(path, format="WEBP", quality=WEBP_QUALITY)


# ── Per-image pipeline ────────────────────────────────────────────────────────

def process_file(
    src: Path,
    out_dir: Path | None = None,
    mode: str = "both",
    mask_path: Path | None = None,
    size: int = DEFAULT_SIZE,
    crop_backend: str = "none",
    crop_zoom: int = 1,
    remove_bg_portrait: bool = True,
    remove_bg_token: bool = True,
    frame_path: Path | None = None,
    split_y: float = 0.5,
    transform: dict | None = None,
) -> dict:
    """
    Process one image.
    mode: 'both' | 'portrait' | 'token' | 'nobg'
    transform: when provided (manual-positioning mode), skips bg removal and
               auto-crop; loads the pre-computed nobg from transform['nobg_path']
               and places it using apply_manual_transform.
    Returns dict with keys for produced paths (portrait, token, nobg).
    Raises ValueError for unsupported extensions.
    """
    if src.suffix.lower() not in SUPPORTED_EXT:
        raise ValueError(f"Unsupported format: {src.suffix}")

    out_dir = out_dir or src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nProcessing: {src.name}  [mode={mode}, size={size}]")

    result = {}
    raw = Image.open(src).convert("RGBA")
    already_transparent = _has_transparency(raw)

    # ── Manual-transform path (preview mode) ─────────────────────────────────
    if transform:
        nobg_path_str = (transform.get("nobg_path") or "").strip()
        pan_x      = float(transform.get("pan_x",      0.0))
        pan_y      = float(transform.get("pan_y",      0.0))
        user_scale = float(transform.get("user_scale", 1.0))
        print(f"  [manual] pan=({pan_x:.3f},{pan_y:.3f}) zoom={user_scale:.2f}")

        if nobg_path_str and Path(nobg_path_str).exists():
            nobg = Image.open(Path(nobg_path_str)).convert("RGBA")
        elif already_transparent:
            print("  [skip] Source already has alpha — skipping background removal")
            nobg = raw
        else:
            print("  [1/?] Removing background…")
            nobg = remove_background(raw)

        portrait_src = nobg if remove_bg_portrait else raw
        token_src    = nobg if remove_bg_token    else raw

        if mode in ("both", "portrait"):
            scaled = apply_manual_transform(portrait_src, pan_x, pan_y, user_scale, size)
            path   = out_dir / f"{src.stem}.webp"
            _save(scaled, path)
            print(f"  ✓ Portrait → {path.name}")
            result["portrait"] = path

        if mode in ("both", "token"):
            scaled = apply_manual_transform(token_src, pan_x, pan_y, user_scale, size)
            token  = apply_mask(scaled.copy(), load_token_mask(size, mask_path))
            if frame_path:
                token = apply_frame(token, Image.open(frame_path).convert("RGBA"), split_y)
            path  = out_dir / f"{src.stem}_token.webp"
            _save(token, path, lossless=True)
            print(f"  ✓ Token    → {path.name}")
            result["token"] = path

        return result
    # ─────────────────────────────────────────────────────────────────────────

    if mode == "nobg":
        if already_transparent:
            print("  [skip] Source already has alpha — skipping background removal")
            nobg = raw
        else:
            print("  [1/?] Removing background…")
            nobg = remove_background(raw)
        path = out_dir / f"{src.stem}.webp"
        _save(nobg, path)
        print(f"  ✓ No-BG    → {path.name}")
        result["nobg"] = path
        return result

    # Determine effective bg-removal flags (skip if already transparent)
    eff_remove_portrait = remove_bg_portrait and not already_transparent
    eff_remove_token    = remove_bg_token    and not already_transparent

    if already_transparent:
        print("  [skip] Source already has alpha — skipping background removal")

    # Run rembg once on the uncropped image (portrait always uses full frame)
    if eff_remove_portrait or eff_remove_token:
        print("  [1/?] Removing background…")
        nobg = remove_background(raw)
    else:
        nobg = raw  # no removal needed

    portrait_base = nobg if (eff_remove_portrait or already_transparent) else raw
    token_base    = nobg if (eff_remove_token    or already_transparent) else raw

    # Portrait: face-center with loose zoom when AI backend available, else top-biased crop
    if mode in ("both", "portrait"):
        if crop_backend != "none":
            print("  [2/?] Centering portrait on face…")
            portrait_src = smart_crop(portrait_base, crop_backend, 1)  # always loose
        else:
            portrait_src = portrait_base
        print("  [2/?] Scaling portrait…")
        portrait_scaled = scale_to_canvas(portrait_src, size, top_bias=True)
        path = out_dir / f"{src.stem}.webp"
        _save(portrait_scaled, path)
        print(f"  ✓ Portrait → {path.name}")
        result["portrait"] = path

    # Token: face-cropped with user zoom, then masked
    if mode in ("both", "token"):
        if crop_backend != "none":
            print("  [3/?] Cropping token…")
            token_src = smart_crop(token_base, crop_backend, crop_zoom)
        else:
            token_src = token_base
        print("  [3/?] Scaling token…")
        token_scaled = scale_to_canvas(token_src, size, top_bias=False)
        print("  [4/?] Applying mask…")
        token = apply_mask(token_scaled.copy(), load_token_mask(size, mask_path))
        if frame_path:
            print("  [5/?] Applying frame…")
            frame_img = Image.open(frame_path).convert("RGBA")
            token = apply_frame(token, frame_img, split_y)
        path  = out_dir / f"{src.stem}_token.webp"
        _save(token, path, lossless=True)
        print(f"  ✓ Token    → {path.name}")
        result["token"] = path

    return result


def process_folder(
    folder: Path,
    out_dir: Path | None = None,
    mode: str = "both",
    mask_path: Path | None = None,
    size: int = DEFAULT_SIZE,
    crop_backend: str = "none",
    crop_zoom: int = 1,
    remove_bg_portrait: bool = True,
    remove_bg_token: bool = True,
    frame_path: Path | None = None,
    split_y: float = 0.5,
    transform: dict | None = None,
) -> list[dict]:
    """Process every supported image in folder (non-recursive)."""
    images = sorted(f for f in folder.iterdir() if f.suffix.lower() in SUPPORTED_EXT)
    if not images:
        print(f"No supported images found in {folder}")
        return []
    results = []
    for img_path in images:
        try:
            results.append(process_file(img_path, out_dir, mode, mask_path, size,
                                        crop_backend, crop_zoom,
                                        remove_bg_portrait, remove_bg_token,
                                        frame_path, split_y, transform))
        except Exception as exc:
            print(f"  ! Skipped {img_path.name}: {exc}")
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RPG Token Processor")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("input",          nargs="?", help="Input image file")
    group.add_argument("--folder", "-f", help="Process all images in a folder")
    parser.add_argument("--output-dir", "-o", default=None,
                        help="Output directory (default: same as source)")
    parser.add_argument("--mode", "-m",
                        choices=["both", "portrait", "token", "nobg"],
                        default="both",
                        help="Output mode (default: both)")
    parser.add_argument("--size", "-s",
                        type=int, choices=list(VALID_SIZES), default=DEFAULT_SIZE,
                        help=f"Output canvas size in px (default: {DEFAULT_SIZE})")
    parser.add_argument("--crop", "-c",
                        choices=["none", "top", "mediapipe", "insightface"],
                        default="none",
                        help="Face crop backend (default: none)")
    parser.add_argument("--zoom", "-z",
                        type=int, choices=[1, 3, 5], default=1,
                        help="Crop zoom: 1=loose, 3=medium, 5=strong (default: 1)")
    parser.add_argument("--frame", "-F",
                        default=None,
                        help="Path to a decorative frame PNG (RGBA) to composite over the token")
    parser.add_argument("--split-y",
                        type=float, default=0.5, metavar="FRAC",
                        help="Vertical fraction (0.0–1.0) where character overflows above the frame (default: 0.5)")
    args = parser.parse_args()

    out        = Path(args.output_dir) if args.output_dir else None
    frame_path = Path(args.frame)      if args.frame      else None

    if args.folder:
        process_folder(Path(args.folder), out, args.mode, size=args.size,
                       crop_backend=args.crop, crop_zoom=args.zoom,
                       frame_path=frame_path, split_y=args.split_y)
    else:
        process_file(Path(args.input), out, args.mode, size=args.size,
                     crop_backend=args.crop, crop_zoom=args.zoom,
                     frame_path=frame_path, split_y=args.split_y)
