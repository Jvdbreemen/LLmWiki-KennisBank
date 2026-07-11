#!/usr/bin/env python3
"""Compact multi-agent KennisBank status for the setup/upgrade summary (TASK-26.13).

The "dashboard" the user sees: after setup installs/repairs the selected agent
environments, this renders a per-agent one-line status (configured? MCP
registered? for Copilot: installed + version) plus a small rollup. It reuses the
existing on-disk config as the source of truth and _copilot for Copilot
detection; it introduces no new runtime surface (AC#4). Terminal-only, JSON mode
for machine consumption.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _copilot  # noqa: E402

AGENTS = ("claude", "codex", "opencode", "copilot")


def _home() -> Path:
    return _copilot._home()


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return ""


def _status_claude() -> dict:
    settings = _home() / ".claude" / "settings.json"
    txt = _read(settings)
    configured = "kb-retrieve.py" in txt and "KENNISBANK_VAULT" in txt
    return {"agent": "claude", "configured": configured, "mcp": False,
            "detail": "hooks + vault env" if configured else "no KennisBank hooks in settings.json"}


def _status_codex() -> dict:
    cfg = _copilot._norm_path(os.environ.get("CODEX_HOME", _home() / ".codex")) / "config.toml"
    txt = _read(cfg)
    mcp = "[mcp_servers.kennisbank]" in txt
    return {"agent": "codex", "configured": mcp, "mcp": mcp,
            "detail": "MCP kennisbank" if mcp else "not configured"}


def _status_opencode() -> dict:
    cfg = _copilot._norm_path(
        os.environ.get("OPENCODE_CONFIG_DIR", _home() / ".config" / "opencode")) / "opencode.json"
    txt = _read(cfg)
    mcp = '"kennisbank"' in txt and '"mcp"' in txt
    return {"agent": "opencode", "configured": mcp, "mcp": mcp,
            "detail": "MCP kennisbank" if mcp else "not configured"}


def _status_copilot() -> dict:
    d = _copilot.detect()
    configured = bool(d.get("kennisbank_registered"))
    installed = bool(d.get("installed"))
    if configured and installed:
        detail = f"installed v{d.get('version')}, MCP registered"
    elif configured and not installed:
        detail = "MCP registered, but copilot not installed (npm install -g @github/copilot)"
    elif installed and not configured:
        detail = f"installed v{d.get('version')}, not registered (run setup.sh --agents copilot)"
    else:
        detail = "skipped - not installed (npm install -g @github/copilot)"
    return {"agent": "copilot", "configured": configured, "installed": installed,
            "mcp": configured, "detail": detail}


_DISPATCH = {
    "claude": _status_claude, "codex": _status_codex,
    "opencode": _status_opencode, "copilot": _status_copilot,
}


def collect(agents: list) -> dict:
    rows = [_DISPATCH[a]() for a in agents if a in _DISPATCH]
    return {
        "agents": rows,
        "configured": sum(1 for r in rows if r["configured"]),
        "total": len(rows),
        "mcp_agents": [r["agent"] for r in rows if r.get("mcp")],
    }


def render(report: dict) -> str:
    # ASCII marks only: the Windows console (cp1252) cannot encode ✓/– (ADR-0002).
    lines = ["KennisBank multi-agent status:"]
    for r in report["agents"]:
        if r["configured"]:
            mark = "ok"
        elif r["agent"] == "copilot" and r.get("installed"):
            mark = "!!"  # installed but not registered -> actionable
        else:
            mark = "--"
        lines.append(f"  [{mark}] {r['agent']:<9} {r['detail']}")
    mcp = ", ".join(report["mcp_agents"]) or "none"
    lines.append(f"summary: {report['configured']}/{report['total']} configured; MCP registered: {mcp}")
    return "\n".join(lines)


def _parse_agents(raw: str | None) -> list:
    if not raw:
        return list(AGENTS)
    vals = [v.strip().lower() for v in raw.replace(";", ",").split(",") if v.strip()]
    if "all" in vals:
        return list(AGENTS)
    return [v for v in vals if v in AGENTS]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="KennisBank multi-agent status summary")
    ap.add_argument("--agents", default="all")
    ap.add_argument("--vault")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    report = collect(_parse_agents(args.agents))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
