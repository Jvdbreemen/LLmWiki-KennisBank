"""Shared test helper: load hyphenated scripts as importable modules.

Scripts in scripts/ use hyphens in their filenames (e.g. build-karpathy-index.py)
so they are not importable via a normal `import`. We load them by path with
importlib.util.spec_from_file_location. _frontmatter.py has no hyphen and is
imported directly via sys.path in test_frontmatter.py.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def load_script(filename: str):
    """Load a script from scripts/ by filename and return the module object.

    The module is given a sanitized name (hyphens -> underscores) and is NOT
    registered in sys.modules under its real hyphenated name, so repeated loads
    stay isolated.
    """
    path = SCRIPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"script not found: {path}")
    mod_name = "script_" + filename.replace("-", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    # Register so dataclasses / typing resolve module globals if needed.
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module
