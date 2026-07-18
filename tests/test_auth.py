import pytest
from pathlib import Path
from famly.client import ApiClient, ApiError
from famly.auth import login, TokenStore, authenticated_client
from famly.config import Credentials
from tests.conftest import FakeTransport

def test_login_extracts_access_token():
    t = FakeTransport()
    t.add("/graphql?Authenticate", {"data": {"me": {"authenticateWithPassword": {"accessToken": "AT123"}}}})
    c = ApiClient("https://app.famly.co", transport=t)
    assert login(c, "a@b.com", "pw", "dev-1") == "AT123"
    assert t.calls[0]["body"]["variables"]["deviceId"] == "dev-1"

def test_token_store_roundtrip(tmp_path):
    s = TokenStore(tmp_path); assert s.load() is None
    s.save("TOK"); assert s.load() == "TOK"
    assert (tmp_path / "token.json").stat().st_mode & 0o777 == 0o600

def test_authenticated_client_uses_cached_token(tmp_path):
    TokenStore(tmp_path).save("CACHED")
    t = FakeTransport()
    c = authenticated_client("https://app.famly.co", Credentials(email="a", password="b"),
                             config_dir=tmp_path, transport=t, device_id="d")
    assert c.token == "CACHED"  # no login call made
    assert t.calls == []

def test_authenticated_client_force_bypasses_cache(tmp_path):
    TokenStore(tmp_path).save("CACHED")
    t = FakeTransport()
    t.add("/graphql?Authenticate", {"data": {"me": {"authenticateWithPassword": {"accessToken": "NEW"}}}})
    c = authenticated_client("https://app.famly.co", Credentials(email="a", password="b"),
                             config_dir=tmp_path, transport=t, device_id="d", force=True)
    assert c.token == "NEW"  # login ran, cache bypassed
    assert TokenStore(tmp_path).load() == "NEW"  # new token persisted
    assert t.calls  # a login call was made


def test_authenticated_client_prefers_access_token_over_cache(tmp_path):
    TokenStore(tmp_path).save("CACHED")
    t = FakeTransport()
    c = authenticated_client("https://app.famly.co", Credentials(access_token="DIRECT"),
                             config_dir=tmp_path, transport=t, device_id="d")
    assert c.token == "DIRECT"
    assert t.calls == []  # no transport calls made

def test_authenticated_client_logs_in_and_persists(tmp_path):
    t = FakeTransport()
    t.add("/graphql?Authenticate", {"data": {"me": {"authenticateWithPassword": {"accessToken": "NEW"}}}})
    c = authenticated_client("https://app.famly.co", Credentials(email="a", password="b"),
                             config_dir=tmp_path, transport=t, device_id="d")
    assert c.token == "NEW"
    assert TokenStore(tmp_path).load() == "NEW"


def test_token_store_records_email(tmp_path):
    s = TokenStore(tmp_path)
    s.save("TOK", email="a@b.com")
    assert s.load() == "TOK"
    assert s.load_record()["email"] == "a@b.com"


def test_token_store_load_record_tolerates_legacy_and_corrupt_files(tmp_path):
    s = TokenStore(tmp_path)
    assert s.load_record() == {}
    (tmp_path / "token.json").write_text("not json")
    assert s.load_record() == {}
    (tmp_path / "token.json").write_text('{"access_token": "OLD"}')  # legacy: no email
    assert s.load() == "OLD" and "email" not in s.load_record()


def test_authenticated_client_persists_email_with_token(tmp_path):
    """The cache must record which account the token belongs to, so later runs
    with different explicit credentials can detect the mismatch."""
    t = FakeTransport()
    t.add("/graphql?Authenticate", {"data": {"me": {"authenticateWithPassword": {"accessToken": "NEW"}}}})
    authenticated_client("https://app.famly.co", Credentials(email="a@b.com", password="pw"),
                         config_dir=tmp_path, transport=t, device_id="d")
    assert TokenStore(tmp_path).load_record()["email"] == "a@b.com"


# --- Authenticate returns a union (AuthenticationResult); regression guards for
# --- the live-schema shape that the original hand-written query got wrong. ---

def test_login_success_from_union():
    t = FakeTransport()
    t.add("/graphql?Authenticate", {"data": {"me": {"authenticateWithPassword": {
        "__typename": "AuthenticationSucceeded", "status": "Succeeded",
        "accessToken": "TOK", "deviceId": "d"}}}})
    c = ApiClient("https://app.famly.co", transport=t)
    assert login(c, "a@b.com", "pw", "d") == "TOK"

def test_login_failed_raises_clean_error():
    t = FakeTransport()
    t.add("/graphql?Authenticate", {"data": {"me": {"authenticateWithPassword": {
        "__typename": "AuthenticationFailed", "status": "Failed",
        "errorTitle": "Invalid password", "errorDetails": "did not match"}}}})
    c = ApiClient("https://app.famly.co", transport=t)
    with pytest.raises(ApiError) as e:
        login(c, "a@b.com", "wrong", "d")
    assert "Invalid password" in str(e.value)

def test_login_two_factor_raises():
    t = FakeTransport()
    t.add("/graphql?Authenticate", {"data": {"me": {"authenticateWithPassword": {
        "__typename": "AuthenticationChallenged", "loginId": "abc", "status": "Challenged"}}}})
    c = ApiClient("https://app.famly.co", transport=t)
    with pytest.raises(ApiError) as e:
        login(c, "a@b.com", "pw", "d")
    assert "two-factor" in str(e.value).lower()
