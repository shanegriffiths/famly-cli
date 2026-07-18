import json

from famly.sources.profile import profile_full_res, fetch_profile
from famly.sources.children import fetch_children
from famly.sources.events import fetch_events
from famly.sources.notes import fetch_notes
from famly.sources.tagged import fetch_tagged
from famly.client import ApiClient
from tests.conftest import FakeTransport, load_fixture

def test_profile_full_res_crop_face_first():
    url = "https://img.famly.co/image/H/100x100/a.jpg?crop=face&expires=Z"
    out = profile_full_res(url)
    assert "/1600x1600/" in out
    assert "crop" not in out
    assert out.count("?") == 1
    assert "expires=Z" in out

def test_profile_full_res_drops_crop_and_upsizes():
    url = "https://img.famly.co/image/H/100x100/a.jpg?expires=Z&crop=face"
    out = profile_full_res(url)
    assert "/1600x1600/" in out
    assert "crop" not in out
    assert out.count("?") == 1
    assert "expires=Z" in out

def test_fetch_children_from_me():
    me = load_fixture("me.json")
    t = FakeTransport(); t.add("/api/me/me/me", me)
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    kids = fetch_children(c)
    assert len(kids) == 1  # the non-child Institution role is filtered out
    assert kids[0].name == "Test Child" and kids[0].id == "child-1"
    assert kids[0].institution == "Test Nursery"

def test_fetch_profile_from_role_image():
    me = {"roles2": [{"targetId": "child-1", "targetType": "Famly.Daycare:Child",
                      "image": "https://img.famly.co/image/H/100x100/a.jpg?expires=Z&crop=face"}]}
    t = FakeTransport(); t.add("/api/me/me/me", me)
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    ref = fetch_profile(c, "child-1")
    assert ref is not None and ref.source == "profile"
    assert "/1600x1600/" in ref.url and "crop" not in ref.url

def test_fetch_events_range():
    # /api/v2/calendar returns [ {period, days:[ {day, events:[...]} ]} ]
    t = FakeTransport()
    t.add("/api/v2/calendar", [{"period": {"from": "2026-07-01"}, "days": [
        {"day": "2026-07-10T00:00:00+00:00", "events": [
            {"originator": {"type": "Famly.Daycare:Event", "id": "e1"},
             "title": "Sports Day",
             "from": "2026-07-10T09:00:00+00:00", "to": "2026-07-10T12:00:00+00:00"}]}]}])
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    evs = fetch_events(c, "child-1", "2026-07-01", "2026-07-31")
    assert len(evs) == 1
    assert evs[0].title == "Sports Day"
    assert evs[0].id == "e1"
    assert evs[0].start == "2026-07-10T09:00:00+00:00"
    assert evs[0].end == "2026-07-10T12:00:00+00:00"

def test_fetch_events_empty_days():
    t = FakeTransport()
    t.add("/api/v2/calendar", [{"period": {"from": "2026-07-01"}, "days": [
        {"day": "2026-07-10T00:00:00+00:00", "events": []}]}])
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    assert fetch_events(c, "child-1", "2026-07-01", "2026-07-31") == []

def test_notes_images_are_full_res():
    page = {"data": {"childNotes": {
        "next": None,
        "result": [{"id": "n1", "createdAt": "2026-06-25T13:00:00Z",
                    "createdBy": {"name": {"fullName": "Alex"}}, "body": "Great nap today",
                    "images": [{"id": "img1", "width": 1920, "height": 2560,
                                "url": "https://img.famly.co/image/H/1080x1920/a.jpg?expires=Z"}]}]}}}
    t = FakeTransport()
    t.routes.append(("/graphql?GetChildNotes", 200, json.dumps(page).encode()))
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    notes = fetch_notes(c, "child-1")
    assert len(notes) == 1
    assert notes[0].images[0].url == "https://img.famly.co/image/H/1920x2560/a.jpg?expires=Z"

def test_notes_paginates_two_pages():
    page1 = {"data": {"childNotes": {
        "next": "CUR",
        "result": [{"id": "n1", "createdAt": "2026-06-01T00:00:00Z",
                    "createdBy": {"name": {"fullName": "T"}}, "body": "x", "images": []}]}}}
    page2 = {"data": {"childNotes": {
        "next": None,
        "result": [{"id": "n2", "createdAt": "2026-06-02T00:00:00Z",
                    "createdBy": {"name": {"fullName": "T"}}, "body": "y", "images": []}]}}}

    class PaginatedTransport(FakeTransport):
        def __init__(self):
            super().__init__()
            self.call_count = 0

        def __call__(self, method, url, headers, body):
            self.calls.append({
                "method": method,
                "url": url,
                "headers": headers,
                "body": json.loads(body) if body else None
            })
            if "/graphql?GetChildNotes" in url:
                self.call_count += 1
                if self.call_count == 1:
                    return 200, json.dumps(page1).encode()
                else:
                    body_obj = json.loads(body)
                    assert body_obj.get("variables", {}).get("cursor") == "CUR"
                    return 200, json.dumps(page2).encode()
            return 404, b'{"error":"no route"}'

    t = PaginatedTransport()
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    notes = fetch_notes(c, "child-1")
    assert len(notes) == 2
    assert notes[0].id == "n1"
    assert notes[1].id == "n2"

def test_fetch_tagged_empty_list():
    t = FakeTransport()
    t.add("/api/v2/images/tagged", [])
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    assert fetch_tagged(c, "child-1") == []

def test_fetch_tagged_images_are_full_res():
    t = FakeTransport()
    t.add("/api/v2/images/tagged", [{"id": "tag1", "width": 1920, "height": 2560,
            "url": "https://img.famly.co/image/H/1080x1920/b.jpg?expires=Z"}])
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    tagged = fetch_tagged(c, "child-1")
    assert tagged[0].url == "https://img.famly.co/image/H/1920x2560/b.jpg?expires=Z"


def _tagged_row(n, day):
    return {"imageId": f"i{n}", "width": 1, "height": 1,
            "url": f"https://img.famly.co/image/H/1x1/{n}.jpg",
            "createdAt": f"2026-06-{day:02d}T12:00:00+00:00"}


def test_fetch_tagged_paginates_past_first_page():
    """A child with more than 100 tagged photos must get all of them, not a
    silently truncated first page."""
    page1 = [_tagged_row(n, 28 - n // 5) for n in range(100)]
    page2 = [_tagged_row(100 + n, 2) for n in range(5)]

    def transport(method, url, headers, body):
        return 200, json.dumps(page2 if "olderThan" in url else page1).encode()

    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    tagged = fetch_tagged(c, "child-1")
    assert len(tagged) == 105
    assert len({r.id for r in tagged}) == 105


def test_fetch_tagged_terminates_if_api_ignores_pagination():
    """If the endpoint ignores the cursor and repeats page 1 forever, the loop
    must stop without duplicating items."""
    page1 = [_tagged_row(n, 20) for n in range(100)]
    calls = []

    def transport(method, url, headers, body):
        calls.append(url)
        return 200, json.dumps(page1).encode()

    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    tagged = fetch_tagged(c, "child-1")
    assert len(tagged) == 100
    assert len(calls) <= 2


def test_get_child_notes_query_selects_note_id():
    """notes.py keys Note.id and the manifest ref on the note's id — the live
    API only returns fields the query selects, and the live ChildNote type
    names it `noteId` (verified by introspection; plain `id` fails query
    validation)."""
    import re
    from famly.auth import _query
    q = _query("GetChildNotes")
    result_block = q.split("result {", 1)[1]
    assert re.search(r"\bnoteId\b", result_block.split("{")[0]), \
        "GetChildNotes must select the note-level noteId field"


def test_notes_reads_note_id_from_live_shape():
    page = {"data": {"childNotes": {
        "next": None,
        "result": [{"noteId": "n-live-1", "createdAt": "2026-06-25T13:00:00Z",
                    "createdBy": {"name": {"fullName": "Alex"}}, "text": "nap",
                    "images": [{"id": "img1", "width": 10, "height": 10,
                                "url": "https://img.famly.co/image/H/10x10/a.jpg"}]}]}}}
    t = FakeTransport()
    t.routes.append(("/graphql?GetChildNotes", 200, json.dumps(page).encode()))
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    notes = fetch_notes(c, "child-1")
    assert notes[0].id == "n-live-1"
    assert notes[0].images[0].ref_id == "n-live-1"
