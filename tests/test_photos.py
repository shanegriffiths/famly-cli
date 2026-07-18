import json
from pathlib import Path

import pytest

from famly.client import AuthError
from famly.models import Child, Observation, FeedItem, MediaRef
from famly import photos


def _stub_sources(monkeypatch, **overrides):
    """Stub every photo source to empty unless overridden."""
    defaults = {
        "fetch_observations": lambda c, cid: [],
        "fetch_feed": lambda c, since=None: [],
        "fetch_conversations": lambda c, include_archived=True: [],
        "fetch_notes": lambda c, cid: [],
        "fetch_tagged": lambda c, cid: [],
        "fetch_profile": lambda c, cid: None,
    }
    for name, fn in {**defaults, **overrides}.items():
        monkeypatch.setattr(photos, name, fn)


def _fake_download(client, ref, d, i):
    path = Path(d, ref.filename(i))
    path.write_text("x")
    return path


def _run(tmp_path, **kwargs):
    args = dict(sources=photos.ALL_SOURCES, since=None, incremental=False,
                include_videos=False, include_files=False, make_gallery=False, quiet=True)
    args.update(kwargs)
    return photos.download_all(object(), Child("child-1", "Robin"), tmp_path, **args)


def test_download_all_dedupes_and_writes_manifest(tmp_path, monkeypatch):
    img = MediaRef(id="dup", url="https://img/x.jpg", kind="image", source="observation", date="2026-01-01T00:00:00Z")
    img_feed = MediaRef(id="dup", url="https://img/x.jpg", kind="image", source="feed", date="2026-01-01T00:00:00Z")
    monkeypatch.setattr(photos, "fetch_observations", lambda c, cid: [Observation("o1", "REGULAR_OBSERVATION", "2026-01-01T00:00:00Z", "L", "cap", [img], [], [], [])])
    monkeypatch.setattr(photos, "fetch_feed", lambda c, since=None: [FeedItem("f1", "2026-01-01T00:00:00Z", "S", "b", [img_feed], [], [], None)])
    for name in ["fetch_conversations", "fetch_notes", "fetch_tagged", "fetch_profile"]:
        monkeypatch.setattr(photos, name, (lambda *a, **k: []) if name != "fetch_profile" else (lambda *a, **k: None))
    def _fake_download(client, ref, d, i):
        path = Path(d, ref.filename(i))
        path.write_text("x")
        return path

    monkeypatch.setattr(photos, "download", _fake_download)
    summary = photos.download_all(object(), Child("child-1", "Robin"), tmp_path,
                                  sources=["observations", "feed"], since=None, incremental=False,
                                  include_videos=False, include_files=False, make_gallery=False)
    assert summary["downloaded"] == 1
    assert (tmp_path / "_manifest.json").exists()


def test_auth_error_in_source_fetch_propagates(tmp_path, monkeypatch):
    """An expired token must abort the run, not degrade into a 'successful'
    empty archive that an agent would take at face value."""
    def _boom(c, cid):
        raise AuthError("unauthorized")

    _stub_sources(monkeypatch, fetch_observations=_boom)
    monkeypatch.setattr(photos, "download", _fake_download)
    with pytest.raises(AuthError):
        _run(tmp_path)


def test_auth_error_from_profile_source_propagates(tmp_path, monkeypatch):
    def _boom(c, cid):
        raise AuthError("unauthorized")

    _stub_sources(monkeypatch, fetch_profile=_boom)
    monkeypatch.setattr(photos, "download", _fake_download)
    with pytest.raises(AuthError):
        _run(tmp_path)


def test_download_failures_are_logged_and_counted(tmp_path, monkeypatch, capsys):
    ok = MediaRef(id="ok1", url="https://img/a.jpg", kind="image", source="tagged", date="2026-01-01T00:00:00Z")
    bad = MediaRef(id="bad1", url="https://img/b.jpg", kind="image", source="tagged", date="2026-01-02T00:00:00Z")
    _stub_sources(monkeypatch, fetch_tagged=lambda c, cid: [ok, bad])

    def _download(client, ref, d, i):
        if ref.id == "bad1":
            raise RuntimeError("403 expired url")
        return _fake_download(client, ref, d, i)

    monkeypatch.setattr(photos, "download", _download)
    summary = _run(tmp_path)
    assert summary["downloaded"] == 1
    assert summary["failed"] == 1
    err = capsys.readouterr().err
    assert "bad1" in err and "403 expired url" in err


def test_auth_error_during_download_propagates(tmp_path, monkeypatch):
    ref = MediaRef(id="r1", url="https://img/a.jpg", kind="image", source="tagged", date="2026-01-01T00:00:00Z")
    _stub_sources(monkeypatch, fetch_tagged=lambda c, cid: [ref])

    def _download(client, ref, d, i):
        raise AuthError("unauthorized")

    monkeypatch.setattr(photos, "download", _download)
    with pytest.raises(AuthError):
        _run(tmp_path)


def test_since_keeps_undated_refs(tmp_path, monkeypatch):
    """A ref whose date didn't parse must survive --since: silently dropping it
    is data loss relative to a run without --since."""
    undated = MediaRef(id="u1", url="https://img/u.jpg", kind="image", source="tagged", date=None)
    _stub_sources(monkeypatch, fetch_tagged=lambda c, cid: [undated])
    monkeypatch.setattr(photos, "download", _fake_download)
    summary = _run(tmp_path, since="2026-01-01")
    assert summary["downloaded"] == 1


def test_zero_download_run_creates_out_dir_and_manifest(tmp_path, monkeypatch):
    _stub_sources(monkeypatch)
    monkeypatch.setattr(photos, "download", _fake_download)
    out = tmp_path / "fresh" / "dir"
    summary = _run(out)
    assert summary["downloaded"] == 0
    assert json.loads((out / "_manifest.json").read_text()) == []


def test_interrupt_still_writes_manifest_for_completed_items(tmp_path, monkeypatch):
    """Ctrl-C halfway through must not orphan the files already on disk — the
    next --incremental run should skip them, not redownload everything."""
    r1 = MediaRef(id="r1", url="https://img/a.jpg", kind="image", source="tagged", date="2026-01-01T00:00:00Z")
    r2 = MediaRef(id="r2", url="https://img/b.jpg", kind="image", source="tagged", date="2026-01-02T00:00:00Z")
    _stub_sources(monkeypatch, fetch_tagged=lambda c, cid: [r1, r2])

    def _download(client, ref, d, i):
        if ref.id == "r2":
            raise KeyboardInterrupt()
        return _fake_download(client, ref, d, i)

    monkeypatch.setattr(photos, "download", _download)
    with pytest.raises(KeyboardInterrupt):
        _run(tmp_path)
    recs = json.loads((tmp_path / "_manifest.json").read_text())
    assert [r["id"] for r in recs] == ["r1"]


def test_incremental_merges_new_records_in_date_order(tmp_path, monkeypatch):
    """A back-dated item arriving after an earlier run must be merged into date
    order, not appended after the newest existing record."""
    (tmp_path / "_manifest.json").write_text(json.dumps(
        [{"file": "new.jpg", "id": "new1", "source": "tagged", "date": "2026-06-01T00:00:00Z",
          "author": "", "caption": "", "w": None, "h": None, "ref": ""}]))
    backfilled = MediaRef(id="old1", url="https://img/o.jpg", kind="image",
                          source="tagged", date="2026-02-01T00:00:00Z")
    _stub_sources(monkeypatch, fetch_tagged=lambda c, cid: [backfilled])
    monkeypatch.setattr(photos, "download", _fake_download)
    _run(tmp_path, incremental=True)
    recs = json.loads((tmp_path / "_manifest.json").read_text())
    assert [r["id"] for r in recs] == ["old1", "new1"]


def test_download_refs_dedupes_downloads_and_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(photos, "download", _fake_download)
    r1 = MediaRef(id="a", url="https://img/a.jpg", kind="image", source="feed", date="2026-01-01T00:00:00Z")
    dup = MediaRef(id="a", url="https://img/a.jpg", kind="image", source="message", date="2026-01-01T00:00:00Z")
    r2 = MediaRef(id="b", url="https://img/b.jpg", kind="image", source="tagged", date="2026-01-02T00:00:00Z")
    summary = photos.download_refs(object(), [r1, dup, r2], tmp_path,
                                   incremental=False, make_gallery=False, quiet=True)
    assert summary == {"downloaded": 2, "failed": 0, "total_refs": 2, "out_dir": str(tmp_path)}
    assert (tmp_path / "_manifest.json").exists()


def test_out_dir_exists_even_when_collection_fails(tmp_path, monkeypatch):
    """Behavior-preserving guarantee from the download_refs split: the output
    directory is created before collection, so a run that dies fetching
    sources leaves the directory in place, exactly as before the refactor."""
    def _boom(c, cid):
        raise AuthError("unauthorized")

    _stub_sources(monkeypatch, fetch_observations=_boom)
    out = tmp_path / "fresh"
    with pytest.raises(AuthError):
        _run(out)
    assert out.is_dir()
