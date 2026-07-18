import json

import pytest

from famly.output import to_jsonable
from famly.models import Child, FeedItem
from famly.client import AuthError


def test_to_jsonable_converts_dataclasses_recursively():
    obj = [FeedItem("f1", "2026-01-01", "Room", "hi"), Child("c1", "Robin")]
    out = to_jsonable(obj)
    assert out[0]["id"] == "f1" and out[0]["images"] == []
    assert out[1]["name"] == "Robin"
    assert to_jsonable({"plain": 1}) == {"plain": 1}


def test_child_slug_plain_empty_and_collision():
    from famly.export import child_slug
    taken = set()
    assert child_slug("Robin Rose", "abcdef123456", taken) == "robin-rose"
    taken.add("robin-rose")
    assert child_slug("Robin Rose!", "fedcba654321", taken) == "robin-rose-fedcba65"
    assert child_slug("", "abcdef123456", set()) == "abcdef12"


def test_child_slug_sanitises_traversal_in_id():
    """When the name is empty the slug falls back to the server-supplied id,
    which must be filtered so a hostile id can't become a traversal path."""
    from famly.export import child_slug
    slug = child_slug("", "../../etc", set())
    assert "/" not in slug and ".." not in slug
    assert slug == "etc"


def test_write_json_creates_parents_and_serialises_dataclasses(tmp_path):
    from famly.export import _write_json
    _write_json(tmp_path / "data" / "children.json", [Child("c1", "Robin")])
    data = json.loads((tmp_path / "data" / "children.json").read_text())
    assert data[0]["name"] == "Robin"


def test_try_returns_sentinel_on_failure_and_reraises_auth(capsys):
    from famly.export import _try, _FAILED
    assert _try("feed", lambda: [1, 2]) == [1, 2]
    assert _try("feed", lambda: (_ for _ in ()).throw(RuntimeError("boom"))) is _FAILED
    assert "feed" in capsys.readouterr().err
    with pytest.raises(AuthError):
        _try("feed", lambda: (_ for _ in ()).throw(AuthError("unauthorized")))


from pathlib import Path

from famly.models import Conversation, Event, MediaRef, Message, Note, Observation
from famly import export as export_mod
from famly import photos as photos_mod


def _img(mid, source, ref=""):
    return MediaRef(id=mid, url=f"https://img.famly.co/{mid}.jpg", kind="image",
                    source=source, date="2026-06-01T00:00:00Z", ref_id=ref)


def _fake_download(client, ref, d, i):
    p = Path(d, ref.filename(i))
    p.write_text("x")
    return p


def _stub_export_sources(monkeypatch, **overrides):
    defaults = {
        "fetch_feed": lambda c: [],
        "fetch_conversations": lambda c, include_archived=True: [],
        "fetch_observations": lambda c, cid: [],
        "fetch_notes": lambda c, cid: [],
        "fetch_events": lambda c, cid, frm, to: [],
        "fetch_tagged": lambda c, cid: [],
        "fetch_profile": lambda c, cid: None,
    }
    for name, fn in {**defaults, **overrides}.items():
        monkeypatch.setattr(export_mod, name, fn)
    monkeypatch.setattr(photos_mod, "download", _fake_download)


def test_export_all_writes_layout_media_and_summary(tmp_path, monkeypatch):
    feed = [FeedItem("f1", "2026-06-01T00:00:00Z", "Room", "hi", images=[_img("i-feed", "feed", "f1")])]
    convos = [Conversation("c1", "Room", ["Alex"], False,
                           messages=[Message("m1", "2026-06-02T00:00:00Z", "Alex", "hello",
                                             images=[_img("i-msg", "message", "c1")])])]
    obs = [Observation("o1", "REGULAR_OBSERVATION", "2026-06-03T00:00:00Z", "L", "cap",
                       images=[_img("i-obs", "observation", "o1")])]
    notes = [Note("n1", "2026-06-04T00:00:00Z", "L", "note", images=[_img("i-note", "note", "n1")])]
    events = [Event("e1", "Sports Day", "2026-07-01", "2026-07-01")]
    windows = {}

    def fake_events(c, cid, frm, to):
        windows.update(frm=frm, to=to)
        return events

    _stub_export_sources(monkeypatch, fetch_feed=lambda c: feed,
                         fetch_conversations=lambda c, include_archived=True: convos,
                         fetch_observations=lambda c, cid: obs,
                         fetch_notes=lambda c, cid: notes,
                         fetch_events=fake_events,
                         fetch_tagged=lambda c, cid: [_img("i-tag", "tagged")],
                         fetch_profile=lambda c, cid: _img("i-prof", "profile"))
    summary = export_mod.export_all(object(), tmp_path, [Child("child-1", "Robin")],
                                    events_from="2023-07-03", events_to="2027-07-03", quiet=True)
    data = tmp_path / "data"
    assert json.loads((data / "children.json").read_text())[0]["name"] == "Robin"
    assert json.loads((data / "feed.json").read_text())[0]["id"] == "f1"
    assert json.loads((data / "messages.json").read_text())[0]["messages"][0]["body"] == "hello"
    assert json.loads((data / "robin" / "observations.json").read_text())[0]["id"] == "o1"
    assert json.loads((data / "robin" / "notes.json").read_text())[0]["id"] == "n1"
    assert json.loads((data / "robin" / "events.json").read_text())[0]["title"] == "Sports Day"
    assert windows == {"frm": "2023-07-03", "to": "2027-07-03"}
    manifest = json.loads((tmp_path / "photos" / "_manifest.json").read_text())
    assert {r["id"] for r in manifest} == {"i-feed", "i-msg", "i-obs", "i-note", "i-tag", "i-prof"}
    assert (tmp_path / "photos" / "gallery.html").exists()
    assert summary == {"out_dir": str(tmp_path), "children": 1, "feed_items": 1,
                       "conversations": 1, "observations": 1, "notes": 1, "events": 1,
                       "photos": {"downloaded": 6, "failed": 0, "total_refs": 6}}


def test_export_all_dedupes_shared_media_across_children(tmp_path, monkeypatch):
    shared = _img("i-shared", "tagged")  # same photo tagged for both siblings
    _stub_export_sources(monkeypatch, fetch_tagged=lambda c, cid: [shared])
    kids = [Child("child-1", "Robin"), Child("child-2", "Sam")]
    summary = export_mod.export_all(object(), tmp_path, kids,
                                    events_from="2023-07-03", events_to="2027-07-03", quiet=True)
    assert summary["children"] == 2
    assert summary["photos"] == {"downloaded": 1, "failed": 0, "total_refs": 1}
    assert (tmp_path / "data" / "robin" / "observations.json").exists()
    assert (tmp_path / "data" / "sam" / "observations.json").exists()


def test_export_rerun_skips_existing_media_and_rewrites_json(tmp_path, monkeypatch):
    calls = []

    def counting_download(client, ref, d, i):
        calls.append(ref.id)
        return _fake_download(client, ref, d, i)

    _stub_export_sources(monkeypatch, fetch_tagged=lambda c, cid: [_img("i-1", "tagged")])
    monkeypatch.setattr(photos_mod, "download", counting_download)
    kids = [Child("child-1", "Robin")]
    export_mod.export_all(object(), tmp_path, kids, events_from="a", events_to="b", quiet=True)
    (tmp_path / "data" / "feed.json").write_text('"stale"')
    summary2 = export_mod.export_all(object(), tmp_path, kids, events_from="a", events_to="b", quiet=True)
    assert calls == ["i-1"]  # second run downloaded nothing
    assert summary2["photos"] == {"downloaded": 0, "failed": 0, "total_refs": 1}
    assert json.loads((tmp_path / "data" / "feed.json").read_text()) == []  # re-fetched and rewritten


def test_export_failed_source_preserves_previous_json(tmp_path, monkeypatch, capsys):
    _stub_export_sources(monkeypatch, fetch_feed=lambda c: [FeedItem("f1", "2026-06-01", "R", "hi")])
    kids = [Child("child-1", "Robin")]
    export_mod.export_all(object(), tmp_path, kids, events_from="a", events_to="b", quiet=True)

    def broken_feed(c):
        raise RuntimeError("500 boom")

    _stub_export_sources(monkeypatch, fetch_feed=broken_feed)
    summary = export_mod.export_all(object(), tmp_path, kids, events_from="a", events_to="b", quiet=True)
    assert "feed" in capsys.readouterr().err
    assert summary["feed_items"] == 0
    # the previous run's good copy is untouched
    assert json.loads((tmp_path / "data" / "feed.json").read_text())[0]["id"] == "f1"


def test_export_auth_error_propagates(tmp_path, monkeypatch):
    def unauthorized(c):
        raise AuthError("unauthorized")

    _stub_export_sources(monkeypatch, fetch_feed=unauthorized)
    with pytest.raises(AuthError):
        export_mod.export_all(object(), tmp_path, [Child("child-1", "Robin")],
                              events_from="a", events_to="b", quiet=True)


def test_export_same_name_children_get_distinct_folders(tmp_path, monkeypatch):
    _stub_export_sources(monkeypatch)
    kids = [Child("abcdef123456", "Robin"), Child("fedcba654321", "Robin")]
    export_mod.export_all(object(), tmp_path, kids,
                          events_from="a", events_to="b", quiet=True)
    assert (tmp_path / "data" / "robin" / "observations.json").exists()
    assert (tmp_path / "data" / "robin-fedcba65" / "observations.json").exists()


def test_export_child_subset_preserves_account_children_and_slugs(tmp_path, monkeypatch):
    """A --child run must not rewrite children.json down to one child, nor
    reassign a same-named sibling's folder slug (silent cross-child mislabeling)."""
    _stub_export_sources(monkeypatch)
    robin1 = Child("abcdef123456", "Robin")
    robin2 = Child("fedcba654321", "Robin")
    export_mod.export_all(object(), tmp_path, [robin2], all_children=[robin1, robin2],
                          events_from="a", events_to="b", quiet=True)
    kids = json.loads((tmp_path / "data" / "children.json").read_text())
    assert [k["id"] for k in kids] == ["abcdef123456", "fedcba654321"]
    assert (tmp_path / "data" / "robin-fedcba65" / "observations.json").exists()
    assert not (tmp_path / "data" / "robin" / "observations.json").exists()
