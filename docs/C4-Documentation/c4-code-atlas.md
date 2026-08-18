# C4 Code Level: Atlas Launcher & Build Orchestration

## Overview

- **Name**: Atlas Launcher & Build Orchestration (Top-Level)
- **Description**: Launcher scripts and build configuration for KennisBank Atlas, a sovereign local-first dashboard for vault exploration and memory management. The top-level orchestrates the dev-mode startup (sidecar + frontend) and provides readiness diagnostics.
- **Location**: `atlas/` (repo root relative: [atlas/](../../atlas/))
- **Language**: Python 3 (launcher/doctor), Shell/JSON (build config), TypeScript/Rust (in subdirectories; documented separately)
- **Purpose**: Provide one-command dev launch, build system integration (Tauri/PyInstaller), and comprehensive health checking before runtime
- **Architecture Reference**: ADR-0004 (two-runtime model: FastAPI sidecar + TypeScript frontend), ADR-007 (Tauri bundling)

## Directory Structure

```
atlas/
├── launch.py                  # Dev launcher: starts sidecar + vite
├── doctor.py                  # Health checker: validates stack readiness
├── package.json               # Tauri CLI configuration
├── __init__.py                # Python package marker
├── BUILD.md                   # Standalone app build instructions
├── README.md                  # Overview, running, and requirements
├── sidecar/                   # FastAPI backend (documented separately: c4-code-atlas-sidecar.md)
├── frontend/                  # TypeScript/Vite UI (documented separately: c4-code-atlas-frontend.md)
└── src-tauri/                 # Tauri shell scaffold (documented separately: c4-code-atlas-tauri.md)
```

## Code Elements

### Launcher Scripts

#### `launch.py` — Development Mode Launcher

**Purpose**: One-command dev startup orchestrating sidecar, frontend, and child process lifecycle management. Handles platform-specific cleanup (Windows Job Objects) and port discovery.

##### Entry Point

- `main() -> None`
  - **Description**: Orchestrates sidecar + Vite startup. Allocates free loopback ports, starts both subprocesses with shared KENNISBANK_VAULT, polls sidecar health, prints launch URL, and runs until Ctrl-C or child exit.
  - **Location**: `atlas/launch.py:120-169`
  - **Signature**: No parameters. Exits via signal handler (`SIGINT`/`SIGTERM`).
  - **Dependencies**:
    - Internal: `_windows_kill_on_close_job()`, `_free_port()`, `_resolve_vault()`
    - External: `subprocess.Popen`, `urllib.request.urlopen`, `signal`, `time`, `os`, `sys`
  - **Behavior**:
    1. Creates Windows Job Object if on Windows (keeps child processes alive until launcher dies)
    2. Resolves vault path from `KENNISBANK_VAULT` env var (fails fast if unset)
    3. Allocates two free loopback ports (one per subprocess)
    4. Spawns `python3 -m atlas.sidecar --host 127.0.0.1 --port <port>` in `atlas/` parent dir
    5. Spawns `npx vite --host 127.0.0.1 --port <port> --strictPort` in `atlas/frontend/`
    6. Polls sidecar `/health` endpoint up to 40 times with 0.5s backoff
    7. Prints open URL with port query param: `http://127.0.0.1:<vite>/?port=<sidecar>`
    8. Loops monitoring child exit; on any exit or signal, terminates all children and quits

##### Function: `_windows_kill_on_close_job()`

- `_windows_kill_on_close_job() -> object | None`
  - **Description**: On Windows, creates a Windows Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and assigns the launcher process to it. This ensures the OS kills all child processes when the launcher dies, even if no signal handlers run (e.g., TaskManager kill, wrapper shell exit). On non-Windows, returns None.
  - **Location**: `atlas/launch.py:26-104`
  - **Signature**: No parameters. Returns opaque ctypes HANDLE or None.
  - **Rationale**: SIGTERM handlers do not run on Windows task termination, leaving sidecar and Vite orphans. A Job Object sidesteps the need for cooperative cleanup—children inherit membership automatically.
  - **Technical Detail**: Explicitly sets ctypes function prototypes (`restype` / `argtypes`) for 64-bit HANDLE correctness; without this, ctypes truncates HANDLEs to 32-bit, breaking `AssignProcessToJobObject`.
  - **Structure Details**:
    - Defines three ctypes Structures: `JOBOBJECT_BASIC_LIMIT_INFORMATION`, `IO_COUNTERS`, `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` (Windows API mirror)
    - Constants: `JobObjectExtendedLimitInformation = 9`, `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000`
    - Creates job via `kernel32.CreateJobObjectW(None, None)`
    - Sets limit info with kill flag via `SetInformationJobObject`
    - Assigns launcher to job via `AssignProcessToJobObject`
    - Closes job handle on failure (fail-open: returns None rather than hard error for compatibility with older Windows or incompatible parent jobs)

##### Function: `_free_port()`

- `_free_port() -> int`
  - **Description**: Finds and returns a free loopback port by binding a temporary TCP socket to `127.0.0.1:0` and reading the OS-assigned port.
  - **Location**: `atlas/launch.py:107-110`
  - **Signature**: No parameters. Returns port number as int.
  - **Dependencies**: `socket.socket`, `AF_INET`, `SOCK_STREAM`
  - **Behavior**: Binds to any available loopback port (OS picks via port 0), retrieves it via `getsockname()[1]`, and closes socket immediately.
  - **Note**: Two consecutive calls may return the same port if the first socket closes before the second binds (small race window, but acceptable for dev—binding happens immediately after).

##### Function: `_resolve_vault()`

- `_resolve_vault() -> str`
  - **Description**: Reads `KENNISBANK_VAULT` environment variable and returns it, or exits with error message if unset. Enforces ADR-0002 (no hardcoded paths).
  - **Location**: `atlas/launch.py:113-117`
  - **Signature**: No parameters. Returns vault path string or exits via `sys.exit()`.
  - **Dependencies**: `os.environ`, `sys.exit`
  - **Error Message**: "KENNISBANK_VAULT is niet gezet (ADR-0002; geen hardcoded default)."
  - **Rationale**: Portable across machines and vault names (e.g., `Kluis` on some systems); enforced at startup rather than later.

##### Inner Function: `_stop(*_)` (Signal Handler)

- `_stop(*_) -> None` (nested inside `main()`)
  - **Description**: Signal handler for `SIGINT` and `SIGTERM`. Gracefully terminates all spawned child processes by calling `.terminate()` on each, catching exceptions, then exits.
  - **Location**: `atlas/launch.py:130-136`
  - **Signature**: Takes `*_` (catches signal number + frame but ignores them).
  - **Behavior**: Iterates `procs` list, calls `.terminate()` on each (non-blocking), swallows exceptions, then `sys.exit(0)`.
  - **Registration**: Bound to `signal.SIGINT` and `signal.SIGTERM` at `main()` lines 138–139.

##### Module-Level Constant: `HERE` and `FRONTEND`

- `HERE = Path(__file__).resolve().parent` (line 22)
  - **Type**: `pathlib.Path`
  - **Value**: Absolute path to `atlas/` directory
  - **Usage**: Working directory for sidecar spawn (`cwd=HERE.parent`), and base for `FRONTEND`

- `FRONTEND = HERE / "frontend"` (line 23)
  - **Type**: `pathlib.Path`
  - **Value**: Absolute path to `atlas/frontend/`
  - **Usage**: Working directory for Vite spawn

---

#### `doctor.py` — Health & Readiness Checker

**Purpose**: Validates the entire Atlas stack before runtime: Python deps (FastAPI, uvicorn, httpx, sqlite-vec), Node/npm, Rust toolchain (optional, Tauri-only), Ollama (optional, recall-only), and vault stores. Exits 0 if no hard failures; warnings do not block.

##### Entry Point

- `main() -> int`
  - **Description**: Runs readiness checks and prints a summary. Returns exit code 0 if all hard dependencies met, 1 if any fail (Rust/Ollama are warnings only). Accepts optional `--port` to health-check a running sidecar.
  - **Location**: `atlas/doctor.py:30-97`
  - **Signature**: No parameters (argparse handles `--port`). Returns int exit code.
  - **Arguments** (CLI):
    - `--port <int>` (optional): Loopback port of a live sidecar to health-check via HTTP GET `/health`

##### Function: `_line()`

- `_line(status: str, label: str, detail: str = "") -> None`
  - **Description**: Prints one status line in format `[<status>] <label>[ - <detail>]`. Used for consistent reporting.
  - **Location**: `atlas/doctor.py:22-23`
  - **Signature**: `status` (str, one of "ok ", "warn", "FAIL"), `label` (str), `detail` (str, optional).
  - **Behavior**: Concatenates detail with " - " prefix if provided, prints to stdout.

##### Function: `_have_module()`

- `_have_module(name: str) -> bool`
  - **Description**: Checks if a Python module is importable by name without importing it (uses `importlib.util.find_spec`).
  - **Location**: `atlas/doctor.py:26-27`
  - **Signature**: `name` (str, e.g., "fastapi"). Returns bool.
  - **Purpose**: Avoid side effects of importing; `find_spec` returns None if not found, else a ModuleSpec.

##### Check Sequence (in `main()`)

1. **Sidecar Python Runtime Dependencies** (lines 38–48):
   - For each of ("fastapi", "uvicorn", "httpx"): check via `_have_module()` → print "ok" or "FAIL" with install hint
   - Separately check "sqlite_vec" (recall lens only) → "ok" or "FAIL"
   - Increment `failures` counter on any FAIL

2. **Frontend Toolchain** (lines 51–54):
   - Check `shutil.which("node")` → print "ok" or "FAIL" with install hint; increment `failures` if missing
   - Check `shutil.which("npm")` → print "ok" or "FAIL"; **does not** increment `failures` (npm is assumed to come with node)

3. **Rust Toolchain** (lines 57–59):
   - Check `shutil.which("cargo")` → print "ok" or **"warn"** (not FAIL); do not increment `failures`
   - Detail: "optional; install rustup for the standalone .exe (dev mode works without)"
   - **Rationale**: Rust is only needed for Tauri bundling (TASK-27.12); dev mode works without it

4. **Ollama** (lines 62–67):
   - Try HTTP GET `http://127.0.0.1:11434/api/version` with 1s timeout via httpx
   - Print "ok" if success, "warn" if exception
   - Detail: "not reachable; /recall degrades, other lenses fine"
   - **Rationale**: Recall lens is optional; other lenses function without Ollama

5. **Vault Stores** (lines 70–80):
   - Read `KENNISBANK_VAULT` from env
   - If unset, print warning "vault" label
   - If set, check existence of four store paths (all warnings, not failures):
     - `.claude/kb-index.db` (kb-index)
     - `.claude/kb-activity.db` (activity)
     - `graphify-out/graph.json` (graph)
     - `09-memory` (memory)

6. **Live Sidecar Health** (lines 83–92, only if `--port` passed):
   - Try HTTP GET `http://127.0.0.1:{port}/health` with 2s timeout
   - Parse JSON response, extract `status` field and list live sources
   - Print "ok" if `status == "ok"`, else "warn"
   - Detail: `{status} · bronnen: {', '.join(live_sources)}`
   - On exception: print "FAIL" with exception message; increment `failures`

7. **Summary** (lines 94–96):
   - Print final line: "ok" if `failures == 0`, "FAIL" otherwise
   - Detail: "klaar voor dev" if ready, else "{failures} harde fout(en)"
   - Return exit code (0 if ready, 1 if failures)

##### Status Constants (line 19)

- `OK = "ok "`, `WARN = "warn"`, `FAIL = "FAIL"`
  - Uppercase/formatting choices match status line display

---

### Configuration Files

#### `package.json` — Tauri CLI Configuration

**Purpose**: Declares the Tauri CLI as a dev dependency for bundling the standalone app (TASK-27.12). Used only at build time, not dev runtime.

**Contents**:
- `name`: "kennisbank-atlas"
- `private`: true (not published to npm)
- `version`: "0.1.0"
- `description`: "KennisBank Atlas standalone app (Tauri shell + frozen sidecar)"
- `scripts.tauri`: "tauri" (CLI entry point)
- `devDependencies`: "@tauri-apps/cli": "^2"

**Usage**: `npm run tauri` (or `npx @tauri-apps/cli`) in `atlas/src-tauri/` to build the bundled app.

#### `__init__.py` — Python Package Marker

**Purpose**: Empty marker file making `atlas/` a Python package. Allows `python3 -m atlas.sidecar` to resolve `atlas` as a package and descend to `sidecar` submodule.

#### `BUILD.md` — Standalone App Build Instructions

**Purpose**: Documents the multi-step process to freeze the sidecar (PyInstaller) and build the Tauri Windows app (MSI/NSIS installer). Covers:
- Prerequisites (Rust, PyInstaller, Node, WebView2 runtime)
- Step-by-step Windows build (sidecar freeze → Tauri build)
- Runtime model (shell picks port, spawns frozen sidecar, injects port into webview)
- Size expectations (Tauri <10 MB + sidecar tens of MB vs Electron 100+ MB)
- Code signing (out of scope; SmartScreen prompts on first run unsigned)

**Key Paths**:
- `atlas/sidecar/atlas-sidecar.spec` (PyInstaller spec)
- `atlas/src-tauri/binaries/atlas-sidecar-x86_64-pc-windows-msvc.exe` (frozen binary)
- `target/release/bundle/` (installer output)

#### `README.md` — Overview & Running

**Purpose**: User-facing guide covering:
- What Atlas is (sovereign, local-first dashboard for vault exploration)
- Seven shipped lenses (Overzicht, Graph, Graphify, Wordcloud, Time-slider, Memory Health, Recall)
- Requirements (Python 3.12+, Node 18+, Ollama, KENNISBANK_VAULT)
- Dev run: `python3 atlas/launch.py` (prints URL)
- Doctor: `python3 atlas/doctor.py [--port <port>]` (validates readiness)
- Tests (pytest for sidecar, npm test for frontend)
- Standalone app info (Tauri scaffold in `atlas/src-tauri/`)

---

## Dependencies

### Internal Dependencies

- **`atlas.sidecar`** — FastAPI backend (separate module, `atlas/sidecar/`, documented in `c4-code-atlas-sidecar.md`)
  - Entry point: `python3 -m atlas.sidecar`
  - API contract: HTTP endpoints `/health`, `/memory/decide`, etc. (documented in `docs/C4-Documentation/apis/`)
  - Health check: GET `/health` → JSON with `status` and `sources` dict

- **`atlas.frontend`** — TypeScript/Vite UI (separate tree, `atlas/frontend/`, documented in `c4-code-atlas-frontend.md`)
  - Entry point: `npx vite --host 127.0.0.1 --port <port>`
  - Port discovery: reads query param `?port=<sidecar_port>` from URL
  - Startup: waits for vite dev server, then browser opens

- **`atlas.src-tauri`** — Tauri shell (separate tree, `atlas/src-tauri/`, documented in `c4-code-atlas-tauri.md`)
  - Used only for bundled app (TASK-27.12)
  - Not involved in dev mode
  - Consumes frozen sidecar from `sidecar/dist/atlas-sidecar/` (PyInstaller output)

### External Dependencies

#### Python Standard Library
- `os` — environment variables, process names
- `sys` — exit, argv
- `signal` — SIGINT/SIGTERM handling
- `socket` — port discovery
- `subprocess` — spawn sidecar/vite as children
- `time` — sleep/polling
- `pathlib.Path` — path manipulation
- `ctypes` — Windows Job Object API (Windows only)
- `argparse` — CLI argument parsing (doctor.py)
- `importlib.util` — module detection (doctor.py)
- `shutil` — command lookup (doctor.py)
- `urllib.request` — sidecar health polling (launch.py)

#### External Tools
- **Python 3.12+** — runtime for launch.py and doctor.py
- **Node.js 18+** — npm/npx for Vite
- **npm** — package manager, Vite CLI
- **Ollama** — optional, for recall lens (http://127.0.0.1:11434)
- **Rust toolchain** (optional) — only for bundled app (cargo, rustup)
- **FastAPI, uvicorn, httpx** (Python packages) — sidecar runtime (installed via `pip install -r atlas/sidecar/requirements.txt`)
- **sqlite-vec** (Python package) — recall embeddings (optional, installed separately if needed)

#### Windows API (launch.py)
- `kernel32.dll`: CreateJobObjectW, SetInformationJobObject, AssignProcessToJobObject, GetCurrentProcess, CloseHandle

---

## Relationships

### Data Flow: Dev Launch

```
User invokes: python3 atlas/launch.py
        ↓
    main() 
        ├─→ _windows_kill_on_close_job() [Windows only]
        │   └─→ OS Job Object (kills all children on launcher exit)
        │
        ├─→ _resolve_vault() 
        │   └─→ KENNISBANK_VAULT env var (or fail fast)
        │
        ├─→ _free_port() × 2
        │   ├─→ sidecar_port
        │   └─→ vite_port
        │
        ├─→ spawn subprocess(python3 -m atlas.sidecar --host 127.0.0.1 --port {sidecar_port})
        │   └─→ KENNISBANK_VAULT inherited via env
        │
        ├─→ spawn subprocess(npx vite --host 127.0.0.1 --port {vite_port} --strictPort)
        │   └─→ KENNISBANK_VAULT inherited via env
        │
        ├─→ poll sidecar /health up to 40× (0.5s backoff)
        │   └─→ http://127.0.0.1:{sidecar_port}/health
        │
        ├─→ print launch URL: http://127.0.0.1:{vite_port}/?port={sidecar_port}
        │
        └─→ monitor children until exit or signal
            └─→ _stop() handler
                └─→ terminate all children + exit(0)
```

### Data Flow: Health Check

```
User invokes: python3 atlas/doctor.py [--port <port>]
        ↓
    main()
        ├─→ Check Python modules (fastapi, uvicorn, httpx, sqlite-vec)
        ├─→ Check CLI tools (node, npm, cargo [optional], ollama [optional])
        ├─→ Check vault stores (.claude/kb-index.db, .claude/kb-activity.db, etc.)
        └─→ [If --port] Check live sidecar health: GET http://127.0.0.1:{port}/health
                └─→ Parse JSON, extract status + sources
        ↓
    Print summary + exit(0 | 1)
```

### Process Tree: Dev Mode

```
┌─ launch.py (launcher, SIGINT/SIGTERM handler)
│  ├─ windows Job Object (if Windows) [owns launcher + children, kills all on close]
│  │
│  ├─ sidecar subprocess (python3 -m atlas.sidecar)
│  │  └─ FastAPI/uvicorn on 127.0.0.1:{sidecar_port}
│  │     └─ Reads vault stores (kb-index.db, kb-activity.db, graph.json, 09-memory/)
│  │        └─ Queries Ollama (optional, http://127.0.0.1:11434)
│  │
│  └─ vite subprocess (npx vite --host 127.0.0.1 --port {vite_port})
│     └─ TypeScript/React dev server
│        └─ Injects port query param into frontend
│           └─ Frontend queries sidecar: http://127.0.0.1:{sidecar_port}/...
```

### Mermaid Diagram: Atlas Launcher Architecture

```mermaid
---
title: C4 Code Diagram - Atlas Launcher Orchestration (launch.py)
---
classDiagram
    namespace AtlasLauncher {
        class launch_py {
            <<module>>
            +main() void
            +_windows_kill_on_close_job() object|None
            +_free_port() int
            +_resolve_vault() str
        }
        
        class SignalHandler {
            <<inner function>>
            +_stop(*_) void
        }
        
        class MainFlow {
            <<workflow>>
            +spawned_procs list[subprocess.Popen]
            +vault_path str
            +sidecar_port int
            +vite_port int
        }
    }
    
    namespace ExternalServices {
        class Sidecar {
            <<subprocess>>
            python3 -m atlas.sidecar
            --host 127.0.0.1
            --port <PORT>
        }
        
        class ViteServer {
            <<subprocess>>
            npx vite
            --host 127.0.0.1
            --port <PORT>
        }
        
        class HealthCheck {
            <<http endpoint>>
            GET /health
            → JSON{status, sources}
        }
    }
    
    namespace OperatingSystem {
        class JobObject {
            <<windows only>>
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            kills all children on launcher exit
        }
        
        class SignalHandler_OS {
            <<os signal>>
            SIGINT/SIGTERM
        }
    }
    
    namespace Environment {
        class VaultEnv {
            <<env var>>
            KENNISBANK_VAULT
            → vault path
        }
    }
    
    launch_py --> SignalHandler : registers
    launch_py --> MainFlow : orchestrates
    MainFlow --> Sidecar : spawn
    MainFlow --> ViteServer : spawn
    MainFlow --> HealthCheck : polls
    launch_py --> JobObject : creates [Windows]
    SignalHandler_OS --> SignalHandler : triggers
    VaultEnv --> launch_py : resolves path
    SignalHandler --> Sidecar : terminate
    SignalHandler --> ViteServer : terminate
```

### Mermaid Diagram: Atlas Doctor (doctor.py) Validation Stack

```mermaid
---
title: C4 Code Diagram - Atlas Doctor Health Checks (doctor.py)
---
classDiagram
    namespace AtlasDoctor {
        class doctor_py {
            <<module>>
            +main() int
            +_line(status, label, detail) void
            +_have_module(name) bool
        }
        
        class HealthCheckSuite {
            <<workflow>>
            +check_python_modules()
            +check_node_toolchain()
            +check_rust_toolchain()
            +check_ollama()
            +check_vault_stores()
            +check_live_sidecar()
        }
    }
    
    namespace PythonDeps {
        class FastAPI {
            <<python module>>
            required: sidecar web framework
        }
        
        class Uvicorn {
            <<python module>>
            required: ASGI server
        }
        
        class Httpx {
            <<python module>>
            required: health check + sidecar ops
        }
        
        class SqliteVec {
            <<python module>>
            optional: recall lens embeddings
        }
    }
    
    namespace FrontendToolchain {
        class Node {
            <<cli tool>>
            required: npm runtime
        }
        
        class Npm {
            <<cli tool>>
            required: vite + dependencies
        }
    }
    
    namespace OptionalTools {
        class Cargo {
            <<cli tool>>
            optional: Tauri bundling only (TASK-27.12)
        }
        
        class Ollama {
            <<external service>>
            optional: http://127.0.0.1:11434
            needed: recall lens only
        }
    }
    
    namespace VaultStores {
        class KBIndex {
            <<file>>
            .claude/kb-index.db
            required: wiki recall
        }
        
        class Activity {
            <<file>>
            .claude/kb-activity.db
            required: timeline/heatmap
        }
        
        class Graph {
            <<file>>
            graphify-out/graph.json
            required: graph lens
        }
        
        class Memory {
            <<directory>>
            09-memory/
            required: memory health lens
        }
    }
    
    namespace LiveServices {
        class SidecarHealth {
            <<http endpoint>>
            GET :{port}/health
            optional: full-stack validation
        }
    }
    
    doctor_py --> HealthCheckSuite : runs
    HealthCheckSuite --> FastAPI : checks
    HealthCheckSuite --> Uvicorn : checks
    HealthCheckSuite --> Httpx : checks
    HealthCheckSuite --> SqliteVec : checks
    HealthCheckSuite --> Node : checks
    HealthCheckSuite --> Npm : checks
    HealthCheckSuite --> Cargo : checks [optional]
    HealthCheckSuite --> Ollama : checks [optional]
    HealthCheckSuite --> KBIndex : validates
    HealthCheckSuite --> Activity : validates
    HealthCheckSuite --> Graph : validates
    HealthCheckSuite --> Memory : validates
    HealthCheckSuite --> SidecarHealth : checks [if --port]
```

### Integration: Launcher + Doctor

**Typical Workflow**:
1. User runs `python3 atlas/doctor.py` to validate readiness → "klaar voor dev" or error report
2. User runs `python3 atlas/launch.py` to start dev mode → prints launch URL
3. User opens printed URL in browser
4. Frontend (Vite) connects to sidecar (FastAPI) via loopback port
5. User interacts with lenses (Overzicht, Graph, Recall, etc.)
6. Ctrl-C stops both, signal handler terminates children

**Process Isolation**: Launcher does not validate; it assumes doctor has run. If deps missing, sidecar/vite spawn will fail (e.g., `ModuleNotFoundError`, `npm not found`). Doctor provides early, human-readable feedback.

---

## Architecture Notes

### Two-Runtime Model (ADR-0004)

Atlas bundles two separate runtime stacks:
1. **Python FastAPI sidecar** — vault query engine, knowledge graph traversal, memory review, recall (vector/FTS)
2. **TypeScript React frontend** — UI, state management, interactive lenses

Both run locally (no network calls except Ollama embeddings). Dev mode runs unbundled; standalone app (Tauri) freezes sidecar to Python-free `.exe` and wraps frontend in WebView2.

### Port Discovery

Both launcher and sidecar use ephemeral port allocation (bind to `:0`, let OS choose). This avoids conflicts when multiple instances run locally or tests run in parallel.

### Signal Handling

- **Unix**: `SIGINT`/`SIGTERM` handlers gracefully terminate children via `.terminate()` (SIGTERM cascade)
- **Windows**: Job Object handles launcher death (TaskManager kill, wrapper shell exit, no handler invocation needed). Explicit signal handlers present for compatibility but Windows rarely runs them

### Vault Path Portability (ADR-0002)

No hardcoded paths. All scripts read `KENNISBANK_VAULT` env var at startup, or fail fast. This enables:
- Multiple vault instances on one machine (e.g., test vs. production)
- Portable scripts across users/machines
- VM/container deployments with mounted vaults

---

## Files & Line References

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Launcher | `atlas/launch.py` | 1–173 | Entry point: `main()`, subprocess orchestration |
| Job Object | `atlas/launch.py` | 26–104 | Windows cleanup guarantee |
| Port Discovery | `atlas/launch.py` | 107–110 | Ephemeral port allocation |
| Vault Resolution | `atlas/launch.py` | 113–117 | ADR-0002 enforcement |
| Signal Handler | `atlas/launch.py` | 130–139 | Child process termination |
| Doctor | `atlas/doctor.py` | 1–101 | Readiness validation suite |
| Tauri Config | `atlas/package.json` | 1–13 | CLI + build deps |
| Package Marker | `atlas/__init__.py` | (empty) | Python module declaration |
| Build Guide | `atlas/BUILD.md` | 1–68 | Standalone app build steps |
| User Guide | `atlas/README.md` | 1–86 | Overview + running + lenses |

---

## Subdirectories (Documented Separately)

- **`atlas/sidecar/`** — FastAPI backend, vault stores, query engines
  - C4 Code documentation: `c4-code-atlas-sidecar.md`
  - Key modules: `main.py`, `health.py`, handlers (memory, graph, recall, etc.)

- **`atlas/frontend/`** — TypeScript/React UI, Vite bundler, lenses
  - C4 Code documentation: `c4-code-atlas-frontend.md`
  - Key modules: React components, state/hooks, API client

- **`atlas/src-tauri/`** — Tauri shell, Windows app, installer
  - C4 Code documentation: `c4-code-atlas-tauri.md`
  - Key modules: `main.rs` (Tauri app), `tauri.conf.json`, PyInstaller spec

---

## Related Documentation

- **ADR-0002**: Cross-platform scripts and vault path portability
- **ADR-0004**: Atlas architecture (two-runtime model)
- **ADR-007**: Tauri bundling and standalone app
- **TASK-27**: Atlas feature implementation (dev launcher, Tauri bundle, lenses)
- **Atlas README**: `atlas/README.md` — user-facing overview
- **Build Guide**: `atlas/BUILD.md` — standalone app build steps
- **Sidecar API**: `docs/C4-Documentation/apis/` — HTTP endpoint contracts

---

## Summary

The `atlas/` top-level code layer provides:
1. **Development launcher** (`launch.py`) — one-command startup (sidecar + frontend) with graceful shutdown
2. **Health validator** (`doctor.py`) — comprehensive pre-flight checks (deps, toolchain, vault stores, live services)
3. **Build configuration** (package.json, BUILD.md) — Tauri CLI integration and standalone app bundling
4. **Coordination** between FastAPI sidecar and TypeScript frontend, both running on loopback with port negotiation

All code enforces ADR-0002 (vault path portability) and ADR-0004 (two-runtime architecture).
