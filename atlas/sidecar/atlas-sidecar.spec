# PyInstaller spec for the Atlas sidecar (TASK-27.12).
# Freezes the FastAPI sidecar into a single executable so the bundled Tauri app
# needs no system Python. Build:  pyinstaller atlas/sidecar/atlas-sidecar.spec
# Output: dist/atlas-sidecar(.exe) -> copy to atlas/src-tauri/binaries/ with the
# Tauri target-triple suffix (e.g. atlas-sidecar-x86_64-pc-windows-msvc.exe).
#
# sqlite-vec ships a native extension that PyInstaller must collect; the hidden
# imports cover FastAPI/uvicorn/httpx pulled in dynamically.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("sqlite_vec")
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("fastapi")
    + ["httpx", "sqlite_vec"]
)

a = Analysis(
    ["__main__.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="atlas-sidecar",
    console=True,          # keep a console so startup/errors are visible
    onefile=True,
    upx=False,
)
