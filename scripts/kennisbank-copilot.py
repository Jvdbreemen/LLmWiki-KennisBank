#!/usr/bin/env python3
"""KennisBank launcher for the standalone GitHub Copilot CLI (`@github/copilot`).

Design contract: docs/adr/0003-copilot-cli-integration.md, section D4
("Wrapper / launcher: trivial exec, not a proxy").

Headroom's `wrap` is a proxy-interception launcher: it injects routing config,
starts a background compression proxy, reroutes the agent's API traffic, and
needs SIGINT/SIGTERM handlers plus restore-on-exit to tear all that down.
**KennisBank has no proxy and reroutes nothing.** This launcher is therefore a
*trivial exec*: resolve the vault + runtime, set ``KENNISBANK_VAULT`` and the
instruction env, run a fast fail-open light validation, then hand off to the
real ``copilot`` preserving argv and exit code. None of Headroom's
signal-handler / restore machinery is copied.

Why ``subprocess.run`` and not ``os.execvpe``: ``os.execvp`` replaces the
process (great on POSIX, absent on Windows). We need to *set* the child env and
we want one code path that is uniform across macOS/Linux/Windows and, above all,
testable -- ``launch()`` is a module-level seam that tests monkeypatch so the
suite never spawns an interactive Copilot TUI. Exit-code fidelity is preserved
by returning ``proc.returncode``.

Wrapper-consumed flags (everything else is passed through to ``copilot``
verbatim):

  --kb-doctor      JSON probe + config report; exit 0 iff probe status is
                   ok/version_old/not_logged_in. Works without a GitHub login.
  --kb-dry-run     JSON of what it WOULD do (vault, binary, env, argv); no launch.
  --kb-print-env   KEY=VALUE lines the wrapper would inject (secret-masked); no launch.
  --no-capture     inject KENNISBANK_COPILOT_NO_CAPTURE=1 into the child env, then
                   launch copilot normally. The flag itself is consumed.

The --kb- prefix on the diagnostic flags avoids any collision with copilot's own
flags. Stdlib only. LF line endings (ADR-0002).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _copilot  # noqa: E402  (Copilot config layer, ADR-0003)

# Flags the wrapper consumes; anything else is copilot's.
FLAG_DOCTOR = "--kb-doctor"
FLAG_DRY_RUN = "--kb-dry-run"
FLAG_PRINT_ENV = "--kb-print-env"
FLAG_NO_CAPTURE = "--no-capture"

NO_CAPTURE_ENV = "KENNISBANK_COPILOT_NO_CAPTURE"

# Doctor exit is 0 for these probe outcomes: the CLI is present and usable enough
# to diagnose/launch (a missing login is not a wrapper failure). Everything else
# (copilot_missing, platform_binary_missing, mcp_not_listed, mcp_list_failed) is
# a non-zero doctor exit.
_DOCTOR_OK_STATUS = ("ok", "version_old", "not_logged_in")

# Mask any value whose KEY looks credential-bearing. The KennisBank env holds
# none (vault path + local Ollama settings only), but masking is applied
# defensively so this launcher can never surface a secret (DoD#3).
_SECRET_KEY_RE = re.compile(r"(token|secret|key|password|authorization)", re.I)


def _mask(key: str, value: str) -> str:
    return "***" if _SECRET_KEY_RE.search(key) else value


# --- resolution ------------------------------------------------------------

def resolve_vault():
    """The active vault: ``KENNISBANK_VAULT`` if set, else the _copilot default
    (~/KennisBank). Uses _copilot path helpers so Git Bash `/d/...` paths and
    the hermetic HOME/USERPROFILE env resolve exactly as the config layer does."""
    raw = os.environ.get("KENNISBANK_VAULT", "").strip()
    if raw:
        return _copilot._norm_path(raw)
    # Fallback via the shared resolver (ADR-0002: no hardcoded vault default
    # outside _vaultpath). sys.path already has this script's dir (set on import).
    from _vaultpath import vault_root
    return vault_root()


def compute_env_overrides(vault, base_env, no_capture):
    """The (key, value) pairs this launcher injects into the child env, in a
    stable order. ``KENNISBANK_VAULT`` is *pinned* (always overwritten with the
    resolved, posix-normalized path) so a stray/relative value can never point
    Copilot at the wrong vault. The KB_LLM_* vars are set only when the user has
    not already set them (do-not-clobber). NO_CAPTURE is added on --no-capture."""
    overrides = []
    for key, val in _copilot._kb_env(vault).items():
        if key == "KENNISBANK_VAULT":
            overrides.append((key, val))          # pinned
        elif key not in base_env:
            overrides.append((key, val))          # set-if-absent
    if no_capture:
        overrides.append((NO_CAPTURE_ENV, "1"))
    return overrides


def build_child_env(vault, base_env, no_capture):
    """A copy of ``base_env`` with the KennisBank overrides applied."""
    env = dict(base_env)
    for key, val in compute_env_overrides(vault, base_env, no_capture):
        env[key] = val
    return env


def light_validate(vault):
    """Fast, fail-open prerequisite check. Returns human-readable WARNING strings
    (never raises, never blocks): a missing vault dir or missing kb-mcp.py is
    surfaced but must not stop the launch (ADR AC#3 fail-open)."""
    warnings = []
    if not vault.is_dir():
        warnings.append(f"KennisBank vault directory not found: {_copilot._posix(vault)}")
    mcp = vault / ".claude" / "scripts" / "kb-mcp.py"
    if not mcp.is_file():
        warnings.append(f"KennisBank MCP server not found: {_copilot._posix(mcp)}")
    return warnings


def install_hint() -> str:
    """Actionable, secret-free hint when the copilot binary is absent (ADR
    Fallbacks, incl. the Windows/nvm4w missing-platform-binary caveat)."""
    return (
        "copilot binary not found on PATH.\n"
        "  Install:  npm install -g @github/copilot\n"
        "  On Windows/nvm4w, npm may place the JS loader without the platform\n"
        "  binary (copilot --version prints 'no platform package found'); then\n"
        "  also install:  npm install -g @github/copilot-<platform>-<arch>  (same version)\n"
        "  Or set KENNISBANK_COPILOT_BIN to the copilot executable path.\n"
        "  Dry-run/doctor work without the binary: kennisbank-copilot --kb-dry-run"
    )


# --- launch seam (monkeypatched by tests) ----------------------------------

def launch(binary, args, env):
    """Hand off to the real copilot, preserving argv and exit code.

    Stdio is inherited (interactive TUI). subprocess -- not os.execvpe -- for a
    single cross-platform code path and testability; tests replace this function
    to capture (binary, args, env) without spawning anything."""
    proc = subprocess.run([binary, *args], env=env)
    return proc.returncode


# --- modes -----------------------------------------------------------------

def _run_doctor(vault) -> int:
    probe = _copilot.probe_cli(vault)
    errors = _copilot.validate_config(vault)
    status = probe.get("status")
    ok = status in _DOCTOR_OK_STATUS
    out = {
        "vault": _copilot._posix(vault),
        "binary": _copilot.find_binary(),
        "status": status,
        "ok": ok,
        "probe": probe,
        "config": {"ok": not errors, "errors": errors},
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if ok else 1


def _run_dry_run(vault, passthrough, no_capture) -> int:
    binary = _copilot.find_binary()
    overrides = compute_env_overrides(vault, os.environ, no_capture)
    out = {
        "mode": "dry-run",
        "vault": _copilot._posix(vault),
        "vault_exists": vault.is_dir(),
        "binary": binary,
        "binary_found": bool(binary),
        "no_capture": no_capture,
        "env": {k: _mask(k, v) for k, v in overrides},
        "copilot_args": passthrough,
        "copilot_argv": [binary or "copilot", *passthrough],
        "warnings": light_validate(vault),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


def _run_print_env(vault, no_capture) -> int:
    for key, val in compute_env_overrides(vault, os.environ, no_capture):
        print(f"{key}={_mask(key, val)}")
    return 0


def _run_launch(vault, passthrough, no_capture) -> int:
    for warning in light_validate(vault):
        print(f"WARNING: {warning}", file=sys.stderr)
    binary = _copilot.find_binary()
    if not binary:
        print(f"ERROR: {install_hint()}", file=sys.stderr)
        return 127  # conventional "command not found"
    child_env = build_child_env(vault, os.environ, no_capture)
    return launch(binary, passthrough, child_env)


# --- arg split + entrypoint ------------------------------------------------

def split_args(argv):
    """Partition argv into (wrapper flags, copilot passthrough). Wrapper flags
    are consumed wherever they appear; every other token is passed through
    unchanged and in order."""
    flags = {"doctor": False, "dry_run": False, "print_env": False, "no_capture": False}
    passthrough = []
    for arg in argv:
        if arg == FLAG_DOCTOR:
            flags["doctor"] = True
        elif arg == FLAG_DRY_RUN:
            flags["dry_run"] = True
        elif arg == FLAG_PRINT_ENV:
            flags["print_env"] = True
        elif arg == FLAG_NO_CAPTURE:
            flags["no_capture"] = True
        else:
            passthrough.append(arg)
    return flags, passthrough


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    flags, passthrough = split_args(argv)
    vault = resolve_vault()

    # Diagnostic modes work WITHOUT a copilot binary or GitHub login (AC#4).
    if flags["doctor"]:
        return _run_doctor(vault)
    if flags["dry_run"]:
        return _run_dry_run(vault, passthrough, flags["no_capture"])
    if flags["print_env"]:
        return _run_print_env(vault, flags["no_capture"])
    return _run_launch(vault, passthrough, flags["no_capture"])


if __name__ == "__main__":
    sys.exit(main())
