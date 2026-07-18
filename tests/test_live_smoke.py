"""Live smoke test against the real Famly API.

Skipped unless FAMLY_EMAIL and FAMLY_PASSWORD are set in the environment, so
this never runs (or hangs) in CI or a plain offline `pytest -q`. Run it
locally with real credentials to sanity-check login + the children endpoint
against the live account:

    FAMLY_EMAIL=... FAMLY_PASSWORD=... .venv/bin/pytest -q tests/test_live_smoke.py
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("FAMLY_EMAIL") and os.environ.get("FAMLY_PASSWORD")),
    reason="live creds not set",
)


def test_login_and_children_live():
    from famly.config import Config
    from famly.auth import authenticated_client
    from famly.sources.children import fetch_children

    cfg = Config("https://app.famly.co")
    creds = cfg.resolve_credentials()
    c = authenticated_client(cfg.base_url, creds, config_dir=cfg.config_dir, device_id=cfg.device_id())
    kids = fetch_children(c)
    assert kids and kids[0].name
