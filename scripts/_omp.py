#!/usr/bin/env python3
"""OMP (oh-my-pi) config layer for KennisBank (stdlib-only).

OMP already loads the shared ``~/.agents/skills`` set, so the installer only has
to add two things, both under the OMP agent directory (``~/.omp/agent``, or
``PI_CODING_AGENT_DIR`` when set):

- ``mcp.json``: a key-scoped ``mcpServers.kennisbank`` entry. Every other server
  and key is preserved; an identical entry is left untouched.
- ``rules/kennisbank.md``: the KennisBank instructions as an always-apply rule.
  Deliberately not ``AGENTS.md``: OMP keeps a single user-level context file and
  ``~/.omp/agent/AGENTS.md`` outranks every other one, so writing it would
  silently hide the user's ``~/.claude/CLAUDE.md`` or ``~/.codex/AGENTS.md``.
  A rule loads beside whatever context file wins.

No lifecycle hooks are installed: OMP runs only TypeScript/JavaScript extensions.
Session work is explicit through ``/skill:sessiestart`` and ``/skill:sessielog``,
and retrieval is an MCP pull, as for Copilot.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _copilot  # noqa: E402  (shared config primitives and the KennisBank MCP env)

RULE_NAME = "kennisbank.md"


def omp_agent_dir() -> Path:
    """The OMP user agent directory. ``PI_CODING_AGENT_DIR`` overrides ~/.omp/agent."""
    raw = os.environ.get("PI_CODING_AGENT_DIR", "").strip()
    return _copilot._norm_path(raw) if raw else _copilot._home() / ".omp" / "agent"


def _mcp_server_spec(vault: Path, python_argv=None) -> dict:
    argv = _copilot._mcp_server_argv(vault, python_argv=python_argv)
    return {
        "type": "stdio",
        "command": argv[0],
        "args": argv[1:],
        "env": _copilot._kb_env(vault),
    }


def ensure_mcp(home: Path, vault: Path, *, dry_run: bool = False, python_argv=None) -> dict:
    return _copilot.merge_json_key(
        home / "mcp.json", "mcpServers", "kennisbank",
        _mcp_server_spec(vault, python_argv=python_argv), dry_run=dry_run,
    )


def _rule_text(vault: Path) -> str:
    vault_s = _copilot._posix(vault)
    return f"""---
description: LLmWiki-KennisBank vault, local MCP recall and session workflows on this machine
alwaysApply: true
---

# LLmWiki-KennisBank

This machine uses the KennisBank vault `{vault_s}`.

- Always set or preserve `KENNISBANK_VAULT={vault_s}` for KennisBank scripts, skills and the MCP server. Do not use `~/KennisBank` unless the user changes the vault.
- Prefer the `kennisbank` MCP server before external search when a task may depend on prior local knowledge. For temporal questions use `what_did_i_do`, `timeline`, `weeklog` or `topic_timeline`. For an explicit question about what worked before, use `experience_recall` first and `source_recall` only on demand for evidence; neither is an automatic advisory.
- KennisBank MCP tools return compact summaries. Use short queries and summarize results instead of reproducing tool output.
- KennisBank workflows are skills: `/skill:sessiestart` for startup maintenance, `/skill:sessielog` for session capture, and `/skill:<name>` for the others. No lifecycle hooks run in OMP.
"""


def ensure_rule(home: Path, vault: Path, *, dry_run: bool = False) -> dict:
    """Write the KennisBank-owned rule file; skipped when already identical."""
    path = home / "rules" / RULE_NAME
    text = _rule_text(vault)
    old = _copilot._read_text(path)
    if old == text:
        return _copilot._result(path, "skipped")
    existed = path.is_file()
    backed_up = _copilot._backup(path, dry_run) if existed else None
    if not dry_run:
        _copilot._write_text(path, text)
    return _copilot._result(path, "updated" if existed else "created", backed_up)


def install(vault: Path, *, home: "Path | None" = None, dry_run: bool = False,
            python_argv=None) -> dict:
    home = home or omp_agent_dir()
    vault = _copilot._norm_path(vault)
    results = {
        "mcp": ensure_mcp(home, vault, dry_run=dry_run, python_argv=python_argv),
        "rule": ensure_rule(home, vault, dry_run=dry_run),
    }
    return {
        "home": _copilot._posix(home),
        "vault": _copilot._posix(vault),
        "dry_run": dry_run,
        "results": results,
        "changed": any(r.get("changed") for r in results.values()),
    }


def validate_config(vault: Path, *, home: "Path | None" = None) -> list:
    """Hard errors on the KennisBank OMP config: MCP entry and rule, both on the active vault."""
    home = home or omp_agent_dir()
    vault = _copilot._norm_path(vault)
    errors = []
    mcp_path = home / "mcp.json"
    servers = _copilot._read_json(mcp_path).get("mcpServers")
    srv = servers.get("kennisbank") if isinstance(servers, dict) else None
    if not isinstance(srv, dict):
        errors.append(f"OMP mcp.json missing mcpServers.kennisbank: {_copilot._posix(mcp_path)}")
    else:
        env = srv.get("env") if isinstance(srv.get("env"), dict) else {}
        if env.get("KENNISBANK_VAULT") != _copilot._posix(vault):
            errors.append("OMP MCP kennisbank KENNISBANK_VAULT does not match the active vault")
        if "kb-mcp.py" not in " ".join(str(a) for a in (srv.get("args") or [])):
            errors.append("OMP MCP kennisbank args do not point at kb-mcp.py")
    rule = home / "rules" / RULE_NAME
    if not rule.is_file():
        errors.append(f"OMP rule missing: {_copilot._posix(rule)}")
    elif _copilot._posix(vault) not in _copilot._read_text(rule):
        errors.append(f"OMP rule does not name the active vault: {_copilot._posix(rule)}")
    return errors


def _main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="KennisBank OMP config helper")
    ap.add_argument("command", choices=["validate"])
    ap.add_argument("--vault", required=True)
    args = ap.parse_args(argv)
    errors = validate_config(_copilot._norm_path(args.vault))
    print(json.dumps({"ok": not errors, "errors": errors}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
