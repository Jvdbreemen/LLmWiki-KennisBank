"""Keep the suite out of the ambient vault.

A test that opens an index without passing a path lands on
``vault_root()/.claude/`` and `_kbindex.connect()` creates that directory. On a
developer machine it writes into the real vault; on CI it creates
``<workspace>/.claude`` -- and `_vaultpath._script_vault()` then treats the
workspace as a vault, so every later test asserting the *default* root gets the
workspace instead of ``~/KennisBank``.

That is how PR #105 turned main red while the suite was green locally: three
tests in test_vaultpath.py failed on CI only, because locally KENNISBANK_VAULT
is always set and the fallback never runs.

Pointing the whole session at an empty temporary vault fixes the class, not the
instance: a stray write goes to a directory nobody reads, and tests that need a
specific root still set the variable themselves.
"""
import os
import tempfile

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolated_vault():
    saved = os.environ.get("KENNISBANK_VAULT")
    tmp = tempfile.TemporaryDirectory(prefix="kb-test-vault-")
    os.environ["KENNISBANK_VAULT"] = tmp.name
    try:
        yield tmp.name
    finally:
        if saved is None:
            os.environ.pop("KENNISBANK_VAULT", None)
        else:
            os.environ["KENNISBANK_VAULT"] = saved
        tmp.cleanup()
