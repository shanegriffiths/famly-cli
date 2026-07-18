import json
from famly.sources.feed import fetch_feed
from famly.client import ApiClient
from tests.conftest import FakeTransport

def test_feed_paginates_via_olderthan_and_builds_fullres():
    pages = [
        {"feedItems": [{"feedItemId": "f1", "createdDate": "2026-02-10T16:00:00+00:00",
                        "sender": {"title": "Alex"}, "body": "Pancake day",
                        "images": [{"imageId": "i1", "prefix": "https://img.famly.co/image/H",
                                    "key": "a.jpg?expires=Z", "width": 1920, "height": 2560,
                                    "url": "https://img.famly.co/image/H/600x800/a.jpg?expires=Z"}],
                        "videos": [], "files": [], "comments": [], "embed": {}}]},
        {"feedItems": []},
    ]
    t = FakeTransport()
    state = {"n": 0}
    def transport(method, url, headers, body):
        p = pages[min(state["n"], len(pages) - 1)]; state["n"] += 1
        return 200, json.dumps(p).encode()
    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    items = fetch_feed(c)
    assert len(items) == 1
    assert items[0].images[0].url == "https://img.famly.co/image/H/1920x2560/a.jpg?expires=Z"

def test_feed_dedupes_across_pages():
    """Test that items are deduplicated across multiple pages."""
    pages = [
        {"feedItems": [
            {"feedItemId": "f10", "createdDate": "2026-06-10T12:00:00+00:00",
             "sender": {"title": "Alice"}, "body": "Item 10",
             "images": [], "videos": [], "files": [], "embed": {}},
            {"feedItemId": "f9", "createdDate": "2026-06-09T12:00:00+00:00",
             "sender": {"title": "Alice"}, "body": "Item 9",
             "images": [], "videos": [], "files": [], "embed": {}},
        ]},
        {"feedItems": [
            {"feedItemId": "f9", "createdDate": "2026-06-09T12:00:00+00:00",
             "sender": {"title": "Alice"}, "body": "Item 9 (dup)",
             "images": [], "videos": [], "files": [], "embed": {}},
            {"feedItemId": "f8", "createdDate": "2026-06-08T12:00:00+00:00",
             "sender": {"title": "Alice"}, "body": "Item 8",
             "images": [], "videos": [], "files": [], "embed": {}},
        ]},
        {"feedItems": []},
    ]
    state = {"n": 0}
    def transport(method, url, headers, body):
        p = pages[min(state["n"], len(pages) - 1)]; state["n"] += 1
        return 200, json.dumps(p).encode()
    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    items = fetch_feed(c)
    assert len(items) == 3
    assert [item.id for item in items] == ["f10", "f9", "f8"]

def test_feed_terminates_on_stuck_cursor():
    """Test that fetch_feed terminates when olderThan stops changing (no progress)."""
    stuck_page = {"feedItems": [
        {"feedItemId": "f1", "createdDate": "2026-06-05T12:00:00+00:00",
         "sender": {"title": "Bob"}, "body": "Stuck 1",
         "images": [], "videos": [], "files": [], "embed": {}},
        {"feedItemId": "f2", "createdDate": "2026-06-04T12:00:00+00:00",
         "sender": {"title": "Bob"}, "body": "Stuck 2",
         "images": [], "videos": [], "files": [], "embed": {}},
    ]}
    call_count = {"n": 0}
    def transport(method, url, headers, body):
        call_count["n"] += 1
        return 200, json.dumps(stuck_page).encode()
    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    items = fetch_feed(c)
    assert len(items) == 2
    assert [item.id for item in items] == ["f1", "f2"]
    # Verify it only made 2 calls (page1 + page2 where olderThan is same as page1's last item)
    assert call_count["n"] == 2

def _item(fid, date, body="x"):
    return {"feedItemId": fid, "createdDate": date, "sender": {"title": "Charlie"},
            "body": body, "images": [], "videos": [], "files": [], "embed": {}}


def test_feed_since_keeps_newer_items_and_stops():
    """Items older than 'since' are excluded, and pagination stops once a whole
    page predates 'since' (older pages can only be older still)."""
    pages = [
        {"feedItems": [_item("f20", "2026-06-20T12:00:00+00:00"),
                       _item("f19", "2026-06-19T12:00:00+00:00")]},
        {"feedItems": [_item("f01", "2026-01-01T12:00:00+00:00"),
                       _item("f02", "2026-01-02T12:00:00+00:00")]},
        {"feedItems": [_item("f00", "2025-12-01T12:00:00+00:00")]},  # never reached
    ]
    call_count = {"n": 0}
    def transport(method, url, headers, body):
        call_count["n"] += 1
        p = pages[min(call_count["n"] - 1, len(pages) - 1)]
        return 200, json.dumps(p).encode()
    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    items = fetch_feed(c, since="2026-06-01T00:00:00+00:00")
    assert [item.id for item in items] == ["f20", "f19"]
    assert call_count["n"] == 2  # stopped after the first all-old page


def test_feed_since_skips_pinned_old_post_without_dropping_newer_items():
    """A pinned months-old post appearing first must not truncate the whole
    feed to nothing — items after it in the page are still newer than since."""
    pages = [
        {"feedItems": [_item("pin", "2025-01-01T12:00:00+00:00", "pinned notice"),
                       _item("new", "2026-06-20T12:00:00+00:00", "fresh photo post")]},
        {"feedItems": []},
    ]
    state = {"n": 0}
    def transport(method, url, headers, body):
        p = pages[min(state["n"], len(pages) - 1)]; state["n"] += 1
        return 200, json.dumps(p).encode()
    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    items = fetch_feed(c, since="2026-06-01T00:00:00+00:00")
    assert [item.id for item in items] == ["new"]

def test_feed_excludes_urlless_video_keeps_file_and_embed():
    """Test that videos without URLs are filtered out, but files and embeds are kept."""
    pages = [
        {"feedItems": [
            {"feedItemId": "f_mixed", "createdDate": "2026-06-15T12:00:00+00:00",
             "sender": {"title": "Dave"}, "body": "Mixed media",
             "images": [],
             "videos": [
                 {"videoId": "v1", "videoUrl": "https://v.famly.co/1.mp4"},
                 {"videoId": "v2"},  # No URL, should be filtered
             ],
             "files": [
                 {"fileId": "fA", "url": "https://files.famly.co/a.pdf"},
             ],
             "embed": {"observationId": "obs-9"}},
        ]},
        {"feedItems": []},
    ]
    state = {"n": 0}
    def transport(method, url, headers, body):
        p = pages[min(state["n"], len(pages) - 1)]; state["n"] += 1
        return 200, json.dumps(p).encode()
    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    items = fetch_feed(c)
    assert len(items) == 1
    assert items[0].id == "f_mixed"
    assert len(items[0].videos) == 1
    assert items[0].videos[0].id == "v1"
    assert items[0].videos[0].url == "https://v.famly.co/1.mp4"
    assert len(items[0].files) == 1
    assert items[0].files[0].id == "fA"
    assert items[0].files[0].url == "https://files.famly.co/a.pdf"
    assert items[0].embed_observation_id == "obs-9"
