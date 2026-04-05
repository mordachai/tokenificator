"""
Central path resolver — works in dev, PyInstaller frozen, and Flatpak contexts.

  BUNDLE_DIR  read-only assets baked into the exe / installed to /app
              (sys._MEIPASS when frozen, /app/share/tokenificator in Flatpak,
               project root otherwise)

  DATA_DIR    writable user data — masks, frames, tmp
              (folder containing the .exe when frozen, XDG_DATA_HOME/tokenificator
               in Flatpak, project root otherwise)
"""

import sys
import os
from pathlib import Path

if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    DATA_DIR   = Path(sys.executable).parent
elif os.environ.get("FLATPAK_ID"):
    BUNDLE_DIR = Path("/app/share/tokenificator")
    _xdg_data  = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    DATA_DIR   = Path(_xdg_data) / "tokenificator"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
else:
    BUNDLE_DIR = Path(__file__).parent
    DATA_DIR   = Path(__file__).parent
