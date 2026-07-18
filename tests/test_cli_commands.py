import json

import click
from click.testing import CliRunner

from famly import cli
from famly.auth import TokenStore
from famly.client import AuthError
from famly.models import Child, Conversation, Event, FeedItem, Observation


def test_children_outputs_json(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])
    # --quiet keeps stdout as pure JSON; progress is on stderr (see test_progress_*).
    res = CliRunner().invoke(cli.main, ["--quiet", "children"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data[0]["name"] == "Robin"


def test_cached_token_skips_credential_resolution(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("FAMLY_ACCESS_TOKEN", raising=False)
    TokenStore(tmp_path).save("CACHED")

    def _boom(self, cli_email=None, cli_password=None, cli_token=None):
        raise AssertionError("resolve_credentials should not be called when a token is cached")

    monkeypatch.setattr("famly.config.Config.resolve_credentials", _boom)
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])
    res = CliRunner().invoke(cli.main, ["--quiet", "children"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data[0]["name"] == "Robin"


def test_explicit_creds_bypass_mismatched_cache(monkeypatch, tmp_path):
    """A cached token for account A must not silently answer a request made
    with explicit credentials for account B."""
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("FAMLY_ACCESS_TOKEN", raising=False)
    TokenStore(tmp_path).save("CACHED", email="old@example.com")
    captured = {}

    def fake_auth_client(base_url, creds, *, config_dir, device_id, transport=None, force=False):
        captured.update(email=creds.email, force=force)
        return _FakeClient(get_result={})

    monkeypatch.setattr(cli, "authenticated_client", fake_auth_client)
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])
    res = CliRunner().invoke(cli.main, ["--quiet", "--email", "new@example.com",
                                        "--password", "pw", "children"])
    assert res.exit_code == 0
    assert captured["email"] == "new@example.com"
    assert captured["force"] is True  # must not fall back onto the same stale cache


def test_matching_email_still_uses_cached_token(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("FAMLY_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("FAMLY_EMAIL", "same@example.com")
    monkeypatch.setenv("FAMLY_PASSWORD", "pw")
    TokenStore(tmp_path).save("CACHED", email="same@example.com")

    def _boom(*a, **k):
        raise AssertionError("must not re-login when the cached token matches the account")

    monkeypatch.setattr(cli, "authenticated_client", _boom)
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])
    res = CliRunner().invoke(cli.main, ["--quiet", "children"])
    assert res.exit_code == 0
    assert json.loads(res.output)[0]["name"] == "Robin"


def test_expired_cache_self_heals_with_env_credentials(monkeypatch, tmp_path):
    """Headless runs with FAMLY_EMAIL/FAMLY_PASSWORD exported must transparently
    re-login when the cached token has expired, not demand `famly login`."""
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("FAMLY_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("FAMLY_EMAIL", "a@b.com")
    monkeypatch.setenv("FAMLY_PASSWORD", "pw")
    TokenStore(tmp_path).save("STALE", email="a@b.com")
    me = {"roles2": [{"targetType": "Famly.Daycare:Child", "targetId": "child-1",
                      "title": "Robin", "subtitle": "Inst"}]}

    def transport(method, url, headers, body):
        if "/graphql?Authenticate" in url:
            return 200, json.dumps(
                {"data": {"me": {"authenticateWithPassword": {"accessToken": "NEW"}}}}).encode()
        if headers.get("x-famly-accesstoken") == "STALE":
            return 401, b""
        return 200, json.dumps(me).encode()

    monkeypatch.setattr("famly.client._urllib_transport", transport)
    res = CliRunner().invoke(cli.main, ["--quiet", "children"])
    assert res.exit_code == 0
    assert json.loads(res.output)[0]["name"] == "Robin"
    assert TokenStore(tmp_path).load() == "NEW"  # healed token persisted for next run


def test_expired_cache_without_credentials_still_asks_for_login(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    for var in ("FAMLY_ACCESS_TOKEN", "FAMLY_EMAIL", "FAMLY_PASSWORD", "FAMLY_OP_ITEM"):
        monkeypatch.delenv(var, raising=False)
    TokenStore(tmp_path).save("STALE")
    monkeypatch.setattr("famly.client._urllib_transport", lambda m, u, h, b: (401, b""))
    res = CliRunner().invoke(cli.main, ["children"])
    assert res.exit_code != 0
    assert "Run `famly login`" in res.output


def test_feed_outputs_json(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(
        cli, "fetch_feed", lambda c, since=None: [FeedItem("f1", "2026-01-01", "Room", "hello")]
    )
    res = CliRunner().invoke(cli.main, ["--quiet", "feed"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data[0]["body"] == "hello"


def test_events_requires_from_and_to(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    res = CliRunner().invoke(cli.main, ["events"])
    assert res.exit_code != 0


def test_events_outputs_json_using_default_child(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])
    calls = {}

    def fake_fetch_events(c, child_id, frm, to):
        calls["child_id"] = child_id
        return [Event("e1", "Sports Day", "2026-02-01", "2026-02-01", True)]

    monkeypatch.setattr(cli, "fetch_events", fake_fetch_events)
    res = CliRunner().invoke(cli.main, ["--quiet", "events", "--from", "2026-02-01", "--to", "2026-02-02"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data[0]["title"] == "Sports Day"
    assert calls["child_id"] == "child-1"


def test_messages_unread_filters(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    convos = [
        Conversation("c1", "Unread convo", ["A"], False, [], unread=True),
        Conversation("c2", "Read convo", ["B"], False, [], unread=False),
    ]
    captured = {}

    def fake_fetch(c, include_archived=False, unread_only=False):
        captured["unread_only"] = unread_only
        return [x for x in convos if x.unread] if unread_only else convos

    monkeypatch.setattr(cli, "fetch_conversations", fake_fetch)
    res = CliRunner().invoke(cli.main, ["--quiet", "messages", "--unread"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert [c["id"] for c in data] == ["c1"]
    assert captured["unread_only"] is True  # filtering happens at fetch time, not post-hoc


def test_observations_since_filters(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])
    obs = [
        Observation("o1", "note", "2026-06-25T10:00:00Z", "Room", "June obs"),
        Observation("o2", "note", "2026-01-01T10:00:00Z", "Room", "January obs"),
    ]
    monkeypatch.setattr(cli, "fetch_observations", lambda c, cid: obs)
    res = CliRunner().invoke(cli.main, ["--quiet", "observations", "--since", "2026-06-01T00:00:00Z"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert [o["id"] for o in data] == ["o1"]


class _FakeClient:
    def __init__(self, get_result=None, exc=None):
        self._get_result = get_result
        self._exc = exc
        self.token = "T"

    def get(self, path, params=None):
        if self._exc is not None:
            raise self._exc
        return self._get_result


def test_whoami_reports_authenticated(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(cli, "_client", lambda ctx: _FakeClient(get_result={}))
    res = CliRunner().invoke(cli.main, ["whoami"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["authenticated"] is True


def test_whoami_reports_unauthenticated_when_token_invalid(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(cli, "_client", lambda ctx: _FakeClient(exc=AuthError("unauthorized")))
    res = CliRunner().invoke(cli.main, ["whoami"])
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["authenticated"] is False


def test_auth_error_surfaces_clean_message(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")

    def _boom(c):
        raise AuthError("unauthorized")

    monkeypatch.setattr(cli, "fetch_children", _boom)
    res = CliRunner().invoke(cli.main, ["children"])
    assert res.exit_code != 0
    assert "Run `famly login`" in res.output


def test_photos_unknown_child_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])
    res = CliRunner().invoke(cli.main, ["photos", "--child", "bogus", "--out", str(tmp_path / "p")])
    assert res.exit_code != 0
    assert "No child with id bogus" in res.output


def test_photos_rejects_unknown_source(monkeypatch, tmp_path):
    """A typo like --sources observation must error, not 'succeed' with zero
    downloads as if the account had no photos."""
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])
    res = CliRunner().invoke(cli.main, ["photos", "--sources", "observation",
                                        "--out", str(tmp_path / "p")])
    assert res.exit_code != 0
    assert "observation" in res.output and "observations" in res.output


def test_photos_sources_tolerates_whitespace(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])
    captured = {}

    def fake_download_all(client, child, out, *, sources, **kwargs):
        captured["sources"] = sources
        return {"downloaded": 0, "failed": 0, "total_refs": 0, "out_dir": out}

    monkeypatch.setattr(cli, "download_all", fake_download_all)
    res = CliRunner().invoke(cli.main, ["--quiet", "photos", "--sources", "feed, messages",
                                        "--out", str(tmp_path / "p")])
    assert res.exit_code == 0
    assert captured["sources"] == ["feed", "messages"]


def test_gallery_missing_manifest_is_clean_error(tmp_path):
    res = CliRunner().invoke(cli.main, ["gallery", str(tmp_path / "nonexistent")])
    assert res.exit_code != 0
    assert "manifest" in res.output.lower()  # a clean message, not a raw traceback


def test_gallery_corrupt_manifest_is_clean_error(tmp_path):
    (tmp_path / "_manifest.json").write_text("not json")
    res = CliRunner().invoke(cli.main, ["gallery", str(tmp_path)])
    assert res.exit_code != 0
    assert "_manifest.json" in res.output


def test_gallery_writes_html_from_manifest(tmp_path):
    manifest = tmp_path / "_manifest.json"
    manifest.write_text(json.dumps([{"file": "a.jpg", "id": "1", "source": "feed", "date": "2026-01-01",
                                     "author": "Room", "caption": "hi", "w": 10, "h": 10, "ref": "r1"}]))
    res = CliRunner().invoke(cli.main, ["gallery", str(tmp_path)])
    assert res.exit_code == 0
    out = tmp_path / "gallery.html"
    assert out.exists()
    assert "hi" in out.read_text() or "a.jpg" in out.read_text()


def test_photos_calls_download_all_with_expected_kwargs(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])

    captured = {}

    def fake_download_all(client, child, out, *, sources, since, incremental, include_videos,
                          include_files, make_gallery, quiet=False):
        captured.update(child=child, out=out, sources=sources, since=since, incremental=incremental,
                        include_videos=include_videos, include_files=include_files,
                        make_gallery=make_gallery, quiet=quiet)
        return {"downloaded": 0, "total_refs": 0, "out_dir": out}

    monkeypatch.setattr(cli, "download_all", fake_download_all)
    res = CliRunner().invoke(cli.main, ["--quiet", "photos", "--out", str(tmp_path / "photos")])
    assert res.exit_code == 0
    assert captured["child"].id == "child-1"
    assert captured["sources"] == cli.ALL_SOURCES
    assert captured["quiet"] is True  # global --quiet is threaded into download_all
    data = json.loads(res.output)
    assert data["downloaded"] == 0


def test_progress_goes_to_stderr_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])
    res = CliRunner().invoke(cli.main, ["children"])
    assert res.exit_code == 0
    # Progress narrates on stderr; the JSON result stays on stdout.
    assert "Fetching children" in res.stderr
    assert "Fetching children" not in res.stdout
    assert json.loads(res.stdout)[0]["name"] == "Robin"


def test_quiet_flag_silences_progress(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])
    res = CliRunner().invoke(cli.main, ["--quiet", "children"])
    assert res.exit_code == 0
    assert res.stderr == ""


def test_help_lists_all_commands():
    res = CliRunner().invoke(cli.main, ["--help"])
    assert res.exit_code == 0
    for cmd in ["login", "whoami", "children", "feed", "messages", "events", "observations",
                "photos", "gallery", "export"]:
        assert cmd in res.output


def test_observations_errors_on_childless_account(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: [])
    res = CliRunner().invoke(cli.main, ["observations"])
    assert res.exit_code != 0
    assert "No children" in res.output


def test_events_errors_on_childless_account(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: [])
    res = CliRunner().invoke(cli.main, ["events", "--from", "2026-07-01", "--to", "2026-07-31"])
    assert res.exit_code != 0
    assert "No children" in res.output


def test_abort_during_command_is_not_masked_as_creds_error(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: (_ for _ in ()).throw(click.Abort()))
    res = CliRunner().invoke(cli.main, ["children"])
    assert res.exit_code != 0
    assert "Set FAMLY_EMAIL" not in res.output


def test_export_outputs_summary_with_wide_event_window(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    monkeypatch.setattr(cli, "fetch_children", lambda c: [Child("child-1", "Robin", "inst-1")])
    captured = {}

    def fake_export_all(client, out, children, *, events_from, events_to, quiet=False, all_children=None):
        captured.update(out=out, children=children, events_from=events_from, events_to=events_to)
        return {"out_dir": out, "children": len(children)}

    monkeypatch.setattr(cli, "export_all", fake_export_all)
    res = CliRunner().invoke(cli.main, ["--quiet", "export", "--out", str(tmp_path / "arc")])
    assert res.exit_code == 0
    assert json.loads(res.output)["children"] == 1
    assert [k.id for k in captured["children"]] == ["child-1"]
    # −3y … +1y window, ISO dates
    from datetime import date
    frm, to = date.fromisoformat(captured["events_from"]), date.fromisoformat(captured["events_to"])
    today = date.today()
    assert (today - frm).days in range(1090, 1100) and (to - today).days in range(360, 370)


def test_export_child_flag_narrows_and_validates(monkeypatch, tmp_path):
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("FAMLY_ACCESS_TOKEN", "T")
    kids = [Child("child-1", "Robin", "inst-1"), Child("child-2", "Sam", "inst-1")]
    monkeypatch.setattr(cli, "fetch_children", lambda c: kids)
    captured = {}

    def fake_export_all(client, out, children, **kwargs):
        captured["children"] = children
        captured["all_children"] = kwargs.get("all_children")
        return {"out_dir": out}

    monkeypatch.setattr(cli, "export_all", fake_export_all)
    res = CliRunner().invoke(cli.main, ["--quiet", "export", "--child", "child-2",
                                        "--out", str(tmp_path / "arc")])
    assert res.exit_code == 0
    assert [k.id for k in captured["children"]] == ["child-2"]
    assert [k.id for k in captured["all_children"]] == ["child-1", "child-2"]
    res = CliRunner().invoke(cli.main, ["--quiet", "export", "--child", "bogus",
                                        "--out", str(tmp_path / "arc")])
    assert res.exit_code != 0
    assert "No child with id bogus" in res.output


def test_subcommand_help_exits_cleanly(monkeypatch, tmp_path):
    """click implements --help via click.exceptions.Exit, which subclasses
    RuntimeError — FamlyGroup's credentials-error mapping must not swallow it."""
    monkeypatch.setenv("FAMLY_CONFIG_DIR", str(tmp_path))
    for var in ("FAMLY_ACCESS_TOKEN", "FAMLY_EMAIL", "FAMLY_PASSWORD", "FAMLY_OP_ITEM"):
        monkeypatch.delenv(var, raising=False)
    res = CliRunner().invoke(cli.main, ["export", "--help"])
    assert res.exit_code == 0
    assert "Set FAMLY_EMAIL" not in res.output
