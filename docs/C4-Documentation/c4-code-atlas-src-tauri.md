# C4 Code Level: Atlas Tauri Desktop Shell

## Overview

- **Name**: KennisBank Atlas Tauri Shell
- **Description**: Minimal Tauri v2 webview host for KennisBank Atlas. Manages WebView2 frontend lifecycle, negotiates ephemeral loopback port for Python sidecar, and maintains sidecar process ownership. Zero Rust business logic per ADR-0004: pure infrastructure.
- **Location**: `atlas/src-tauri/` — [ADR-0004 reference](../../docs/adr/0004-atlas-tauri-architecture.md)
- **Language**: Rust 2021 edition (minimal); TypeScript/JavaScript frontend (separate)
- **Purpose**: Desktop application shell for the KennisBank Atlas knowledge dashboard. Provides:
  1. Native OS webview (WebView2 on Windows) to host the reactive frontend
  2. Sidecar process spawning and lifecycle management
  3. Port negotiation: discovers free loopback port and injects it into frontend
  4. Process cleanup: sidecar dies with the app (no orphans)
  5. Content Security Policy enforcement (localhost-only connections)
  6. Application bundling for Windows (MSI/NSIS installers)

## Code Elements

### Functions

#### `free_port() -> u16`
- **Location**: `src/main.rs:22-28`
- **Signature**: `fn free_port() -> u16`
- **Description**: Discovers a free ephemeral loopback port by binding a TCP listener to `127.0.0.1:0`, retrieving the assigned port, and dropping the listener. Used to negotiate sidecar binding port at startup.
- **Dependencies**:
  - `std::net::TcpListener` — standard library TCP socket binding
- **Behavior**: 
  - Binds to wildcard ephemeral port (OS assigns next available)
  - Panics with "bind ephemeral port" if binding fails (e.g., no loopback available)
  - Returns the OS-assigned port number as `u16`
  - Listener is dropped immediately; port remains available for sidecar

#### `main()`
- **Location**: `src/main.rs:30-67`
- **Signature**: `fn main()`
- **Description**: Application entry point. Assembles Tauri app with shell plugin, runs setup hook to spawn sidecar, and starts the event loop. Panics if any critical step fails (no graceful degradation at startup).
- **Setup Flow**:
  1. Create Tauri builder with shell plugin enabled
  2. Register setup hook (runs before webview creates)
  3. Inside setup: discover free port via `free_port()`
  4. Spawn sidecar binary `atlas-sidecar` with `--host 127.0.0.1` and `--port {port}`
  5. Drain sidecar stdout/stderr in async task (prevents blocking if sidecar fills buffers)
  6. Create main webview window with initialization script injecting port
  7. Build and run Tauri event loop
- **Panics**:
  - "atlas-sidecar binary is bundled" if sidecar exe not found in bundle
  - "spawn sidecar" if process spawn fails (e.g., permissions, binary not executable)
  - "run KennisBank Atlas" if event loop fails (rare; indicates OS-level issue)
- **Environment**:
  - Inherits `KENNISBANK_VAULT` environment variable; sidecar receives it by process inheritance
  - Windows subsystem: configured via `#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]` to suppress console window in production builds
- **Dependencies**:
  - `tauri::Manager`, `tauri::Builder`, `tauri::WebviewUrl`, `tauri::WebviewWindowBuilder` — Tauri framework core
  - `tauri_plugin_shell::{process::CommandEvent, ShellExt}` — process spawning plugin
  - `tauri::async_runtime::spawn` — tokio-backed async task for log draining

### Initialization Script

#### Port Injection Script (Embedded in `main()`)
- **Location**: `src/main.rs:56`
- **Template**: `format!("window.__ATLAS_PORT__ = {};", port)`
- **Description**: JavaScript injected into the webview before the frontend loads. Sets a global variable `window.__ATLAS_PORT__` to the negotiated port number. Frontend's `data-client.ts` reads this value to establish connection to sidecar.
- **Frontend Consumer**: `atlas/frontend/src/data-client.ts:87-93` (`resolvePort()` function reads `window.__ATLAS_PORT__` first, falls back to URL query param `?port=NNNN` in dev mode)

## Configuration

### tauri.conf.json
**File**: `tauri.conf.json`

| Key | Value | Purpose |
| --- | --- | --- |
| `productName` | "KennisBank Atlas" | App name in window title, installer, system menus |
| `version` | "0.1.0" | Semantic version (increment for releases) |
| `identifier` | "net.vandenbreemen.kennisbank.atlas" | Unique macOS/Windows app identifier (reverse DNS) |
| `build.frontendDist` | "../frontend/dist" | Path to compiled SPA assets (relative to src-tauri/) |
| `build.devUrl` | "http://127.0.0.1:5173" | Dev server URL for `cargo tauri dev` (Vite runs on 5173) |
| `build.beforeDevCommand` | "npm --prefix frontend run dev" | Runs frontend dev server before Tauri dev watcher |
| `build.beforeBuildCommand` | "npm --prefix frontend run build" | Builds optimized frontend SPA before release build |
| `app.security.csp` | `default-src 'self'; connect-src http://127.0.0.1:*; ...` | Content Security Policy — restricts all resource loads to self + localhost |
| `bundle.active` | true | Enable bundling for release builds |
| `bundle.targets` | `["msi", "nsis"]` | Windows installer formats (MSI for silent installs, NSIS for GUI) |
| `bundle.icon` | `["icons/icon.ico"]` | Path to app icon (converted to .icns, etc. per platform) |
| `bundle.resources` | `{"binaries/_internal": "_internal"}` | Bundles PyInstaller `_internal/` directory (Python stdlib, libs) into installer root as `_internal/` |
| `bundle.externalBin` | `["binaries/atlas-sidecar"]` | External binary to bundle; Tauri auto-renames to platform triple (e.g., `-x86_64-pc-windows-msvc.exe`) |

**CSP Breakdown**:
```
default-src 'self'                         → all resources from package by default
connect-src http://127.0.0.1:*             → fetch/XHR/WebSocket only to 127.0.0.1 (any port)
img-src 'self' http://127.0.0.1:* data:   → images from self, localhost, or data: URIs
style-src 'self' 'unsafe-inline'           → CSS from self + inline <style> (required by SPA)
frame-src http://127.0.0.1:*               → <iframe> content from localhost
```

**Sidecar Binary Placement**: The frozen Python sidecar (PyInstaller artifact) lives at:
- Source: `atlas/sidecar/dist/atlas-sidecar/atlas-sidecar.exe` + `_internal/`
- Bundled path: `atlas/src-tauri/binaries/atlas-sidecar-x86_64-pc-windows-msvc.exe` (platform-specific triple appended by build.rs)
- Runtime access: Tauri CLI auto-renames and places the exe in the installer; sidecar locates itself via `$PATH` or bundled location

### Cargo.toml
**File**: `Cargo.toml`

```toml
[package]
name = "kennisbank-atlas"
version = "0.1.0"
edition = "2021"
description = "KennisBank Atlas - local-first knowledge/memory dashboard"
```

**Dependencies**:
| Crate | Version | Role |
| --- | --- | --- |
| `tauri` | 2 | Core Tauri framework (webview, IPC, app lifecycle) |
| `tauri-plugin-shell` | 2 | Process spawning plugin (for sidecar) |
| `serde` | 1 with `derive` | Serialization (used in Tauri IPC; not in this shell's code) |
| `serde_json` | 1 | JSON parsing (used in Tauri framework) |
| `tauri-build` | 2 (build-dep) | Tauri build script macro (generates context in build.rs) |

**Features**:
- `custom-protocol`: opt-in feature to use custom `tauri://` protocol (not enabled in current config)

### build.rs
**File**: `build.rs`

```rust
fn main() {
    tauri_build::build()
}
```

**Purpose**: Calls `tauri_build::build()` macro, which:
1. Parses `tauri.conf.json` and `Cargo.toml`
2. Generates the Tauri context (bundled assets, app config) at compile time
3. Makes resources available via `tauri::generate_context!()` macro in `main.rs`

No custom build logic; entirely standard Tauri setup.

## Dependencies

### Internal Code Dependencies

```
src/main.rs
├── calls: tauri::Builder::default()
├── calls: tauri_plugin_shell::init()
├── calls: app.shell().sidecar() → spawns atlas-sidecar process
├── calls: WebviewWindowBuilder → creates webview window
└── calls: tauri::generate_context!() → macro that pulls config from build.rs
    └── depends on: build.rs (build-time codegen)
    └── depends on: tauri.conf.json (configuration)
    └── depends on: ../frontend/dist (SPA assets, injected into webview)

Initialization Script
├── injected into: webview document.head before frontend loads
└── consumed by: ../frontend/src/data-client.ts::resolvePort()
```

### External Crates (Dependencies)

**Direct**:
- `tauri 2.x` — webview, app lifecycle, IPC framework
- `tauri-plugin-shell 2.x` — `Command` and `CommandEvent` for process spawning
- `serde 1.x` — serialization traits (used transitively by Tauri)
- `serde_json 1.x` — JSON codec (used transitively by Tauri)

**Build-time**:
- `tauri-build 2.x` — build script that generates Tauri context

**Transitive** (pulled by Tauri; not directly used):
- `tokio` — async runtime (used for event loop and sidecar I/O)
- `wry` — webview backend (wraps WebView2 on Windows, WKWebView on macOS)
- `winapi` / `cocoa` — platform-specific bindings (used by Tauri, not by this code)

### System Dependencies (Runtime)

**Windows**:
- **WebView2 Runtime** — provides the native webview (usually pre-installed on Windows 11; installer can bundle it)
- **PyInstaller frozen sidecar** — `atlas-sidecar.exe` + `_internal/` (Python runtime, dependencies)

**macOS** (future; not implemented yet):
- **WKWebView** — built into OS
- **Frozen sidecar** (arm64 or x86_64)

## Relationships

### Process Topology

```
┌─────────────────────────────────────────────────────────────┐
│  Windows Desktop User Session                               │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  KennisBank Atlas Tauri App (kennisbank-atlas.exe)     │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  WebView2 (Native OS Webview)                    │  │ │
│  │  │  ┌────────────────────────────────────────────┐  │  │ │
│  │  │  │  Frontend SPA (TypeScript)                 │  │  │ │
│  │  │  │  ├─ main.ts (tab router, shell)           │  │  │ │
│  │  │  │  ├─ data-client.ts (HTTP client)          │  │  │ │
│  │  │  │  ├─ lenses/* (six visualization lenses)   │  │  │ │
│  │  │  │  └─ Reads: window.__ATLAS_PORT__         │  │  │ │
│  │  │  └────────────────────────────────────────────┘  │  │ │
│  │  │  ↓ HTTP (localhost-only, CSP-enforced)        │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │  ↓ Spawns and owns lifecycle (tauri-plugin-shell)  │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  atlas-sidecar.exe (Frozen Python)              │  │ │
│  │  │  ├─ FastAPI app                                │  │ │
│  │  │  ├─ /health, /graph, /timeline, /memory-health │  │ │
│  │  │  ├─ /recall, /provenance                       │  │ │
│  │  │  └─ Binds: 127.0.0.1:{negotiated-port}       │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │     ↓ Reads (async tasks)                           │ │
│  │     ├─ Local KennisBank vault (KENNISBANK_VAULT env) │ │
│  │     │  ├─ kb-index.db (SQLite)                      │ │
│  │     │  ├─ kb-activity.db (temporal events)          │ │
│  │     │  ├─ 09-memory/ (bi-temporal memory entries)   │ │
│  │     │  ├─ 02-wiki/ (markdown documents)             │ │
│  │     │  └─ graphify-out/graph.json (knowledge graph) │ │
│  │     └─ Local Ollama (http://127.0.0.1:11434) [recall only] │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  No outbound network; all processing is local & synchronous│ │
│  Sidecar lifecycle: spawned at app start → killed at close │ │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow: Port Negotiation & Sidecar Startup

```mermaid
---
title: Tauri Shell Startup Sequence
---
flowchart LR
    subgraph App["App Startup (Rust)"]
        A["tauri::Builder::default()"]
        B["register setup() hook"]
        C["free_port() → u16"]
        D["shell.sidecar()"]
        E["spawn(atlas-sidecar)"]
        F["inject init script"]
        G["WebviewWindowBuilder"]
    end
    
    subgraph Frontend["Frontend (TypeScript)"]
        H["HTML loads"]
        I["script injected: window.__ATLAS_PORT__ = port"]
        J["main.ts executes"]
        K["data-client.resolvePort()"]
        L["connectSidecar()"]
        M["fetch(/health)"]
    end
    
    subgraph Sidecar["Sidecar Process (Python)"]
        N["atlas-sidecar.exe starts"]
        O["--host 127.0.0.1 --port {port}"]
        P["FastAPI app.run()"]
        Q["Listen on 127.0.0.1:{port}"]
    end
    
    subgraph Backend["Vault & Services"]
        R["KENNISBANK_VAULT env"]
        S["Load kb-index.db, etc"]
        T["Connect to local Ollama"]
    end
    
    A → B → C
    C ⇌ D → E
    E ⇌ N → O → P → Q
    C ← E
    F → G
    G → H → I → J → K → L → M
    E ← R → S
    P ← T
    M ⇌ Q
    
    classDef rust fill:#f96,stroke:#333,stroke-width:2px
    classDef ts fill:#0099ff,stroke:#333,stroke-width:2px
    classDef py fill:#306998,stroke:#ffd43b,stroke-width:2px,color:#fff
    classDef storage fill:#999,stroke:#333,stroke-width:2px,color:#fff
    
    class A,B,C,D,E,F,G rust
    class H,I,J,K,L,M ts
    class N,O,P,Q py
    class R,S,T storage
```

### Rust Startup Flow (Pseudocode)

```rust
// main() execution sequence
1. tauri::Builder::default()
2.   .plugin(tauri_plugin_shell::init())  // enable Command spawn
3.   .setup(|app| {
4.     let port = free_port()              // OS allocates → u16
5.     let (mut rx, _child) = app
6.       .shell()
7.       .sidecar("atlas-sidecar")        // locate exe in bundle
8.       .args(["--host", "127.0.0.1", "--port", &port.to_string()])
9.       .spawn()                          // fork process
10.      .expect("spawn sidecar")
11.
12.    tauri::async_runtime::spawn(async move {
13.      while let Some(event) = rx.recv().await {
14.        if let CommandEvent::Stderr(line) = event {
15.          eprintln!("[sidecar] {}", ...)  // drain stderr to prevent deadlock
16.        }
17.      }
18.    })
19.
20.    let init = format!("window.__ATLAS_PORT__ = {};", port)
21.    WebviewWindowBuilder::new(app, "main", WebviewUrl::default())
22.      .title("KennisBank Atlas")
23.      .inner_size(1400.0, 900.0)
24.      .initialization_script(&init)
25.      .build()?
26.
27.    Ok(())
28.  })
29. .run(tauri::generate_context!())
30.  .expect("run KennisBank Atlas")
```

### Frontend Startup Flow (Pseudocode)

```typescript
// frontend/src/main.ts flow
1. import { DataClient } from "./data-client"
2. const client = new DataClient()                // reads window.__ATLAS_PORT__
3.
4. async function connectSidecar(bar) {
5.   if (!client.configured) {
6.     bar.textContent = "geen sidecar-poort"     // no port injection
7.     return false
8.   }
9.   // Poll /health with retry (sidecar cold-boot takes seconds)
10.  const health = await client.health()
11.  if (!health) {
12.    bar.textContent = "Connecting to sidecar..."
13.    await retry(...)                           // exponential backoff
14.  }
15.  renderAllLenses()
16. }
```

### Sidecar Communicates Back to Frontend

```
Frontend HTTP GET → http://127.0.0.1:{port}/graph
                    http://127.0.0.1:{port}/health
                    http://127.0.0.1:{port}/recall?q=...
                    etc.
                ↓
Sidecar FastAPI handler reads req
                ↓
Query local vault (kb-index.db, memory/, graph.json, Ollama)
                ↓
Return JSON { status, data... }
                ↓
Frontend JSON.parse() → renders lens
```

### Code Diagram: Rust Shell Structure

```mermaid
---
title: Tauri Shell Code Organization
---
classDiagram
    namespace RustShell {
        class Main {
            fn main()
            -Builder builder
            -setup_hook hook
        }
        class PortDiscovery {
            fn free_port() u16
            -TcpListener listener
        }
        class ProcessManagement {
            <<interface>>
            +spawn() → Process
            +recv_events() → CommandEvent
        }
        class WebviewHost {
            fn build_window()
            -WebviewWindowBuilder builder
            -init_script init
        }
        class Config {
            <<config>>
            tauri.conf.json
            Cargo.toml
        }
    }
    
    namespace Frontend {
        class DataClient {
            -base_url string
            +health() Promise
            +graph() Promise
            +recall() Promise
        }
        class PortResolution {
            fn resolvePort()
            -window.__ATLAS_PORT__
            -URLSearchParams
        }
    }
    
    Main --> PortDiscovery : calls
    Main --> ProcessManagement : uses
    Main --> WebviewHost : builds
    Main --> Config : reads at build-time
    WebviewHost --> Frontend : injects init script
    DataClient --> PortResolution : uses
```

## Architectural Notes

### Why Minimal Rust?

Per ADR-0004, the Rust shell is intentionally thin:
- **No business logic** in Rust (no ranking, recall, graph algorithms)
- **One responsibility**: host the webview + manage sidecar lifecycle
- **Rationale**: reduces build-time Rust toolchain dependency, minimizes attack surface, keeps app weight under 10 MB (vs 100+ MB for Electron)
- **Tradeoff**: requires two runtimes at packaging time (Python sidecar + Rust shell)

### Process Ownership & Lifecycle

| Phase | Owner | Action |
| --- | --- | --- |
| **Launch** | Rust shell (`main.rs`) | `tauri-plugin-shell` spawns sidecar, holds process handle |
| **Running** | Shell + sidecar | Shell drains stderr/stdout; sidecar serves HTTP requests; frontend polls `/health` |
| **Shutdown** | Shell | When user closes app window, Tauri drops `_child` handle → process terminated |
| **No orphan** | Guaranteed | tauri-plugin-shell manages the handle; process is owned by shell, not detached |

### Loopback-Only Security Boundary

- **Sidecar binding**: `--host 127.0.0.1 --port {ephemeral}` (never `0.0.0.0`)
- **Frontend CSP**: `connect-src http://127.0.0.1:*` (blocks all external domains)
- **No cloud**: sidecar reads only local vault, calls only local Ollama (if enabled)
- **Single-user desktop**: trust boundary is the local machine; multi-user scenarios would need per-session tokens (not implemented; not a requirement for single-user desktop app)

### Cold Start & Retry Logic

PyInstaller-frozen sidecar has measurable cold-boot delay (seconds on first launch; Python runtime initialization, imports, etc.). Frontend implements retry with exponential backoff in `connectSidecar()` (see `frontend/src/main.ts:50-ish`) rather than failing immediately on the first failed fetch.

## Testing & Validation

**Acceptance Smoke Test** (from ADR-0004, gate for TASK-27.10):
1. App starts as a Tauri app (WebView2 loads bundled frontend)
2. Sidecar spawns and `/health` is green
3. Graph lens renders against real data (2514 nodes, performant)
4. Live recall works: `/recall` waterfall returns ordered results
5. Sidecar shuts down with the app (no orphan process)

**Manual validation checklist**:
- [ ] `cargo tauri dev` starts dev webview with local Vite dev server
- [ ] Sidecar binary placed at `atlas/src-tauri/binaries/atlas-sidecar-{platform}.exe`
- [ ] `tauri.conf.json` paths match filesystem (frontendDist, icons, etc.)
- [ ] Python sidecar dependencies frozen in PyInstaller `_internal/` directory
- [ ] Windows installer created in `target/release/bundle/msi/` or `/nsis/`
- [ ] Installer runs without Rust or Python pre-installed

## Build & Deployment

**Build Prerequisites** (dev machine only):
- Rust toolchain via rustup (`cargo`)
- Tauri CLI: `npm i -g @tauri-apps/cli` or `cargo install tauri-cli`
- WebView2 runtime (Windows 11+ includes it; installer can bundle)
- PyInstaller for freezing sidecar
- Node.js + npm for frontend

**Build Steps** (see `atlas/BUILD.md`):
```bash
# 1. Freeze sidecar
cd atlas/sidecar
pyinstaller atlas-sidecar.spec

# 2. Place sidecar in Tauri binaries directory
cp dist/atlas-sidecar/atlas-sidecar.exe ../src-tauri/binaries/atlas-sidecar-x86_64-pc-windows-msvc.exe
cp -r dist/atlas-sidecar/_internal ../src-tauri/binaries/

# 3. Build Tauri app + frontend
cd ../src-tauri
npx @tauri-apps/cli build  # also runs beforeBuildCommand (npm run build)

# 4. Installers in target/release/bundle/
```

**Distribution**:
- Installers are in `target/release/bundle/msi/` (silent MSI) and `/nsis/` (interactive NSIS)
- Code signing: out of scope; unsigned installers trigger SmartScreen prompt
- No external dependencies; app is self-contained

## ADR References

- **ADR-0004**: [KennisBank Atlas as a local-first Tauri standalone app](../../docs/adr/0004-atlas-tauri-architecture.md) — architectural decisions, sidecar API contract, enforcement invariants
- **ADR-0007** (OralHistoryAgent): Similar pattern (native webview + frozen Python sidecar)

## Files in This Component

```
atlas/src-tauri/
├── src/
│   └── main.rs                  # Tauri shell: free_port(), main()
├── build.rs                     # Build script: calls tauri_build::build()
├── Cargo.toml                   # Rust dependencies
├── Cargo.lock                   # Dependency lock (auto-generated)
├── tauri.conf.json              # App config: frontend paths, CSP, bundle settings
├── binaries/
│   ├── atlas-sidecar-x86_64-pc-windows-msvc.exe  # Frozen sidecar exe
│   └── _internal/               # PyInstaller Python runtime & deps
├── icons/
│   └── icon.ico                 # App icon (generated from icon-src.png)
└── target/                      # Build artifacts (excluded from docs)
    └── release/
        └── bundle/              # Windows installers (MSI, NSIS)
```

**Related Frontend Code**:
- `atlas/frontend/src/main.ts` — app shell, tab router, sidecar handshake
- `atlas/frontend/src/data-client.ts` — HTTP client, port resolution
- `atlas/frontend/src/lenses/*.ts` — six visualization lenses

**Related Backend Code**:
- `atlas/sidecar/` — FastAPI app (separate C4 documentation)
- `atlas/sidecar/atlas-sidecar.spec` — PyInstaller spec file

---

**Document Generated**: 2026-08-17  
**Revision**: Initial C4 Code-level documentation for atlas/src-tauri  
**Scope**: Rust shell only (frontend and sidecar documented separately)
