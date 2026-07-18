from pathlib import Path
from famly.models import MediaRef
from famly.media import dedupe, download, load_manifest, write_manifest
from famly.client import ApiClient

def test_dedupe_by_id():
    a = MediaRef(id="x", url="u", kind="image"); b = MediaRef(id="x", url="u2", kind="image")
    assert len(dedupe([a, b])) == 1

def test_dedupe_keeps_refs_without_ids():
    """Refs with a missing/empty id can't be deduped, but must never be dropped."""
    a = MediaRef(id="", url="u1", kind="image"); b = MediaRef(id=None, url="u2", kind="image")
    c = MediaRef(id="x", url="u3", kind="image")
    assert [r.url for r in dedupe([a, b, c])] == ["u1", "u2", "u3"]

def test_download_sends_auth_header_for_famly_urls(tmp_path):
    """Media downloads go through the client's authenticated path — file refs
    served by app.famly.co need the x-famly-accesstoken header."""
    seen = {}
    def transport(method, url, headers, body):
        seen.update(headers=headers, url=url)
        return 200, b"DATA"
    c = ApiClient("https://app.famly.co", token="TT", transport=transport)
    ref = MediaRef(id="abcd1234ffff", url="https://app.famly.co/api/v2/files/f1", kind="file",
                   source="message", date="2026-01-01T00:00:00Z")
    download(c, ref, tmp_path, 1)
    assert seen["headers"].get("x-famly-accesstoken") == "TT"

def test_download_writes_bytes(tmp_path):
    def transport(method, url, headers, body): return 200, b"JPEGDATA"
    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    ref = MediaRef(id="abcd1234ffff", url="https://img/x.jpg", kind="image", source="feed",
                   date="2026-01-01T00:00:00Z")
    p = download(c, ref, tmp_path, 1)
    assert p.exists() and p.read_bytes() == b"JPEGDATA"
    assert p.name == "2026-01-01_01_feed_abcd1234.jpg"

def test_download_sanitises_traversal_in_api_date(tmp_path):
    """A hostile server-supplied date must not escape the output dir via the
    generated filename — path separators and dots are stripped, and a date that
    reduces to nothing collapses to 'unknown'."""
    def transport(method, url, headers, body): return 200, b"X"
    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    for bad_date in ("../../../../etc/cron.d/evil", "/tmp/pwned", "..%2f..%2fx"):
        ref = MediaRef(id="abcd1234", url="https://img.famly.co/x.jpg", kind="image",
                       source="feed", date=bad_date)
        p = download(c, ref, tmp_path, 1)
        assert p.parent == tmp_path                       # stayed inside out_dir
        assert ".." not in p.name and "/" not in p.name
    # A date made entirely of path characters leaves nothing usable -> "unknown".
    ref = MediaRef(id="abcd1234", url="https://img.famly.co/x.jpg", kind="image",
                   source="feed", date="/tmp/pwned")
    assert download(c, ref, tmp_path, 1).name.startswith("unknown_")

def test_manifest_roundtrip(tmp_path):
    write_manifest(tmp_path, [{"file": "a.jpg", "id": "x"}])
    assert load_manifest(tmp_path)[0]["id"] == "x"
