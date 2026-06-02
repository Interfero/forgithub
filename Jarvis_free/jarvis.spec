# -*- mode: python -*-
# PyInstaller: Jarvis.exe с UI, модулями и каталогом data/memory (предобучение).
# Сборка: build-exe.bat (сначала npm run build)

from pathlib import Path

block_cipher = None
root = Path(SPECPATH)
backend = root / "backend"
frontend_dist = root / "frontend" / "dist"
memory_src = backend / "data" / "memory"

datas = []
if frontend_dist.is_dir():
    datas.append((str(frontend_dist), "frontend/dist"))
if memory_src.is_dir():
    datas.append((str(memory_src), "data/memory"))

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "duckduckgo_search",
    "edge_tts",
]

a = Analysis(
    [str(backend / "main.py")],
    pathex=[str(backend)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Jarvis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
