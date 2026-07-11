"""KennisBank config layer for the standalone GitHub Copilot CLI (`@github/copilot`).

Design contract: see docs/adr/0003-copilot-cli-integration.md.

This module is the reusable, hermetically testable helper layer (TASK-26.2) that
`install-agent-envs.py` delegates to for the Copilot agent. It:

- detects the `copilot` binary, its version, and the config home (honoring
  `COPILOT_HOME`), returning a machine-readable dict for setup/doctor;
- mutates Copilot config *idempotently and non-destructively* using two KISS
  mechanisms (ADR D6):
    * structured config (JSON) -> key-scoped read-modify-write + equivalence
      check, no markers needed (mcp-config.json, hooks/kennisbank.json);
    * freeform files -> a marker-delimited managed block, never clobbering user
      content (copilot-instructions.md, the .agent.md profile).
- reports every mutation as added / updated / skipped / created with the backup
  path, and supports a full dry-run.

Stdlib only. No hyphen in the filename so scripts can ``import _copilot`` after a
``sys.path.insert`` (same trick as ``_common.py`` / ``_frontmatter.py``). All
generated config pins ``KENNISBANK_VAULT`` explicitly so a non-default vault
never silently falls back to ~/KennisBank inside Copilot.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# --- markers & constants ---------------------------------------------------

KB_START = "<!-- BEGIN LLmWiki-KennisBank -->"
KB_END = "<!-- END LLmWiki-KennisBank -->"

# Copilot hooks (exit code 2 = deny) were hardened in v1.0.70; target that.
MIN_VERSION = (1, 0, 70)

# Env every KennisBank-generated Copilot config pins so the right vault + local
# LLM backend is used regardless of Copilot's cwd.
def _kb_env(vault: "Path") -> dict:
    return {
        "KENNISBANK_VAULT": _posix(vault),
        "KB_LLM_PROVIDERS": "ollama",
        "KB_LLM_MODEL": "gemma4:12b",
        "KB_LLM_ENDPOINT": "http://localhost:11434",
    }


# --- platform / path helpers (self-contained, stdlib-only) -----------------

def _is_windows_like() -> bool:
    return os.name == "nt" or sys.platform.startswith(("win", "msys", "cygwin"))


def _norm_path(raw) -> Path:
    s = str(raw)
    if os.name == "nt":
        # Git Bash may pass /d/Users/... into native Python.
        m = re.match(r"^/([a-zA-Z])/(.*)$", s)
        if m:
            s = f"{m.group(1).upper()}:/{m.group(2)}"
    return Path(os.path.expanduser(os.path.expandvars(s)))


def _posix(p) -> str:
    return str(p).replace("\\", "/")


def _win(p) -> str:
    return str(p).replace("/", "\\")


def _home() -> Path:
    raw = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    return _norm_path(raw)


def copilot_home() -> Path:
    """The Copilot config home. ``COPILOT_HOME`` overrides ~/.copilot.

    Verified against copilot v1.0.70: mutations under a temporary COPILOT_HOME
    never touch the real home, which is what makes the tests hermetic.
    """
    raw = os.environ.get("COPILOT_HOME", "").strip()
    return _norm_path(raw) if raw else _home() / ".copilot"


def _mcp_server_argv(vault: Path) -> list:
    py = ["py", "-3"] if _is_windows_like() else ["python3"]
    return [*py, _posix(vault / ".claude" / "scripts" / "kb-mcp.py")]


# --- detection -------------------------------------------------------------

def find_binary() -> "str | None":
    """Locate the copilot binary. ``KENNISBANK_COPILOT_BIN`` overrides discovery
    (used by tests with a fake binary and by users with a non-PATH install)."""
    override = os.environ.get("KENNISBANK_COPILOT_BIN", "").strip()
    if override:
        return override if (Path(override).is_file() or shutil.which(override)) else None
    return shutil.which("copilot")


def _version_tuple(text: str) -> "tuple | None":
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(g) for g in m.groups()) if m else None


def binary_version(binary: "str | None" = None, timeout: int = 20) -> "tuple | None":
    """Return the copilot version as a (major, minor, patch) tuple, or None.

    Runs ``copilot --version`` (non-interactive, never launches the TUI). On the
    Windows/nvm4w missing-platform-binary case this prints "no platform package
    found" with no version -> returns None, which the caller reports actionably.
    """
    binary = binary or find_binary()
    if not binary:
        return None
    try:
        proc = subprocess.run(
            [binary, "--version"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    return _version_tuple((proc.stdout or "") + (proc.stderr or ""))


def detect(vault: "Path | None" = None) -> dict:
    """Machine-readable detection snapshot for setup/doctor (JSON-serializable)."""
    binary = find_binary()
    version = binary_version(binary) if binary else None
    home = copilot_home()
    mcp_path = home / "mcp-config.json"
    registered = False
    if mcp_path.is_file():
        data = _read_json(mcp_path)
        registered = isinstance(data.get("mcpServers"), dict) and "kennisbank" in data["mcpServers"]
    return {
        "binary": binary,
        "installed": bool(binary),
        "version": ".".join(str(x) for x in version) if version else None,
        "version_ok": bool(version) and version >= MIN_VERSION,
        "min_version": ".".join(str(x) for x in MIN_VERSION),
        "platform_binary_ok": binary is not None and version is not None,
        "home": _posix(home),
        "home_exists": home.exists(),
        "mcp_config": _posix(mcp_path),
        "kennisbank_registered": registered,
        "hooks_file": _posix(home / "hooks" / "kennisbank.json"),
        "hooks_present": (home / "hooks" / "kennisbank.json").is_file(),
        "instructions_file": _posix(home / "copilot-instructions.md"),
        "agent_profile": _posix(home / "agents" / "kennisbank.agent.md"),
    }


# --- generic idempotent primitives -----------------------------------------

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return ""


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_json(path: Path) -> dict:
    """Fail-open JSON read: {} on missing / unparseable / non-dict (ADR D6)."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict) -> None:
    _write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


BACKUP_SUFFIX = ".kbak"


def _backup(path: Path, dry_run: bool) -> "str | None":
    """Back up an existing file before a destructive-ish write. One rolling
    backup at ``<path>.kbak``. Returns the backup path (str) or None."""
    if not path.is_file():
        return None
    bak = path.with_name(path.name + BACKUP_SUFFIX)
    if not dry_run:
        shutil.copy2(path, bak)
    return _posix(bak)


def restore_backup(path: Path) -> bool:
    """Roll back the last backup, if any. Returns True if restored."""
    bak = path.with_name(path.name + BACKUP_SUFFIX)
    if bak.is_file():
        shutil.copy2(bak, path)
        return True
    return False


def _result(path: Path, action: str, backed_up: "str | None" = None,
            detail: str = "") -> dict:
    return {
        "path": _posix(path),
        "action": action,          # created | updated | skipped
        "changed": action in ("created", "updated"),
        "backed_up": backed_up,
        "detail": detail,
    }


def replace_managed_block(path: Path, block: str, *, dry_run: bool) -> dict:
    """Insert/replace the KennisBank marker block in a freeform file without
    ever clobbering user content outside the markers (ADR D6 / AC#2)."""
    old = _read_text(path)
    pattern = re.compile(re.escape(KB_START) + r".*?" + re.escape(KB_END), re.S)
    existed = path.is_file()
    if pattern.search(old):
        new = pattern.sub(lambda _m: block.strip(), old)
        action = "updated" if new != old else "skipped"
    else:
        sep = "\n\n" if old.strip() else ""
        new = old.rstrip() + sep + block.strip() + "\n"
        action = "updated" if existed else "created"
    if new == old:
        return _result(path, "skipped")
    backed_up = _backup(path, dry_run) if existed else None
    if not dry_run:
        _write_text(path, new)
    return _result(path, action, backed_up)


def merge_json_key(path: Path, top_key: str, name: str, value: dict,
                   *, dry_run: bool) -> dict:
    """Key-scoped read-modify-write of ``data[top_key][name] = value``.

    Preserves every other key. Equivalence check -> skipped when identical, so
    repeated setup runs never rewrite or duplicate (AC#2/#3). Fail-open read.
    """
    data = _read_json(path)
    existed = path.is_file()
    container = data.get(top_key)
    if not isinstance(container, dict):
        container = {}
    current = container.get(name)
    if current == value:
        return _result(path, "skipped")
    action = "updated" if existed else "created"
    backed_up = _backup(path, dry_run) if existed else None
    container[name] = value
    data[top_key] = container
    if not dry_run:
        _write_json(path, data)
    return _result(path, action, backed_up)


def remove_json_key(path: Path, top_key: str, name: str, *, dry_run: bool) -> dict:
    data = _read_json(path)
    container = data.get(top_key)
    if not isinstance(container, dict) or name not in container:
        return _result(path, "skipped")
    backed_up = _backup(path, dry_run)
    del container[name]
    if not dry_run:
        _write_json(path, data)
    return _result(path, "updated", backed_up)


def remove_managed_block(path: Path, *, dry_run: bool) -> dict:
    old = _read_text(path)
    pattern = re.compile(r"\n*" + re.escape(KB_START) + r".*?" + re.escape(KB_END) + r"\n*", re.S)
    if not pattern.search(old):
        return _result(path, "skipped")
    new = pattern.sub("\n", old).lstrip("\n")
    backed_up = _backup(path, dry_run)
    if not dry_run:
        _write_text(path, new)
    return _result(path, "updated", backed_up)


# --- surface writers (built on the primitives) -----------------------------

def _mcp_server_spec(vault: Path) -> dict:
    argv = _mcp_server_argv(vault)
    return {
        "type": "local",
        "command": argv[0],
        "args": argv[1:],
        "env": _kb_env(vault),
        "tools": ["*"],
    }


def ensure_mcp(home: Path, vault: Path, *, dry_run: bool = False) -> dict:
    """Register the KennisBank stdio MCP server in ~/.copilot/mcp-config.json
    (schema verified against copilot v1.0.70). Idempotent, login-free (ADR D1)."""
    return merge_json_key(home / "mcp-config.json", "mcpServers", "kennisbank",
                          _mcp_server_spec(vault), dry_run=dry_run)


# Capture script (built by TASK-26.6); the hook map references it here so the
# registration is one place. Fail-open is the script's responsibility.
_CAPTURE_SCRIPT = "kb-copilot-capture.py"


def _desired_hooks(vault: Path) -> dict:
    """Copilot hook map (camelCase events). Lifecycle maintenance mirrors the
    Codex hookset; capture entries feed rawlog/activity (TASK-26.6/26.8). Every
    KennisBank hook is fail-open: the scripts always exit 0."""
    cap = _CAPTURE_SCRIPT
    return {
        "sessionStart": [
            ("import-copilot.py", None, 60),
            ("build-embed-index.py", None, 180),
            ("build-kb-index.py", None, 180),
            ("build-activity-index.py", None, 180),
            ("sweep-launch.py", None, 30),
            ("memory-notify.py", None, 30),
            ("distill-notify.py", None, 30),
            (cap, "--event sessionStart", 30),
        ],
        "userPromptSubmitted": [(cap, "--event userPromptSubmitted", 30)],
        "preToolUse": [(cap, "--event preToolUse", 30)],
        "postToolUse": [(cap, "--event postToolUse", 30)],
        "sessionEnd": [
            (cap, "--event sessionEnd", 30),
            ("kb-usage-scan.py", None, 30),
        ],
    }


def _hook_command(vault: Path, script: str, arg: "str | None", shell: str) -> str:
    if shell == "powershell":
        base = f'py -3 "{_win(vault / ".claude" / "scripts" / script)}"'
    else:
        base = f'python3 "{_posix(vault / ".claude" / "scripts" / script)}"'
    cmd = f"{base} {arg}" if arg else base
    # Fail-open guard (ADR D3): a KennisBank hook must NEVER block Copilot. Force
    # exit 0 at the shell level so a missing/erroring script can never make a
    # preToolUse hook return the deny exit code (2). KennisBank observes; it
    # never denies a tool call.
    return f"{cmd}; exit 0"


def _hook_entry(vault: Path, script: str, arg: "str | None", timeout: int) -> dict:
    return {
        "type": "command",
        "bash": _hook_command(vault, script, arg, "bash"),
        "powershell": _hook_command(vault, script, arg, "powershell"),
        "cwd": ".",
        "timeoutSec": timeout,
        "env": _kb_env(vault),
    }


def _hook_matches(entry: dict, script: str, arg: "str | None") -> bool:
    if not isinstance(entry, dict):
        return False
    blob = str(entry.get("bash", "")) + "\n" + str(entry.get("powershell", ""))
    if script not in blob:
        return False
    # Capture entries share a script but differ by --event; match the arg too.
    return arg in blob if arg else True


def ensure_hooks(home: Path, vault: Path, *, dry_run: bool = False) -> dict:
    """Register the KennisBank hook set in ~/.copilot/hooks/kennisbank.json.

    Upsert-by-(script,arg): re-runs never duplicate and unrelated user entries
    survive. Cross-platform via bash+powershell keys (ADR D3). Schema:
    {"version":1,"hooks":{<event>:[<entry>...]}}.
    """
    path = home / "hooks" / "kennisbank.json"
    data = _read_json(path)
    existed = path.is_file()
    if not isinstance(data.get("version"), int):
        data["version"] = 1
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
    changed = not existed or data.get("version") != 1

    for event, specs in _desired_hooks(vault).items():
        groups = hooks.get(event)
        if not isinstance(groups, list):
            groups = []
        for script, arg, timeout in specs:
            entry = _hook_entry(vault, script, arg, timeout)
            found = False
            for i, existing in enumerate(groups):
                if _hook_matches(existing, script, arg):
                    if existing != entry:
                        groups[i] = entry
                        changed = True
                    found = True
                    break
            if not found:
                groups.append(entry)
                changed = True
        hooks[event] = groups

    data["version"] = 1
    data["hooks"] = hooks
    if not changed:
        return _result(path, "skipped")
    backed_up = _backup(path, dry_run) if existed else None
    if not dry_run:
        _write_json(path, data)
    return _result(path, "updated" if existed else "created", backed_up)


def _instructions_block(vault: Path) -> str:
    vault_s = _posix(vault)
    return f"""{KB_START}
# LLmWiki-KennisBank

This machine uses a non-default KennisBank vault:

`{vault_s}`

Operational rules for GitHub Copilot CLI:
- Always set or preserve `KENNISBANK_VAULT={vault_s}` for KennisBank scripts, hooks and the MCP server.
- Do not use `~/KennisBank` as the active vault on this machine unless the user explicitly changes it.
- Prefer the local KennisBank MCP server (`recall`, `capture`) before external search when a task may depend on prior local knowledge. For temporal questions use `what_did_i_do`, `timeline`, `weeklog` or `topic_timeline` first.
- KennisBank hooks are fail-open: a missing Ollama, missing embeddings or a script error may skip context capture, but must never block Copilot.

Client: Copilot
{KB_END}
"""


def ensure_instructions(home: Path, vault: Path, *, dry_run: bool = False) -> dict:
    """Write the KennisBank managed block into the global personal instructions
    file ~/.copilot/copilot-instructions.md (ADR D2). Marker-scoped."""
    return replace_managed_block(home / "copilot-instructions.md",
                                 _instructions_block(vault), dry_run=dry_run)


def _agent_profile_text(vault: Path) -> str:
    vault_s = _posix(vault)
    return f"""{KB_START}
# KennisBank

KennisBank-aware custom agent for GitHub Copilot CLI. Select with
`copilot --agent kennisbank`.

Vault: `{vault_s}` (always pinned via `KENNISBANK_VAULT`).

Use the local KennisBank MCP server before external search:
- `recall(query, k)` for wiki/memory retrieval.
- `capture(title, body, memory_type, importance)` for unverified memory.
- `what_did_i_do`, `timeline`, `weeklog`, `topic_timeline` for temporal recall.

Your Copilot session and tool events are captured locally (rawlog -> activity
index) so you can recall "what did I do" later; this capture is fail-open.

Prefer local knowledge and the local Ollama backend. KennisBank hooks and
capture never block a Copilot turn (always fail-open).
{KB_END}
"""


def ensure_agent_profile(home: Path, vault: Path, *, dry_run: bool = False) -> dict:
    """Write ~/.copilot/agents/kennisbank.agent.md (note: the .agent.md
    extension is required; a plain .md is ignored). Managed via marker: an
    existing user file without our marker is left untouched (skipped)."""
    path = home / "agents" / "kennisbank.agent.md"
    if path.is_file():
        text = _read_text(path)
        if KB_START not in text:
            return _result(path, "skipped", detail="unmanaged user file left intact")
    return replace_managed_block(path, _agent_profile_text(vault), dry_run=dry_run)


# --- orchestration ---------------------------------------------------------

def install(vault: Path, *, home: "Path | None" = None, dry_run: bool = False) -> dict:
    """Install all four Copilot surfaces idempotently. Returns a JSON report."""
    home = home or copilot_home()
    vault = _norm_path(vault)
    results = {
        "mcp": ensure_mcp(home, vault, dry_run=dry_run),
        "hooks": ensure_hooks(home, vault, dry_run=dry_run),
        "instructions": ensure_instructions(home, vault, dry_run=dry_run),
        "agent_profile": ensure_agent_profile(home, vault, dry_run=dry_run),
    }
    return {
        "home": _posix(home),
        "vault": _posix(vault),
        "dry_run": dry_run,
        "results": results,
        "changed": any(r.get("changed") for r in results.values()),
    }


def remove(vault: Path, *, home: "Path | None" = None, dry_run: bool = False) -> dict:
    """Reverse the install (rollback). Removes only KennisBank-managed keys and
    marker blocks; unmanaged user content is preserved."""
    home = home or copilot_home()
    vault = _norm_path(vault)
    results = {
        "mcp": remove_json_key(home / "mcp-config.json", "mcpServers", "kennisbank", dry_run=dry_run),
        "hooks": _remove_hooks(home, vault, dry_run=dry_run),
        "instructions": remove_managed_block(home / "copilot-instructions.md", dry_run=dry_run),
        "agent_profile": remove_managed_block(home / "agents" / "kennisbank.agent.md", dry_run=dry_run),
    }
    return {"home": _posix(home), "dry_run": dry_run, "results": results}


def _remove_hooks(home: Path, vault: Path, *, dry_run: bool) -> dict:
    """Remove only KennisBank hook entries; keep any unrelated user entries."""
    path = home / "hooks" / "kennisbank.json"
    if not path.is_file():
        return _result(path, "skipped")
    data = _read_json(path)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return _result(path, "skipped")
    desired = _desired_hooks(vault)
    changed = False
    for event, specs in desired.items():
        groups = hooks.get(event)
        if not isinstance(groups, list):
            continue
        keep = [g for g in groups if not any(_hook_matches(g, s, a) for s, a, _t in specs)]
        if len(keep) != len(groups):
            changed = True
        if keep:
            hooks[event] = keep
        else:
            hooks.pop(event, None)
    if not changed:
        return _result(path, "skipped")
    backed_up = _backup(path, dry_run)
    if not dry_run:
        if hooks:
            data["hooks"] = hooks
            _write_json(path, data)
        else:
            # Nothing of ours or theirs left: remove our managed file entirely.
            path.unlink()
    return _result(path, "updated", backed_up)


# --- validation (TASK-26.5) ------------------------------------------------

def validate_config(vault: Path, *, home: "Path | None" = None) -> list:
    """Hard errors on the KennisBank Copilot config writes (login-free).

    Checks the four managed surfaces exist and the MCP server points at the
    active vault via KENNISBANK_VAULT (never a wrong default path, AC#4)."""
    home = home or copilot_home()
    vault = _norm_path(vault)
    errors = []
    mcp = _read_json(home / "mcp-config.json")
    servers = mcp.get("mcpServers") if isinstance(mcp.get("mcpServers"), dict) else {}
    srv = servers.get("kennisbank")
    if not isinstance(srv, dict):
        errors.append(f"Copilot mcp-config.json missing mcpServers.kennisbank: {_posix(home / 'mcp-config.json')}")
    else:
        env = srv.get("env") if isinstance(srv.get("env"), dict) else {}
        if env.get("KENNISBANK_VAULT") != _posix(vault):
            errors.append("Copilot MCP kennisbank KENNISBANK_VAULT does not match the active vault")
        if "kb-mcp.py" not in " ".join(str(a) for a in (srv.get("args") or [])):
            errors.append("Copilot MCP kennisbank args do not point at kb-mcp.py")
    for label, p in (
        ("hooks", home / "hooks" / "kennisbank.json"),
        ("instructions", home / "copilot-instructions.md"),
        ("agent profile", home / "agents" / "kennisbank.agent.md"),
    ):
        if not p.is_file():
            errors.append(f"Copilot {label} missing: {_posix(p)}")
    return errors


def probe_cli(vault: Path, *, home: "Path | None" = None, timeout: int = 25) -> dict:
    """Login-free probe of the real copilot CLI for doctor (TASK-26.5/26.9).

    Distinguishes copilot_missing / platform_binary_missing / not_logged_in /
    mcp_not_listed / version_old / ok, with machine-readable JSON."""
    home = home or copilot_home()
    binary = find_binary()
    out = {"installed": bool(binary), "binary": binary, "version": None,
           "version_ok": False, "mcp_listed": None, "status": "", "detail": "",
           "min_version": ".".join(str(x) for x in MIN_VERSION)}
    if not binary:
        out["status"] = "copilot_missing"
        out["detail"] = "copilot not installed (optional; run: npm install -g @github/copilot)"
        return out
    ver = binary_version(binary, timeout=timeout)
    out["version"] = ".".join(str(x) for x in ver) if ver else None
    if ver is None:
        out["status"] = "platform_binary_missing"
        out["detail"] = ("copilot present but no platform binary; run: "
                         "npm install -g @github/copilot-<platform>-<arch> at the same version")
        return out
    out["version_ok"] = ver >= MIN_VERSION
    env = dict(os.environ)
    env["COPILOT_HOME"] = str(home)
    try:
        proc = subprocess.run(
            [binary, "mcp", "list"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, env=env,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        out["status"] = "mcp_list_failed"
        out["detail"] = f"copilot mcp list failed: {e}"
        return out
    blob = ((proc.stdout or "") + "\n" + (proc.stderr or "")).lower()
    if "kennisbank" in blob:
        out["mcp_listed"] = True
        out["status"] = "ok" if out["version_ok"] else "version_old"
        if not out["version_ok"]:
            out["detail"] = f"copilot {out['version']} < {out['min_version']}; hooks exit-2-deny needs {out['min_version']}+"
    else:
        out["mcp_listed"] = False
        if any(k in blob for k in ("log in", "login", "not authenticated", "sign in", "/login")):
            out["status"] = "not_logged_in"
            out["detail"] = "kennisbank not shown; copilot may need /login"
        else:
            out["status"] = "mcp_not_listed"
            out["detail"] = "kennisbank not in copilot mcp list; run setup to register it"
    return out


# --- CLI -------------------------------------------------------------------

def _main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="KennisBank Copilot config helper")
    ap.add_argument("command", choices=["detect", "install", "remove", "probe", "validate"])
    ap.add_argument("--vault")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.command == "detect":
        out = detect(_norm_path(args.vault) if args.vault else None)
    elif args.command == "probe":
        # Vault fallback via the shared resolver (ADR-0002: no hardcoded vault
        # default outside _vaultpath). Lazy import: only reached as a CLI, where
        # this script's dir is already on sys.path.
        from _vaultpath import vault_root
        out = probe_cli(_norm_path(args.vault) if args.vault else vault_root())
    elif args.command == "validate":
        if not args.vault:
            ap.error("--vault is required for validate")
        errors = validate_config(_norm_path(args.vault))
        out = {"ok": not errors, "errors": errors}
    else:
        if not args.vault:
            ap.error("--vault is required for install/remove")
        vault = _norm_path(args.vault)
        fn = install if args.command == "install" else remove
        out = fn(vault, dry_run=args.dry_run)

    # Output is always machine-readable JSON (AC#3 / DoD#3); --json is accepted
    # for symmetry with the other KennisBank helpers.
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
