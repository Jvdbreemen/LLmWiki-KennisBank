"""Shared vault-path resolution for the KennisBank scripts.

A single source of truth for "where is the vault?". All scripts resolve the
vault root the same way:

1. the ``KENNISBANK_VAULT`` environment variable, if set and non-empty;
2. otherwise the default ``~/KennisBank``.

This replaces the per-file ``Path.home() / "KennisBank"`` hardcodes so the
whole script layer can be pointed at another vault with one env var, e.g.::

    KENNISBANK_VAULT=/tmp/test python3 stale-check.py

Stdlib only. No hyphen in the filename so the scripts can ``import`` it after
``sys.path.insert`` (the same trick used for ``_frontmatter.py``).
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "KENNISBANK_VAULT"
DEFAULT_VAULT = Path.home() / "KennisBank"


def vault_root() -> Path:
    """Return the vault root.

    Honors ``$KENNISBANK_VAULT`` (expanding ``~`` and env vars); falls back to
    ``~/KennisBank`` when the variable is unset or empty. The path is returned
    as-is (not resolved) so callers can decide whether to ``.resolve()``.
    """
    raw = os.environ.get(ENV_VAR, "").strip()
    if raw:
        return Path(os.path.expanduser(os.path.expandvars(raw)))
    return DEFAULT_VAULT
