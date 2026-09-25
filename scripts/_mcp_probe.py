#!/usr/bin/env python3
"""Probe the local runtime required by the KennisBank MCP server."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import struct
import sys
from typing import Any


def _version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return ""


def _failure(code: str, message: str, **details: Any) -> dict[str, Any]:
    result = {
        "ok": False,
        "python": sys.executable,
        "mcp": "",
        "mcp_api": "",
        "sqlite_vec": "",
        "load_extension": False,
        "enable_load_extension": False,
        "vec_version": "",
        "vec0": False,
        "error_code": code,
        "error": message,
    }
    result.update(details)
    return result


def _probe_connection(conn, sqlite_vec) -> dict[str, Any]:
    load_extension = hasattr(conn, "load_extension")
    enable_load_extension = hasattr(conn, "enable_load_extension")
    if not load_extension or not enable_load_extension:
        try:
            conn.close()
        except Exception:
            pass
        return _failure(
            "extension_loading_unsupported",
            "Python sqlite3 has no load_extension/enable_load_extension API",
            load_extension=load_extension,
            enable_load_extension=enable_load_extension,
        )
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        version = conn.execute("SELECT vec_version()").fetchone()[0]
        conn.execute(
            "CREATE VIRTUAL TABLE probe_vec_docs USING vec0("
            "doc_id INTEGER PRIMARY KEY, embedding float[3])"
        )
        vector = struct.pack("3f", 1.0, 0.0, 0.0)
        conn.execute(
            "INSERT INTO probe_vec_docs(doc_id, embedding) VALUES (?, ?)",
            (1, vector),
        )
        row = conn.execute(
            "SELECT doc_id FROM probe_vec_docs WHERE embedding MATCH ? "
            "ORDER BY distance LIMIT 1",
            (vector,),
        ).fetchone()
        if not row or int(row[0]) != 1:
            return _failure(
                "vec0_unavailable",
                "sqlite-vec loaded but the vec0 query returned no row",
                vec_version=str(version),
            )
        return {
            "ok": True,
            "python": sys.executable,
            "mcp": _version("mcp"),
            "mcp_api": "unknown",
            "sqlite_vec": _version("sqlite-vec"),
            "load_extension": True,
            "enable_load_extension": True,
            "vec_version": str(version),
            "vec0": True,
            "error_code": "",
            "error": "",
        }
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        if "no such module" in message.lower() or "vec0" in message.lower():
            code = "vec0_unavailable"
        else:
            code = "search_error"
        return _failure(code, message)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def probe() -> dict[str, Any]:
    try:
        import mcp  # noqa: F401
        from mcp import client  # noqa: F401
    except Exception as exc:
        return _failure("mcp_missing", f"mcp import failed: {type(exc).__name__}: {exc}")
    try:
        try:
            from mcp.server import mcpserver  # noqa: F401
            api = "modern"
        except Exception:
            from mcp.server import fastmcp  # noqa: F401
            api = "legacy"
    except Exception as exc:
        return _failure(
            "mcp_api_missing",
            f"mcp server API import failed: {type(exc).__name__}: {exc}",
        )
    try:
        import sqlite_vec
    except Exception as exc:
        return _failure(
            "sqlite_vec_missing",
            f"sqlite-vec import failed: {type(exc).__name__}: {exc}",
        )
    try:
        import sqlite3
        conn = sqlite3.connect(":memory:")
    except Exception as exc:
        return _failure("sqlite_open_failed", f"SQLite open failed: {type(exc).__name__}: {exc}")
    result = _probe_connection(conn, sqlite_vec)
    if result.get("ok"):
        result["mcp_api"] = api
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.parse_args(argv)
    result = probe()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
