# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Tokenificator.

Build:
    pyinstaller tokenificator.spec

Output: dist/Tokenificator/Tokenificator.exe  (onedir — fast startup)
Users can add masks/frames next to Tokenificator.exe and they appear in the UI.
"""
from PyInstaller.utils.hooks import copy_metadata

block_cipher = None

# Packages that call importlib.metadata.version() on themselves at import time
# must have their dist-info metadata bundled explicitly.
# Use a safe wrapper because onnxruntime may be installed under different dist-info
# names depending on the environment (e.g. onnxruntime vs onnxruntime-cpu).
def _safe_meta(pkg):
    try:
        return copy_metadata(pkg)
    except Exception:
        return []

_metadata = (
    _safe_meta("pymatting")
    + _safe_meta("rembg")
    + _safe_meta("onnxruntime")
    + _safe_meta("onnxruntime-cpu")
    + _safe_meta("onnxruntime-gpu")
    + _safe_meta("Pillow")
    + _safe_meta("numpy")
)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=_metadata + [
        ("templates",   "templates"),
        ("masks",       "masks"),
        ("frames",      "frames"),
        ("mode_images", "mode_images"),
        ("zoom_images", "zoom_images"),
        ("_paths.py",   "."),
        ("face_crop.py","." ),
    ],
    hiddenimports=[
        # Flask / Werkzeug
        "flask",
        "werkzeug",
        "werkzeug.serving",
        "werkzeug.debug",
        # Pillow
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        # rembg and its deps
        "rembg",
        "rembg.bg",
        "rembg.sessions",
        "rembg.sessions.base",
        "rembg.sessions.u2net",
        "rembg.sessions.u2netp",
        "rembg.sessions.u2net_human_seg",
        "rembg.sessions.u2net_cloth_seg",
        "rembg.sessions.silueta",
        "rembg.sessions.isnet_general_use",
        "rembg.sessions.isnet_anime",
        "rembg.sessions.sam",
        "onnxruntime",
        "onnxruntime.capi",
        # scipy / skimage used by rembg
        "scipy",
        "scipy.ndimage",
        "scipy.special",
        "scipy.special._ufuncs_cxx",
        "skimage",
        "skimage.morphology",
        # pooch (model downloader used by rembg)
        "pooch",
        # tkinter for file dialogs
        "tkinter",
        "tkinter.filedialog",
        # misc
        "pkg_resources",
        "packaging",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Tokenificator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # set to False for no terminal window (errors will be silent)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="icon.ico",  # uncomment and add icon.ico to enable
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Tokenificator",
)
