"""
Central path resolver — works in both dev and PyInstaller frozen contexts.

  BUNDLE_DIR  read-only assets baked into the exe
              (sys._MEIPASS when frozen, project root otherwise)

  DATA_DIR    writable user data — masks, frames, tmp
              (folder containing the .exe when frozen, project root otherwise)
"""

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    DATA_DIR   = Path(sys.executable).parent
else:
    BUNDLE_DIR = Path(__file__).parent
    DATA_DIR   = Path(__file__).parent
