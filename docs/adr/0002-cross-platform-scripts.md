# ADR-0002: Scripts and tests target macOS, Linux, and Windows

- **Status**: Accepted
- **Date**: 2026-06-20
- **Deciders**: Jvdbreemen, Robert van den Breemen

## Context

LLmWiki-KennisBank ships two kinds of executable code: Python utility scripts
(`scripts/*.py`) and shell tooling (`setup.sh`, `scripts/doctor.sh`). These run
on contributors' development machines and in CI. The maintainer develops on
Windows (Git Bash); other contributors and the documentation assume macOS and
Linux; GitHub Actions CI runs on `ubuntu-latest`.

Platform drift has already produced concrete failures:

- A deploy test passed a Windows-style path (`C:\Users\...\Temp`) as `HOME` to a
  `bash` subprocess. Git Bash mangled the backslashes and the install landed in
  an unexpected location, so the test failed on Windows while passing in CI.
- A fix attempt hard-coded `C:\Program Files\Git\bin\bash.exe`, which misses
  per-user Git installs (`%LOCALAPPDATA%\Programs\Git`), Scoop, and
  Chocolatey layouts, and whose PATH fallback silently selects the WSL/Store
  `bash` stub in `System32` — a different filesystem namespace.

Without an explicit, shared rule, "works on my machine" keeps shipping
platform-specific breakage that only one of the three environments catches.

## Decision

**Every script and test in this project must work on macOS, Linux, and Windows
(Git Bash), and the test suite must pass on all three.**

Concrete, enforceable rules:

- Never pass a Windows-style path (`C:\...`) to a `bash` subprocess. Convert to
  Git Bash POSIX form (`/c/...`) first.
- Resolve the vault through the `KENNISBANK_VAULT` environment variable
  (fallback `$HOME/KennisBank`) everywhere, including `setup.sh` — never
  hard-code `~/KennisBank`.
- Shell scripts use LF line endings (CRLF breaks `bash` on macOS/Linux).
- Do not hard-code absolute platform paths to tools. Discover them via
  environment variables, `PATH` (`shutil.which`), or, on Windows, the
  `GitForWindows` registry key — and reject the `System32` WSL stub.
- When a required tool genuinely cannot be located on a platform, skip the test
  with a clear reason rather than failing with a misleading error.
- CI keeps running `python3 -m py_compile scripts/*.py`,
  `bash -n setup.sh scripts/doctor.sh`, and `python3 -m unittest discover -s
  tests` on `ubuntu-latest`; Windows and macOS behaviour is verified by writing
  tests that are themselves platform-aware.

## Consequences

**Positive**

- The maintainer's Windows workflow and contributors' macOS/Linux workflows are
  first-class; breakage is caught by a test rather than by a confused user.
- The portability rules are written down once and apply to every future script
  and test, instead of being rediscovered per incident.

**Negative / trade-offs**

- Tests that shell out need platform-aware helpers (path conversion, bash
  discovery), which is more code than a naive `["bash", ...]` call.
- CI runs only on Linux, so Windows/macOS regressions are caught by
  platform-aware test logic and contributor machines, not by a CI matrix. A
  multi-OS CI matrix is a possible future enhancement but is out of scope here.

## References

- `tests/test_setup_deploy.py` — `_bash_path()` POSIX conversion and the
  Windows bash-discovery helper.
- `setup.sh` — `VAULT="${KENNISBANK_VAULT:-$HOME/KennisBank}"`.
- `.github/workflows/ci.yml` — the three CI checks.
- ADR-0001 — prior decision establishing `OLLAMA_EMBED_MODEL` as the
  override-everything pattern this ADR extends to paths and tools.
