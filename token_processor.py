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

    top_bias=True: for portrait output, biases the vertical crop toward the top
    so the head isn't cut off when no face detection is available.
    """
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top  = (h - side) // 4 if top_bias else (h - side) // 2
    img  = img.crop((left, top, left + side, top + side))
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
) -> dict:
    """
    Process one image.
    mode: 'both' | 'portrait' | 'token' | 'nobg'
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
                                        remove_bg_portrait, remove_bg_token))
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
    args = parser.parse_args()

    out = Path(args.output_dir) if args.output_dir else None

    if args.folder:
        process_folder(Path(args.folder), out, args.mode, size=args.size,
                       crop_backend=args.crop, crop_zoom=args.zoom)
    else:
        process_file(Path(args.input), out, args.mode, size=args.size,
                     crop_backend=args.crop, crop_zoom=args.zoom)
