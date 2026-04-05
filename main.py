#!/usr/bin/env python3
"""
Tokenificator — launcher
Bootstraps writable asset dirs, then starts Flask and opens the browser.
"""

import os
import sys
import shutil
import threading
import time
import webbrowser
from pathlib import Path


# ── Bootstrap writable dirs on first run ──────────────────────────────────────
# masks/ and frames/ are bundled in the exe / installed to /app, but users may
# add their own files, so we copy them out to the writable DATA_DIR once.
def _bootstrap():
    if not getattr(sys, "frozen", False) and not os.environ.get("FLATPAK_ID"):
        return
    from _paths import BUNDLE_DIR, DATA_DIR
    for name in ("masks", "frames", "mode_images", "zoom_images"):
        dst = DATA_DIR / name
        if not dst.exists():
            src = BUNDLE_DIR / name
            if src.exists():
                shutil.copytree(src, dst)
            else:
                dst.mkdir(parents=True, exist_ok=True)

_bootstrap()


# ── Import app after bootstrap so paths resolve correctly ─────────────────────
from app import app  # noqa: E402  (import after sys.path setup)

PORT = 5000


def _open_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://localhost:{PORT}")


if __name__ == "__main__":
    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(debug=False, port=PORT, use_reloader=False)
