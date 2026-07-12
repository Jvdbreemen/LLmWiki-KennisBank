# Building the standalone KennisBank Atlas app (TASK-27.12)

The bundled desktop app wraps the frontend in a Tauri WebView2 shell and ships a
**frozen** Python sidecar, so end users need neither Python nor Node. This is the
ADR-0004 / ADR-007 "two runtimes to package" cost, made explicit.

> Status: the scaffold (`atlas/src-tauri/`, `atlas/sidecar/atlas-sidecar.spec`) is
> build-ready but has NOT been built here (no Rust toolchain in this env). Expect
> to smoke-test `cargo tauri dev` once and adjust `main.rs`/config if needed.

## Prerequisites (build machine only)

- **Rust toolchain** via rustup (`cargo`) - https://rustup.rs
- **Tauri CLI**: `cargo install tauri-cli --version '^2'` (or `npm i -g @tauri-apps/cli`)
- **WebView2 runtime** (present on modern Windows; the installer can bundle it)
- **PyInstaller**: `pip install pyinstaller`
- The frontend deps: `cd atlas/frontend && npm install`

`python3 atlas/doctor.py` reports whether `cargo` is present (it is optional -
only needed here).

## Steps (Windows)

1. Freeze the sidecar:
   ```bash
   cd atlas/sidecar && pyinstaller atlas-sidecar.spec
   ```
   This produces `dist/atlas-sidecar.exe`.

2. Place the frozen sidecar where Tauri expects an external binary, renamed with
   the Rust target triple:
   ```bash
   mkdir -p ../src-tauri/binaries
   cp dist/atlas-sidecar.exe ../src-tauri/binaries/atlas-sidecar-x86_64-pc-windows-msvc.exe
   ```

3. Build the app (this also runs `npm run build` for the frontend via
   `beforeBuildCommand`):
   ```bash
   cd ../src-tauri && cargo tauri build
   ```
   The MSI/NSIS installer lands in `target/release/bundle/`.

## Runtime model

- The shell picks a free loopback port, spawns the frozen sidecar bound to
  `127.0.0.1` on it, and injects the port into the webview
  (`window.__ATLAS_PORT__`) before the frontend loads.
- The sidecar child is owned by the shell and dies with the app (no orphan).
- Fully offline: the CSP allows only `self` + `http://127.0.0.1:*`; the sidecar
  calls only local stores and local Ollama. Dependency downloads happen at BUILD
  time only.

## Size expectation

- Tauri shell: well under 10 MB (reuses the OS WebView2, no bundled Chromium).
- Frozen sidecar: tens of MB (Python runtime + FastAPI + sqlite-vec). Total is a
  fraction of an Electron app's 100 MB+.

## Code signing

Out of scope; documented. Unsigned installers show a SmartScreen prompt on first
run. Sign with a code-signing certificate for distribution if desired.
