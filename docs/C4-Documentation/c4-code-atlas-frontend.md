# C4 Code Level: Atlas Frontend

## Overview

- **Name**: KennisBank Atlas Frontend
- **Description**: Tauri desktop application frontend—a six-lens tab-shell interface over the localhost sidecar, built with Vite and TypeScript. Provides navigation, status reporting, and multiple visualization/interaction modes for KennisBank vault exploration.
- **Location**: [atlas/frontend](../../atlas/frontend/) (repository root: `D:/Users/Robert/Documents/GitHub/RvdB/LLmWiki-KennisBank`)
- **Language**: TypeScript + HTML + CSS (Module ESNext build target)
- **Purpose**: Frontend shell for the Tauri desktop application, handling UI layout (tabs, statusbar, lens panes), markdown/graph rendering, and user interaction with the localhost KennisBank sidecar API.

## Code Elements

### Configuration Files

#### package.json
- **Location**: `atlas/frontend/package.json`
- **Purpose**: Node.js package configuration and build script definitions
- **Key Settings**:
  - **name**: `kennisbank-atlas-frontend`
  - **version**: `0.1.0`
  - **type**: `"module"` (ES modules enabled)
  - **private**: `true` (not published to npm)
  - **description**: "KennisBank Atlas frontend: six-lens tab-shell over the localhost sidecar (TASK-27.3)."
  
- **Build Scripts** (lines 7-11):
  - `dev`: `vite` — starts local dev server with hot reload
  - `build`: `tsc --noEmit && vite build` — type-check then build optimized bundle to `dist/`
  - `preview`: `vite preview` — preview built bundle locally
  - `test`: `vitest run` — run unit tests once (no watch mode)

- **Development Dependencies** (lines 13-18):
  - `typescript@^5.6.0` — TypeScript compiler and type definitions
  - `vite@^5.4.0` — build tool and dev server
  - `vitest@^4.1.10` — unit test framework (Vite-native)
  - `@types/markdown-it@^14.1.2` — TypeScript type definitions for markdown-it library

- **Production Dependencies** (lines 19-29):
  - `markdown-it@^14.3.0` — Markdown parser and renderer
  - `markdown-it-footnote@^4.0.0` — Markdown footnote syntax extension
  - `markdown-it-task-lists@^2.1.1` — Markdown task list (checkbox) extension
  - `dompurify@^3.4.12` — HTML sanitizer (prevents XSS in rendered content)
  - `highlight.js@^11.11.1` — Syntax highlighting for code blocks
  - `katex@^0.17.0` — Math typesetting (LaTeX rendering)
  - `@vscode/markdown-it-katex@^1.1.2` — KaTeX plugin for markdown-it
  - `mermaid@^11.16.0` — Diagram and flowchart rendering (UML, state, sequence, etc.)
  - `force-graph@^1.49.0` — 3D/2D force-directed graph visualization

#### tsconfig.json
- **Location**: `atlas/frontend/tsconfig.json`
- **Purpose**: TypeScript compiler configuration for the frontend
- **Key Settings** (lines 2-11):
  - **target**: `ES2020` — compile TypeScript to ES2020 JavaScript (no legacy polyfills)
  - **module**: `ESNext` — output native ES modules (Vite preserves these for tree-shaking)
  - **moduleResolution**: `bundler` — use bundler semantics (Vite's default, treats `package.json` `exports` field)
  - **strict**: `true` — enable all strict type checking flags
  - **noUnusedLocals**: `true` — error on unused local variables
  - **noUnusedParameters**: `true` — error on unused function parameters
  - **skipLibCheck**: `true` — skip type-checking of `node_modules` (faster compilation)
  - **lib**: `["ES2020", "DOM", "DOM.Iterable"]` — include ES2020 built-ins, DOM APIs, and iterable DOM collections
  - **types**: `[]` — empty (no auto-included type definitions, explicit via imports)

- **Include** (line 13):
  - **include**: `["src"]` — compile only the `src/` directory

#### index.html
- **Location**: `atlas/frontend/index.html`
- **Purpose**: HTML entry point for the Tauri webview
- **Key Elements** (lines 1-16):
  - **DOCTYPE**: `html` (HTML5)
  - **lang**: `"nl"` — Dutch language (KennisBank is Dutch-language)
  - **meta charset**: `UTF-8` — character encoding
  - **meta viewport**: `width=device-width, initial-scale=1.0` — responsive mobile viewport
  - **title**: `"KennisBank Atlas"` — browser tab title
  
- **Body Structure** (lines 8-15):
  - **Container `#app`**: root React/JS mount point for the entire application
  - **Navigation `#tabs`**: container for the six-lens tab navigation shell
  - **Statusbar `#statusbar`**: container for status indicators and metadata display
  - **Main `#lens`**: container for the active lens/pane rendering (markdown, graph, etc.)
  - **Module Script**: `<script type="module" src="/src/main.ts"></script>` — loads TypeScript entry point at build time

#### .gitignore
- **Location**: `atlas/frontend/.gitignore`
- **Purpose**: Exclude build artifacts and dependencies from version control
- **Contents** (lines 1-2):
  - `node_modules/` — npm dependencies (large, not version-controlled)
  - `dist/` — build output (generated at build time)

### Build and Runtime Behavior

#### Vite Configuration
- **Configuration Mode**: No explicit `vite.config.ts` — uses Vite 5.4.0 default configuration
- **Default Behaviors**:
  - **Development Server**: runs on `http://localhost:5173` by default (Vite dev server)
  - **Build Output**: `dist/` directory with optimized, tree-shaken bundles
  - **Entry Point**: `index.html` (auto-detected by Vite)
  - **Module Resolution**: ES modules with bundler semantics
  - **Hot Module Reload (HMR)**: enabled in dev mode for instant feedback

#### Build Pipeline
1. **Type Check**: `tsc --noEmit` validates all TypeScript without emitting output
2. **Bundle**: `vite build` creates optimized production bundle
3. **Output**: Minified JavaScript, CSS, and assets in `dist/`
4. **Tauri Integration**: Tauri build process copies `dist/` into the bundled application

## Dependencies

### Internal Dependencies
- `./src/main.ts` — TypeScript entry point (loaded by index.html)
- `./src/` tree — all TypeScript/JavaScript source files (documented separately)
- `./dist/` — build output directory (generated, documented separately)

### External Dependencies

#### Runtime Dependencies (in `package.json` `dependencies`)
| Package | Version | Purpose |
|---------|---------|---------|
| `markdown-it` | ^14.3.0 | Markdown parsing and rendering engine |
| `markdown-it-footnote` | ^4.0.0 | Support for footnote syntax in Markdown |
| `markdown-it-task-lists` | ^2.1.1 | Support for GitHub-style task lists (checkboxes) |
| `dompurify` | ^3.4.12 | HTML sanitization (prevents XSS attacks in rendered content) |
| `highlight.js` | ^11.11.1 | Syntax highlighting for code blocks in Markdown |
| `katex` | ^0.17.0 | Math typesetting engine (LaTeX/AMS-LaTeX rendering) |
| `@vscode/markdown-it-katex` | ^1.1.2 | KaTeX plugin for markdown-it (LaTeX in Markdown) |
| `mermaid` | ^11.16.0 | Diagram rendering (UML, flowcharts, sequence, state, etc.) |
| `force-graph` | ^1.49.0 | 3D/2D force-directed graph visualization library |

#### Development Dependencies (in `package.json` `devDependencies`)
| Package | Version | Purpose |
|---------|---------|---------|
| `typescript` | ^5.6.0 | TypeScript compiler and language support |
| `vite` | ^5.4.0 | Build tool, bundler, and dev server |
| `vitest` | ^4.1.10 | Unit test framework (Vite-native, supports ES modules) |
| `@types/markdown-it` | ^14.1.2 | TypeScript type definitions for markdown-it library |

#### System/Tauri Dependencies (external to frontend package)
- **Tauri Runtime** — provides native OS bindings (window, filesystem, process, IPC)
- **WebView2** (Windows) / **WKWebKit** (macOS) / **WebKit** (Linux) — renders the frontend
- **Localhost Sidecar** — KennisBank backend API accessible at `http://localhost:8080` (or configured port)

## Relationships

### Tauri Integration
```
┌─────────────────────────────────────────┐
│         Tauri Application               │
│  ┌──────────────────────────────────┐   │
│  │   WebView (index.html)           │   │
│  │  ┌──────────────────────────────┐│   │
│  │  │ Frontend (src/main.ts)       ││   │
│  │  │  - Tabs shell                ││   │
│  │  │  - Status bar                ││   │
│  │  │  - Lens panes (6 modes)      ││   │
│  │  │  - Markdown/Graph rendering  ││   │
│  │  └──────────────────────────────┘│   │
│  └──────────────────────────────────┘   │
│           │ API calls                   │
│           v                             │
│  ┌──────────────────────────────────┐   │
│  │   Localhost Sidecar              │   │
│  │   (KennisBank backend, frozen)   │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

### Rendering Pipeline
1. **Markdown Source** → `markdown-it` parser → parsed AST
2. **AST** → `highlight.js` (code blocks) + `katex` (math) → HTML
3. **HTML** → `dompurify` sanitizer → safe DOM
4. **Diagrams** → `mermaid` renderer → SVG/canvas
5. **Graphs** → `force-graph` layout engine → 2D/3D visualization
6. **DOM** → browser renderer → visible UI

### Development Workflow
```
src/ (TypeScript source)
  ↓
  vite dev (watch + HMR)
  ↓
  http://localhost:5173 (dev server + Tauri bridge)
  ↓
  browser/WebView (live reload)
```

### Production Workflow
```
src/ (TypeScript source)
  ↓
  tsc --noEmit (type checking)
  ↓
  vite build (bundling + minification)
  ↓
  dist/ (optimized output)
  ↓
  Tauri build (embed in app)
  ↓
  .exe/.dmg/.AppImage (platform-specific binary)
```

## Build Outputs

### Distribution Directory (`dist/`)
- **Generated by**: `npm run build` (Vite build process)
- **Contents**:
  - `index.html` (minified, with script/style references updated)
  - JavaScript bundles (tree-shaken, minified, code-split if configured)
  - CSS bundles (minified)
  - Assets (images, fonts, etc. if any)
- **Consumed by**: Tauri build process (embedded in executable)
- **Not version-controlled**: excluded via `.gitignore`

## Configuration Rationale

| Setting | Rationale |
|---------|-----------|
| `type: "module"` | ES modules are the standard for modern JavaScript; Vite prefers native ESM |
| `target: ES2020` | Tauri WebView2/WKWebKit support ES2020; no legacy browser compatibility needed |
| `strict: true` | Enforces type safety, catches errors at compile time, reduces runtime bugs |
| `noUnusedLocals`, `noUnusedParameters` | Keeps codebase clean; unused code is often dead code or a mistake |
| `moduleResolution: "bundler"` | Aligns with Vite's bundler semantics; respects `exports` field in package.json |
| Six-lens design | Supports multiple viewing modes: reading view, outline/graph, metadata, schema, search, settings (TASK-27 design) |
| Rich markdown support | KennisBank articles use footnotes, task lists, KaTeX math, syntax highlighting, Mermaid diagrams |
| Graph visualization | Enables exploration of vault graph structure (knowledge interconnections) |
| DOMPurify + strict CSP | Renders user/system content safely without XSS risk |

## Notes

- **Vite Version Lock**: package-lock.json pins exact versions; run `npm ci` (not `npm install`) for reproducible builds
- **TypeScript Strict Mode**: all code must pass strict type checking before build succeeds
- **No Implicit Dependencies**: `lib: []` and empty `types` array mean you must explicitly import types (e.g., `import type { Node } from 'force-graph'`)
- **Development Server**: Vite dev server runs independently of Tauri; the Tauri bridge injects IPC for native calls
- **Hot Reload**: Code changes in `src/` trigger live reload in the WebView during `npm run dev`
- **Six-Lens Tabs**: The `#tabs` and `#lens` containers support switching between different viewing modes; implementation is in `src/`
- **Internationalization**: HTML `lang="nl"` indicates Dutch language; translations/i18n would be in the source code
- **Performance**: Vite's production build includes tree-shaking, code splitting, and minification to reduce bundle size and load time in the desktop app

## Related Documentation

- **src/ directory**: C4 Code documentation for the TypeScript source tree (documented separately)
- **dist/ directory**: Build output (not documented, generated)
- **Tauri Integration**: `atlas/src-tauri/` (Rust backend, separate C4 documentation)
- **Build Instructions**: `atlas/BUILD.md` and `atlas/README.md`
- **CLAUDE.md** (project): Build language policy and best practices
