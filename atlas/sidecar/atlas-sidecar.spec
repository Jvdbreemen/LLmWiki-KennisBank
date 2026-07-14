# PyInstaller spec for the Atlas sidecar (TASK-27.12).
# Freezes the FastAPI sidecar so the bundled Tauri app needs no system Python.
# Build:  pyinstaller atlas/sidecar/atlas-sidecar.spec
# Output (onedir): dist/atlas-sidecar/atlas-sidecar(.exe) + _internal/.
# Copy the exe to atlas/src-tauri/binaries/ with the Tauri target-triple suffix
# and _internal/ next to it; tauri.conf.json maps _internal into the install
# root so the exe finds it at runtime.
#
# onedir, NOT onefile: onefile re-extracts ~76MB to a fresh %TEMP%\_MEI dir on
# every launch, and antivirus then rescans every DLL — measured cold starts of
# minutes inside the bundled app. onedir unpacks once at install time.
#
# sqlite-vec ships a native extension that PyInstaller must collect; the hidden
# imports cover FastAPI/uvicorn/httpx pulled in dynamically.
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# repo root (two up from atlas/sidecar) so `import atlas.sidecar` resolves.
ROOT = os.path.abspath(os.path.join(os.getcwd(), "..", ".."))

datas = collect_data_files("sqlite_vec")
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("fastapi")
    + ["httpx", "sqlite_vec"]
)

a = Analysis(
    ["__main__.py"],
    pathex=[ROOT],
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
    [],
    exclude_binaries=True,
    name="atlas-sidecar",
    console=True,          # keep a console so startup/errors are visible
    upx=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="atlas-sidecar",
    upx=False,
)
