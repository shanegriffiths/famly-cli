import urllib.error

import pytest
from famly.client import ApiClient, ApiError, AuthError
from tests.conftest import FakeTransport, SequenceTransport


def test_get_sends_token_header():
    t = FakeTransport()
    t.add("/api/v2/thing", {"ok": True})
    c = ApiClient("https://app.famly.co", token="TT", transport=t)
    assert c.get("/api/v2/thing") == {"ok": True}
    assert t.calls[0]["headers"]["x-famly-accesstoken"] == "TT"


def test_graphql_returns_data_and_posts_operation():
    t = FakeTransport()
    t.add("/graphql?Op", {"data": {"hello": 1}})
    c = ApiClient("https://app.famly.co", token="TT", transport=t)
    assert c.graphql("Op", {"a": 1}, "query{}") == {"hello": 1}
    call = t.calls[0]
    assert call["method"] == "POST" and call["body"]["operationName"] == "Op"


def test_graphql_malformed_response_no_data_no_errors():
    """GraphQL response with neither data nor errors raises ApiError."""
    t = FakeTransport()
    t.add("/graphql?Op", {"something_else": 1})
    c = ApiClient("https://app.famly.co", transport=t)
    with pytest.raises(ApiError):
        c.graphql("Op", {}, "query{}")


def test_graphql_error_response():
    """GraphQL response with errors raises ApiError."""
    t = FakeTransport()
    t.add("/graphql?Op", {"errors": [{"message": "boom"}]})
    c = ApiClient("https://app.famly.co", transport=t)
    with pytest.raises(ApiError):
        c.graphql("Op", {}, "query{}")


def test_get_401_unauthorized():
    """GET against 401 status raises AuthError."""
    t = FakeTransport()
    t.add("/api/v2/thing", {}, status=401)
    c = ApiClient("https://app.famly.co", transport=t)
    with pytest.raises(AuthError):
        c.get("/api/v2/thing")


def test_get_500_server_error():
    """GET against 500 status raises ApiError."""
    t = FakeTransport()
    t.add("/api/v2/thing", {}, status=500)
    c = ApiClient("https://app.famly.co", transport=t)
    with pytest.raises(ApiError):
        c.get("/api/v2/thing")


class _FakeResponse:
    status = 200
    def read(self): return b"{}"
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_urllib_transport_sets_timeout(monkeypatch):
    """A stalled server must not hang the CLI forever: every request carries a timeout."""
    from famly import client as client_mod
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(client_mod.urllib.request, "urlopen", fake_urlopen)
    client_mod._urllib_transport("GET", "https://app.famly.co/x", {}, None)
    assert captured["timeout"] is not None and captured["timeout"] > 0


def test_urllib_transport_timeout_env_override(monkeypatch):
    from famly import client as client_mod
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(client_mod.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("FAMLY_HTTP_TIMEOUT", "5")
    client_mod._urllib_transport("GET", "https://app.famly.co/x", {}, None)
    assert captured["timeout"] == 5.0


def test_urllib_transport_maps_read_timeout_to_apierror(monkeypatch):
    """A timeout during the response read raises bare TimeoutError (not
    URLError) — it must still surface as a clean ApiError."""
    from famly import client as client_mod

    def fake_urlopen(req, timeout=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr(client_mod.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ApiError):
        client_mod._urllib_transport("GET", "https://app.famly.co/x", {}, None)


def test_urllib_transport_maps_urlerror_to_apierror(monkeypatch):
    """No network/DNS must surface as a clean ApiError, not a raw URLError traceback."""
    from famly import client as client_mod

    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("dns down")

    monkeypatch.setattr(client_mod.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ApiError):
        client_mod._urllib_transport("GET", "https://app.famly.co/x", {}, None)


def test_401_refreshes_token_and_retries_once():
    t = SequenceTransport((401, b""), (200, b'{"ok": true}'))
    refreshed = []

    def refresh():
        refreshed.append(1)
        return "NEW"

    c = ApiClient("https://app.famly.co", token="OLD", transport=t, refresh=refresh)
    assert c.get("/api/x") == {"ok": True}
    assert refreshed == [1]
    assert c.token == "NEW"
    assert t.calls[1]["headers"]["x-famly-accesstoken"] == "NEW"


def test_401_refresh_returning_none_raises_autherror():
    t = SequenceTransport((401, b""))
    c = ApiClient("https://app.famly.co", token="OLD", transport=t, refresh=lambda: None)
    with pytest.raises(AuthError):
        c.get("/api/x")


def test_401_after_refresh_raises_instead_of_looping():
    t = SequenceTransport((401, b""), (401, b""))
    c = ApiClient("https://app.famly.co", token="OLD", transport=t, refresh=lambda: "NEW")
    with pytest.raises(AuthError):
        c.get("/api/x")
    assert len(t.calls) == 2  # retried exactly once


def test_download_sends_auth_to_famly_hosts_and_returns_bytes():
    t = SequenceTransport((200, b"IMG"))
    c = ApiClient("https://app.famly.co", token="TT", transport=t)
    assert c.download("https://img.famly.co/image/H/1x1/a.jpg") == b"IMG"
    assert t.calls[0]["headers"]["x-famly-accesstoken"] == "TT"


def test_download_omits_token_for_foreign_hosts():
    """The access token must not leak to non-Famly hosts (e.g. presigned S3 URLs)."""
    t = SequenceTransport((200, b"IMG"))
    c = ApiClient("https://app.famly.co", token="TT", transport=t)
    c.download("https://cdn.example.com/a.jpg")
    assert "x-famly-accesstoken" not in t.calls[0]["headers"]


def test_download_error_raises_apierror():
    t = SequenceTransport((403, b"denied"))
    c = ApiClient("https://app.famly.co", token="TT", transport=t)
    with pytest.raises(ApiError):
        c.download("https://img.famly.co/a.jpg")


def test_download_401_raises_autherror():
    t = SequenceTransport((401, b""))
    c = ApiClient("https://app.famly.co", token="TT", transport=t)
    with pytest.raises(AuthError):
        c.download("https://img.famly.co/a.jpg")


def test_download_rejects_non_https_urls():
    """Media URLs are server-supplied. A file://, ftp:// or data:// URL must not
    be opened as a local-file read, and http:// must be refused so the access
    token is never sent in cleartext (even to a matching Famly host)."""
    calls = []

    def transport(method, url, headers, body):
        calls.append(url)
        return 200, b"SECRET"

    c = ApiClient("https://app.famly.co", token="TT", transport=transport)
    for bad in ("file:///etc/passwd", "ftp://host/x",
                "data:text/plain,hi", "http://app.famly.co/image/H/1x1/a.jpg"):
        with pytest.raises(ApiError):
            c.download(bad)
    assert calls == []  # transport is never reached for a rejected scheme
