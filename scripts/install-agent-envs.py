#!/usr/bin/env python3
"""Install and validate KennisBank integrations for local agent clients.

This helper is intentionally stdlib-only. setup.sh owns the vault scaffold and
Claude Code deploy; this script owns the cross-agent layer:

- Codex: skills, prompt aliases, AGENTS.md, hooks.json, MCP config.
- OpenCode: skills, commands, AGENTS.md, plugin hook, MCP config.
- Claude Code validation: verifies the files setup.sh installed.

All generated client config pins KENNISBANK_VAULT explicitly. That prevents a
non-default vault from silently falling back to ~/KennisBank in another agent.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 support.
    tomllib = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _copilot  # noqa: E402  (Copilot config layer, ADR-0003)


AGENTS = ("claude", "codex", "opencode", "copilot")
KB_START = "<!-- BEGIN LLmWiki-KennisBank -->"
KB_END = "<!-- END LLmWiki-KennisBank -->"

ROOT_COMMANDS = {
    "sessielog": "Maak of werk een KennisBank sessielog bij.",
    "wiki": "Compileer raw sessies naar wiki-artikelen.",
    "intake": "Verwerk bestanden uit de KennisBank inbox.",
    "stale": "Controleer stale wiki-artikelen.",
    "sessiestart": "Laad KennisBank sessiestart-context.",
    "import": "Importeer bestaande sessies of exports naar de KennisBank.",
    "reconcile": "Reconcile tegenstrijdige wiki-informatie.",
    "uitdaag": "Daag een idee uit met KennisBank-context.",
    "brug": "Zoek bruggen tussen KennisBank-onderwerpen.",
    "weeklog": "Maak een temporal activity weeklog met source refs.",
    "timeline": "Maak een chronologische activity timeline.",
    "watdeedik": "Beantwoord wat je deed op een datum of in een periode.",
    "destilleer": "Destilleer ruwe sessies naar bruikbare kennis.",
    "kennisbank-upgrade": "Upgrade de KennisBank tooling naar de nieuwste release.",
    "kennisbank-contribute": "Breng lokale KennisBank-toolingverbeteringen upstream.",
}

NESTED_COMMAND_ALIASES = {
    "kennisbank/settings": "kennisbank-settings",
    "kennisbank/rebuild-index": "kennisbank-rebuild-index",
    "kennisbank/rebuild-memory": "kennisbank-rebuild-memory",
}

MODEL_CHECK_TEXT = "KennisBank model smoke test. Antwoord exact met OK."
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "openai/gpt-5.2"


def _norm_path(raw: str | Path) -> Path:
    s = str(raw)
    if os.name == "nt":
        # Git Bash may pass /d/Users/... into native Python.
        m = re.match(r"^/([a-zA-Z])/(.*)$", s)
        if m:
            s = f"{m.group(1).upper()}:/{m.group(2)}"
    return Path(os.path.expanduser(os.path.expandvars(s)))


def _posix(p: Path) -> str:
    return str(p).replace("\\", "/")


def _is_windows_like() -> bool:
    return os.name == "nt" or sys.platform.startswith(("win", "msys", "cygwin"))


def _agent_python_argv() -> list[str]:
    return ["py", "-3"] if _is_windows_like() else ["python3"]


def _mcp_server_argv(vault: Path) -> list[str]:
    return [*_agent_python_argv(), _posix(vault / ".claude" / "scripts" / "kb-mcp.py")]


def _shell_join(argv: list[str]) -> str:
    parts = []
    for arg in argv:
        s = str(arg)
        if _is_windows_like():
            if re.search(r'[\s"]', s):
                parts.append('"' + s.replace('"', '\\"') + '"')
            else:
                parts.append(s)
        else:
            parts.append(shlex.quote(s))
    return " ".join(parts)


def _home() -> Path:
    raw = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    return _norm_path(raw)


def _codex_home() -> Path:
    return _norm_path(os.environ.get("CODEX_HOME", _home() / ".codex"))


def _opencode_home() -> Path:
    return _norm_path(os.environ.get("OPENCODE_CONFIG_DIR", _home() / ".config" / "opencode"))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _copytree(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _replace_block(path: Path, block: str) -> bool:
    old = _read_text(path)
    pattern = re.compile(re.escape(KB_START) + r".*?" + re.escape(KB_END), re.S)
    if pattern.search(old):
        new = pattern.sub(lambda _m: block.strip(), old)
    else:
        sep = "\n\n" if old.strip() else ""
        new = old.rstrip() + sep + block.strip() + "\n"
    if new != old:
        _write_text(path, new)
        return True
    return False


def _agent_block(client: str, vault: Path) -> str:
    vault_s = _posix(vault)
    return f"""{KB_START}
# LLmWiki-KennisBank

This machine uses a non-default KennisBank vault:

`{vault_s}`

Operational rules:
- Always set or preserve `KENNISBANK_VAULT={vault_s}` for KennisBank scripts, hooks, MCP servers, skills, and commands.
- Do not use `C:\\Users\\rvdbr\\KennisBank` or `~/KennisBank` as the active vault on this machine unless the user explicitly changes the vault.
- Prefer the local KennisBank MCP server before external search when the task may depend on prior local knowledge.
- The local LLM backend is Ollama with `gemma4:12b`; embeddings use `qwen3-embedding:8b` unless the vault config says otherwise.
- KennisBank hooks must fail open: missing Ollama, missing embeddings, or a script error may skip context injection, but must not block the agent.

Client: {client}
{KB_END}
"""


def _command_sources(repo: Path) -> list[tuple[str, Path, str]]:
    out: list[tuple[str, Path, str]] = []
    for stem, description in ROOT_COMMANDS.items():
        p = repo / "commands" / f"{stem}.md"
        if p.is_file():
            out.append((stem, p, description))
    for rel, alias in NESTED_COMMAND_ALIASES.items():
        p = repo / "commands" / f"{rel}.md"
        if p.is_file():
            out.append((alias, p, f"KennisBank command alias voor {rel}."))
    return out


def _prompt_text(name: str, source: Path, description: str, target_agent: str) -> str:
    body = source.read_text(encoding="utf-8")
    return (
        "---\n"
        f"description: {description}\n"
        "argument-hint: [ARGUMENTS]\n"
        "---\n\n"
        f"Je voert de KennisBank-workflow `{name}` uit voor {target_agent}.\n"
        "Gebruik de actieve KENNISBANK_VAULT uit de agentconfig; val niet terug op "
        "`~/KennisBank` als die env-var bestaat.\n\n"
        f"{body.rstrip()}\n"
    )


def _install_shared_skills(repo: Path, skills_root: Path) -> list[Path]:
    installed = []
    src_root = repo / "skills"
    if not src_root.is_dir():
        return installed
    for sdir in sorted(src_root.iterdir()):
        if not (sdir / "SKILL.md").is_file():
            continue
        dst = skills_root / sdir.name
        _copytree(sdir, dst)
        installed.append(dst / "SKILL.md")
    return installed


def install_codex(repo: Path, vault: Path) -> dict:
    codex = _codex_home()
    shared_skills = _home() / ".agents" / "skills"
    prompts = codex / "prompts"

    skills = _install_shared_skills(repo, shared_skills)
    written_prompts = []
    for name, source, desc in _command_sources(repo):
        dst = prompts / f"{name}.md"
        _write_text(dst, _prompt_text(name, source, desc, "Codex"))
        written_prompts.append(dst)

    _replace_block(codex / "AGENTS.md", _agent_block("Codex", vault))
    _ensure_codex_hooks(codex / "hooks.json", vault)
    _ensure_codex_mcp(codex / "config.toml", vault)
    return {
        "skills": [str(p) for p in skills],
        "prompts": [str(p) for p in written_prompts],
        "agents_md": str(codex / "AGENTS.md"),
        "hooks": str(codex / "hooks.json"),
        "mcp": str(codex / "config.toml"),
    }


def _codex_command(script: str, vault: Path) -> str:
    return _shell_join([*_agent_python_argv(), _posix(vault / ".claude" / "scripts" / script)])


def _hook_group(script: str, vault: Path, matcher: str | None = None, timeout: int = 60) -> dict:
    group: dict = {
        "hooks": [{
            "type": "command",
            "command": _codex_command(script, vault),
            "timeout": timeout,
            "statusMessage": f"KennisBank: {script}",
        }]
    }
    if matcher:
        group["matcher"] = matcher
    return group


def _ensure_codex_hooks(path: Path, vault: Path) -> None:
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError(f"{path} must contain a JSON object")
    else:
        data = {}
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"{path}: hooks must be an object")

    desired = {
        "SessionStart": [
            ("build-embed-index.py", "startup|resume|clear|compact", 180),
            ("build-kb-index.py", "startup|resume|clear|compact", 180),
            ("build-activity-index.py", "startup|resume|clear|compact", 180),
            ("sweep-launch.py", "startup|resume|clear|compact", 30),
            ("memory-notify.py", "startup|resume|clear|compact", 30),
            ("distill-notify.py", "startup|resume|clear|compact", 30),
        ],
        "UserPromptSubmit": [
            ("kb-retrieve.py", None, 30),
        ],
        "Stop": [
            ("archive-transcript.py", None, 30),
            ("kb-usage-scan.py", None, 30),
        ],
        "PreToolUse": [
            ("kb-presearch.py", "web|web_search|WebSearch|WebFetch", 30),
        ],
    }
    for event, specs in desired.items():
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"{path}: hooks.{event} must be a list")
        for script, matcher, timeout in specs:
            command = _codex_command(script, vault)
            found = False
            for group in groups:
                if not isinstance(group, dict):
                    continue
                for h in group.get("hooks", []):
                    if isinstance(h, dict) and script in str(h.get("command", "")):
                        h["command"] = command
                        h.setdefault("type", "command")
                        h["timeout"] = timeout
                        h.setdefault("statusMessage", f"KennisBank: {script}")
                        if matcher:
                            group["matcher"] = matcher
                        found = True
            if not found:
                groups.append(_hook_group(script, vault, matcher=matcher, timeout=timeout))
    _write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _toml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _ensure_codex_mcp(path: Path, vault: Path) -> None:
    text = _read_text(path)
    argv = _mcp_server_argv(vault)
    args = ", ".join(_toml_quote(a) for a in argv[1:])
    block = f"""
[mcp_servers.kennisbank]
command = {_toml_quote(argv[0])}
args = [{args}]

[mcp_servers.kennisbank.env]
KB_LLM_ENDPOINT = "http://localhost:11434"
KB_LLM_MODEL = "gemma4:12b"
KB_LLM_PROVIDERS = "ollama"
KENNISBANK_VAULT = "{_posix(vault)}"
""".strip()
    pattern = re.compile(
        r"\n?\[mcp_servers\.kennisbank\]\n.*?(?=\n\[(?!mcp_servers\.kennisbank(?:\.|\]))|\Z)",
        re.S,
    )
    if "[mcp_servers.kennisbank]" in text:
        new = pattern.sub(lambda _m: "\n" + block + "\n", text)
    else:
        new = text.rstrip() + "\n\n" + block + "\n"
    _write_text(path, new)


def install_opencode(repo: Path, vault: Path) -> dict:
    cfg = _opencode_home()
    shared_skills = _home() / ".agents" / "skills"
    commands = cfg / "commands"
    plugins = cfg / "plugins"

    skills = _install_shared_skills(repo, shared_skills)
    written_commands = []
    for name, source, desc in _command_sources(repo):
        dst = commands / f"{name}.md"
        _write_text(dst, _prompt_text(name, source, desc, "OpenCode"))
        written_commands.append(dst)

    _replace_block(cfg / "AGENTS.md", _agent_block("OpenCode", vault))
    plugin = _write_opencode_plugin(plugins / "kennisbank.js", vault)
    config = _ensure_opencode_config(cfg / "opencode.json", vault, plugin)
    return {
        "skills": [str(p) for p in skills],
        "commands": [str(p) for p in written_commands],
        "agents_md": str(cfg / "AGENTS.md"),
        "plugin": str(plugin),
        "mcp": str(config),
    }


def _write_opencode_plugin(path: Path, vault: Path) -> Path:
    scripts = _posix(vault / ".claude" / "scripts")
    vault_s = _posix(vault)
    text = f"""// Generated by LLmWiki-KennisBank. Keep this file small and local-only.
import {{ $ }} from "bun";

const vault = "{vault_s}";
const scripts = "{scripts}";

async function run(script) {{
  try {{
    await $`py -3 ${{scripts}}/${{script}}`.env({{
      ...process.env,
      KENNISBANK_VAULT: vault,
      KB_LLM_PROVIDERS: process.env.KB_LLM_PROVIDERS || "ollama",
      KB_LLM_MODEL: process.env.KB_LLM_MODEL || "gemma4:12b",
      KB_LLM_ENDPOINT: process.env.KB_LLM_ENDPOINT || "http://localhost:11434",
    }}).quiet();
  }} catch (_) {{
    // KennisBank hooks are fail-open.
  }}
}}

export const KennisBankPlugin = async ({{ client }}) => {{
  return {{
    event: async (input) => {{
      if (input.event?.type === "session.idle") {{
        await run("build-embed-index.py");
        await run("build-kb-index.py");
        await run("build-activity-index.py");
        await run("sweep-launch.py");
        await run("memory-notify.py");
        await run("distill-notify.py");
      }}
      if (input.event?.type === "session.updated") {{
        await run("archive-transcript.py");
        await run("kb-usage-scan.py");
      }}
    }},
  }};
}};
"""
    _write_text(path, text)
    return path


def _ensure_opencode_config(path: Path, vault: Path, plugin: Path) -> Path:
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError(f"{path} must contain a JSON object")
    else:
        data = {}
    data.setdefault("$schema", "https://opencode.ai/config.json")
    data["autoupdate"] = False
    data.setdefault("mcp", {})
    data["mcp"]["kennisbank"] = {
        "type": "local",
        "enabled": True,
        "command": _mcp_server_argv(vault),
        "environment": {
            "KENNISBANK_VAULT": _posix(vault),
            "KB_LLM_PROVIDERS": "ollama",
            "KB_LLM_MODEL": "gemma4:12b",
            "KB_LLM_ENDPOINT": "http://localhost:11434",
        },
    }
    data.setdefault("permission", {})
    data["permission"].setdefault("skill", {})
    for skill in ("autoresearch", "kennisbank-upgrade", "kennisbank-contribute"):
        data["permission"]["skill"].setdefault(skill, "allow")
    _write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return path


def install_copilot(repo: Path, vault: Path) -> dict:
    """Install the KennisBank integration for the standalone GitHub Copilot CLI.

    Delegates config mutation to the idempotent _copilot layer (ADR-0003 D1-D6):
    MCP registration, hooks, global instructions and the custom agent profile.
    Shared skills are already discoverable by Copilot from ~/.agents/skills.
    """
    skills = _install_shared_skills(repo, _home() / ".agents" / "skills")
    report = _copilot.install(vault)
    res = report["results"]
    return {
        "skills": [str(p) for p in skills],
        "mcp": res["mcp"]["path"],
        "hooks": res["hooks"]["path"],
        "instructions": res["instructions"]["path"],
        "agent_profile": res["agent_profile"]["path"],
        "home": report["home"],
    }


def validate_files(repo: Path, vault: Path, agents: list[str]) -> list[str]:
    errors: list[str] = []
    for p in (
        vault / ".claude" / "scripts" / "kb-mcp.py",
        vault / ".claude" / "scripts" / "kb-retrieve.py",
        vault / ".claude" / "scripts" / "kb-presearch.py",
        vault / ".claude" / "scripts" / "build-activity-index.py",
        vault / ".claude" / "scripts" / "kb-activity.py",
        vault / ".claude" / "scripts" / "kb-activity-eval.py",
        vault / ".claude" / "kennisbank-embed.json",
        vault / ".claude" / "kennisbank-llm.json",
    ):
        if not p.is_file():
            errors.append(f"missing deployed file: {p}")

    if "claude" in agents:
        base = _home() / ".claude"
        for cmd in ("sessielog", "sessiestart", "kennisbank-upgrade", "weeklog", "timeline", "watdeedik"):
            if not (base / "commands" / f"{cmd}.md").is_file():
                errors.append(f"missing Claude command: {cmd}")
        for skill in ("autoresearch", "kennisbank-upgrade", "kennisbank-contribute"):
            if not (base / "skills" / skill / "SKILL.md").is_file():
                errors.append(f"missing Claude skill: {skill}")
        settings = base / "settings.json"
        if settings.is_file():
            txt = settings.read_text(encoding="utf-8")
            for need in ("kb-retrieve.py", "kb-presearch.py", "build-kb-index.py", "build-activity-index.py"):
                if need not in txt:
                    errors.append(f"missing Claude hook for {need}")
            if "KENNISBANK_VAULT" not in txt:
                errors.append("Claude settings.json lacks KENNISBANK_VAULT env")
        else:
            errors.append(f"missing Claude settings.json: {settings}")

    if "codex" in agents:
        codex = _codex_home()
        for skill in ("autoresearch", "kennisbank-upgrade", "kennisbank-contribute"):
            if not (_home() / ".agents" / "skills" / skill / "SKILL.md").is_file():
                errors.append(f"missing Codex shared skill: {skill}")
        for prompt in ("sessielog", "sessiestart", "kennisbank-upgrade", "weeklog", "timeline", "watdeedik"):
            if not (codex / "prompts" / f"{prompt}.md").is_file():
                errors.append(f"missing Codex prompt alias: {prompt}")
        for p in (codex / "AGENTS.md", codex / "hooks.json", codex / "config.toml"):
            if not p.is_file():
                errors.append(f"missing Codex config file: {p}")
        codex_config = _read_text(codex / "config.toml")
        if codex_config.count("[mcp_servers.kennisbank]") != 1:
            errors.append("Codex config.toml must contain exactly one [mcp_servers.kennisbank] block")
        if codex_config.count("[mcp_servers.kennisbank.env]") != 1:
            errors.append("Codex config.toml must contain exactly one [mcp_servers.kennisbank.env] block")
        if tomllib is not None:
            try:
                tomllib.loads(codex_config)
            except Exception as e:
                errors.append(f"Codex config.toml is not valid TOML: {e}")
        for need in ("kb-retrieve.py", "kb-presearch.py", "build-activity-index.py", "mcp_servers.kennisbank", _posix(vault)):
            combined = _read_text(codex / "hooks.json") + "\n" + codex_config
            if need not in combined:
                errors.append(f"Codex config lacks {need}")

    if "opencode" in agents:
        cfg = _opencode_home()
        for cmd in ("sessielog", "sessiestart", "kennisbank-upgrade", "weeklog", "timeline", "watdeedik"):
            if not (cfg / "commands" / f"{cmd}.md").is_file():
                errors.append(f"missing OpenCode command: {cmd}")
        for p in (cfg / "AGENTS.md", cfg / "plugins" / "kennisbank.js", cfg / "opencode.json"):
            if not p.is_file():
                errors.append(f"missing OpenCode config file: {p}")
        for need in ("kb-mcp.py", "KennisBankPlugin", _posix(vault)):
            combined = _read_text(cfg / "opencode.json") + "\n" + _read_text(cfg / "plugins" / "kennisbank.js")
            if need not in combined:
                errors.append(f"OpenCode config lacks {need}")

    if "copilot" in agents:
        for skill in ("autoresearch", "kennisbank-upgrade", "kennisbank-contribute"):
            if not (_home() / ".agents" / "skills" / skill / "SKILL.md").is_file():
                errors.append(f"missing Copilot shared skill: {skill}")
        if not (vault / ".claude" / "scripts" / "kb-copilot-capture.py").is_file():
            errors.append(f"missing Copilot capture hook script: {vault / '.claude' / 'scripts' / 'kb-copilot-capture.py'}")
        errors.extend(_copilot.validate_config(vault))
    return errors


def validate_mcp_runtime(vault: Path, timeout: int = 15) -> list[str]:
    """Validate that the configured stdio MCP server can initialize."""
    script = vault / ".claude" / "scripts" / "kb-mcp.py"
    if not script.is_file():
        return [f"missing KennisBank MCP server script: {script}"]

    py = _agent_python_argv()
    dep_check = "import mcp; import mcp.client.stdio; import mcp.server.fastmcp"
    try:
        proc = subprocess.run(
            [*py, "-c", dep_check],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        return [f"KennisBank MCP python interpreter not found: {_shell_join(py)}"]
    except subprocess.TimeoutExpired:
        return [f"KennisBank MCP dependency check timed out: {_shell_join(py)}"]
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        return [
            "KennisBank MCP dependency missing or broken for "
            f"{_shell_join(py)}; run: {_shell_join([*py, '-m', 'pip', 'install', 'mcp==1.28.1'])}"
            + (f" ({detail})" if detail else "")
        ]

    payload = {
        "command": _mcp_server_argv(vault)[0],
        "args": _mcp_server_argv(vault)[1:],
        "env": {
            "KENNISBANK_VAULT": _posix(vault),
            "KB_LLM_PROVIDERS": "ollama",
            "KB_LLM_MODEL": "gemma4:12b",
            "KB_LLM_ENDPOINT": "http://localhost:11434",
        },
    }
    client_code = r'''
import anyio
import json
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    cfg = json.loads(sys.argv[1])
    env = dict(os.environ)
    env.update(cfg.get("env") or {})
    params = StdioServerParameters(
        command=cfg["command"],
        args=cfg["args"],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            missing = {"recall", "capture", "what_did_i_do", "timeline", "weeklog", "topic_timeline"} - names
            if missing:
                raise SystemExit("missing MCP tools: " + ", ".join(sorted(missing)))
            print("MCP handshake OK: " + ", ".join(sorted(names)))

anyio.run(main)
'''
    env = dict(os.environ)
    env.update(payload["env"])
    try:
        proc = subprocess.run(
            [*py, "-c", client_code, json.dumps(payload)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
        )
    except FileNotFoundError:
        return [f"KennisBank MCP python interpreter not found: {_shell_join(py)}"]
    except subprocess.TimeoutExpired:
        return [f"KennisBank MCP handshake timed out: {_shell_join(_mcp_server_argv(vault))}"]
    if proc.returncode != 0:
        detail = "\n".join(x for x in (proc.stderr.strip(), proc.stdout.strip()) if x).strip()
        if len(detail) > 1200:
            detail = detail[:1200] + "..."
        return [f"KennisBank MCP handshake failed for {_shell_join(_mcp_server_argv(vault))}: {detail}"]
    return []


def _json_file(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _secrets_path() -> Path:
    raw = os.environ.get("KENNISBANK_SECRETS_FILE", "").strip()
    if raw:
        return _norm_path(raw)
    return _home() / ".config" / "kennisbank" / "secrets.json"


def _write_user_secret(name: str, value: str) -> Path:
    path = _secrets_path()
    data = _json_file(path)
    data[name] = value
    _write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def _read_user_secret(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    data = _json_file(_secrets_path())
    return str(data.get(name, "")).strip()


def configure_llm(
    vault: Path,
    provider: str,
    model: str | None = None,
    api_key_env: str = "OPENROUTER_API_KEY",
    api_key_value: str | None = None,
) -> dict:
    provider = provider.lower().strip()
    cfg_path = vault / ".claude" / "kennisbank-llm.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = _json_file(cfg_path)
    if provider == "ollama":
        cfg.update({
            "providers": ["ollama"],
            "model": model or cfg.get("model") or "gemma4:latest",
            "endpoint": "http://localhost:11434",
        })
        cfg.pop("api_key_env", None)
    elif provider == "openrouter":
        cfg.update({
            "providers": ["openrouter"],
            "model": model or cfg.get("model") or OPENROUTER_DEFAULT_MODEL,
            "endpoint": OPENROUTER_ENDPOINT,
            "api_key_env": api_key_env or "OPENROUTER_API_KEY",
        })
        if api_key_value:
            _write_user_secret(cfg["api_key_env"], api_key_value)
    else:
        raise ValueError(f"unknown LLM provider: {provider}")
    _write_text(cfg_path, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    return cfg


def _resolve_llm_config(vault: Path) -> dict:
    cfg = _json_file(vault / ".claude" / "kennisbank-llm.json")
    providers = cfg.get("providers") or ["ollama"]
    if isinstance(providers, str):
        providers = [p.strip() for p in providers.split(",") if p.strip()]
    return {
        "providers": providers,
        "model": os.environ.get("KB_LLM_MODEL") or cfg.get("model") or "gemma4:latest",
        "endpoint": os.environ.get("KB_LLM_ENDPOINT") or cfg.get("endpoint") or "http://localhost:11434",
        "api_key_env": os.environ.get("KB_LLM_API_KEY_ENV") or cfg.get("api_key_env") or "OPENROUTER_API_KEY",
        "models": cfg.get("models") if isinstance(cfg.get("models"), dict) else {},
    }


def _resolve_embed_config(vault: Path) -> dict:
    cfg = _json_file(vault / ".claude" / "kennisbank-embed.json")
    return {
        "provider": os.environ.get("KB_EMBED_PROVIDER") or cfg.get("provider") or "ollama",
        "model": os.environ.get("KB_EMBED_MODEL") or cfg.get("model") or "qwen3-embedding:8b",
        "endpoint": os.environ.get("KB_EMBED_ENDPOINT") or cfg.get("endpoint") or "http://localhost:11434",
    }


def validate_models(vault: Path, timeout: int = 45) -> list[str]:
    errors: list[str] = []
    llm = _resolve_llm_config(vault)
    emb = _resolve_embed_config(vault)
    llm_providers = [str(p).lower() for p in llm["providers"]]
    needs_ollama = emb["provider"] == "ollama" or "ollama" in llm_providers

    def run(payload: dict) -> tuple[int, str, str]:
        proc = subprocess.run(
            ["ollama", "show", payload["model"]],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def ollama_json(path: str, payload: dict) -> dict:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:11434" + path,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    if needs_ollama:
        try:
            subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=True,
            )
        except FileNotFoundError:
            return ["ollama executable not found"]
        except subprocess.TimeoutExpired:
            return ["ollama list timed out"]
        except subprocess.CalledProcessError as e:
            return [f"ollama list failed: {(e.stderr or e.stdout).strip()}"]

    if emb["provider"] == "ollama":
        rc, _out, err = run(emb)
        if rc != 0:
            errors.append(f"ollama model missing/unavailable for embedding: {emb['model']} ({err.strip()})")
        try:
            body = ollama_json("/api/embeddings", {"model": emb["model"], "prompt": "kennisbank"})
            if not body.get("embedding"):
                errors.append(f"embedding smoke returned no vector for {emb['model']}")
        except Exception as e:
            errors.append(f"embedding smoke failed for {emb['model']}: {e}")

    if "ollama" in llm_providers:
        model = llm["models"].get("ollama") or llm["model"]
        rc, _out, err = run({"model": model})
        if rc != 0:
            errors.append(f"ollama model missing/unavailable for llm: {model} ({err.strip()})")
        try:
            body = ollama_json(
                "/api/generate",
                {"model": model, "prompt": MODEL_CHECK_TEXT, "stream": False, "options": {"temperature": 0}},
            )
            content = body.get("response") or ""
            if "OK" not in content:
                errors.append(f"llm smoke did not return OK for {model}: {content.strip()[:120]}")
        except Exception as e:
            errors.append(f"llm smoke failed for {model}: {e}")

    if "openrouter" in llm_providers:
        model = llm["models"].get("openrouter") or llm["model"] or OPENROUTER_DEFAULT_MODEL
        key_env = llm["api_key_env"] or "OPENROUTER_API_KEY"
        key = _read_user_secret(key_env)
        if not key:
            errors.append(f"OpenRouter API key missing: set {key_env} or store it with setup")
        else:
            endpoint = (llm["endpoint"] or OPENROUTER_ENDPOINT).rstrip("/")
            try:
                payload = json.dumps({
                    "model": model,
                    "messages": [{"role": "user", "content": MODEL_CHECK_TEXT}],
                    "max_tokens": 8,
                    "temperature": 0,
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{endpoint}/chat/completions",
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                        "X-OpenRouter-Title": "LLmWiki-KennisBank setup validation",
                    },
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                content = body["choices"][0]["message"].get("content") or ""
                if "OK" not in content:
                    errors.append(f"OpenRouter smoke did not return OK for {model}: {content[:120]}")
            except Exception as e:
                errors.append(f"OpenRouter smoke failed for {model}: {e}")
    return errors


def parse_agents(raw: str | None) -> list[str]:
    if not raw:
        return ["claude", "codex"]
    vals = [v.strip().lower() for v in raw.replace(";", ",").split(",") if v.strip()]
    if "all" in vals:
        return list(AGENTS)
    bad = [v for v in vals if v not in AGENTS]
    if bad:
        raise SystemExit(f"unknown agent(s): {', '.join(bad)}. Known: {', '.join(AGENTS)}, all")
    return vals


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--vault", required=True)
    ap.add_argument("--agents", default="claude,codex")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--configure-llm", action="store_true")
    ap.add_argument("--llm-provider", choices=["ollama", "openrouter"])
    ap.add_argument("--llm-model")
    ap.add_argument("--llm-api-key-env", default="OPENROUTER_API_KEY")
    ap.add_argument("--skip-models", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    repo = _norm_path(args.repo)
    vault = _norm_path(args.vault)
    agents = parse_agents(args.agents)
    result: dict = {
        "repo": str(repo),
        "vault": str(vault),
        "agents": agents,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "install": {},
        "validation_errors": [],
    }
    try:
        if args.configure_llm:
            key_value = os.environ.get("KENNISBANK_OPENROUTER_API_KEY_TO_STORE", "")
            result["llm_config"] = configure_llm(
                vault,
                args.llm_provider or "ollama",
                model=args.llm_model,
                api_key_env=args.llm_api_key_env,
                api_key_value=key_value or None,
            )
        if args.install:
            if "codex" in agents:
                result["install"]["codex"] = install_codex(repo, vault)
            if "opencode" in agents:
                result["install"]["opencode"] = install_opencode(repo, vault)
            if "copilot" in agents:
                result["install"]["copilot"] = install_copilot(repo, vault)
        if args.validate:
            result["validation_errors"].extend(validate_files(repo, vault, agents))
            if any(a in agents for a in ("codex", "opencode", "copilot")):
                result["validation_errors"].extend(validate_mcp_runtime(vault))
            if not args.skip_models:
                result["validation_errors"].extend(validate_models(vault))
    except Exception as e:
        result["validation_errors"].append(str(e))

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for client, info in result["install"].items():
            print(f"{client}: installed")
            for key, val in info.items():
                if isinstance(val, list):
                    print(f"  {key}: {len(val)}")
                else:
                    print(f"  {key}: {val}")
        if result["validation_errors"]:
            print("validation: FAIL")
            for err in result["validation_errors"]:
                print(f"  - {err}")
        elif args.validate:
            print("validation: PASS")
    return 1 if result["validation_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
