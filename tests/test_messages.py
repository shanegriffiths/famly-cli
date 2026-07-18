import json
from famly.sources.messages import fetch_conversations
from famly.client import ApiClient
from tests.conftest import FakeTransport

def test_lists_conversations_and_loads_messages():
    t = FakeTransport()
    t.add("/api/v2/conversations?limit=50&offset=0&inbox=OWN&inbox2=1&archived=false",
          {"conversations": [{"conversationId": "c1", "title": "Nursery 2", "participants": [{"title": "Nursery 2"}]}]})
    t.add("/api/v2/conversations/c1",
          {"conversationId": "c1", "title": "Nursery 2", "participants": [{"title": "Nursery 2"}],
           "cursor": None, "messages": [{"messageId": "m1", "createdAt": "2026-06-01T09:00:00Z",
                                          "author": {"title": "Alex"}, "body": "hi", "images": [], "files": []}]})
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    convos = fetch_conversations(c)
    assert convos[0].id == "c1" and convos[0].messages[0].body == "hi"

def _msg(mid, ts):
    return {"messageId": mid, "createdAt": ts, "author": {"title": "T"}, "body": "hi", "images": [], "files": []}

def test_messages_dedup_on_timestamp_tie():
    """Boundary-tie dedup: a message repeated at a page boundary (inclusive olderThan
    semantics) must only appear once in the final message list. Pages are padded to the
    50-item API page size (with repeats of already-seen ids) so pagination doesn't stop
    early on the `len(page) < 50` guard before the boundary duplicate is exercised."""
    m1 = _msg("m1", "2026-06-01T09:00:02+00:00")
    m2 = _msg("m2", "2026-06-01T09:00:01+00:00")
    m3 = _msg("m3", "2026-06-01T09:00:00+00:00")
    pages = [
        {"messages": [m1] + [m2] * 49},   # page 1: 50 items, last item ties with page 2's first
        {"messages": [m2] + [m3] * 49},   # page 2: boundary repeat of m2, then m3
        {"messages": []},                 # page 3: empty, terminates pagination
    ]
    state = {"n": 0}
    def transport(method, url, headers, body):
        if "/api/v2/conversations?" in url:
            return 200, json.dumps({"conversations": [{"conversationId": "c1", "title": "A", "participants": []}]}).encode()
        p = pages[min(state["n"], len(pages) - 1)]
        state["n"] += 1
        return 200, json.dumps(p).encode()
    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    convos = fetch_conversations(c)
    assert [m.id for m in convos[0].messages] == ["m1", "m2", "m3"]

def test_include_archived_merges_both_passes():
    def transport(method, url, headers, body):
        if "/api/v2/conversations?" in url:
            if "archived=false" in url:
                return 200, json.dumps({"conversations": [{"conversationId": "c1", "title": "A", "participants": []}]}).encode()
            return 200, json.dumps({"conversations": [{"conversationId": "c2", "title": "B", "participants": []}]}).encode()
        return 200, json.dumps({"messages": []}).encode()
    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    convos = fetch_conversations(c, include_archived=True)
    assert [x.id for x in convos] == ["c1", "c2"]

def test_bare_list_conversation_response():
    def transport(method, url, headers, body):
        if "/api/v2/conversations?" in url:
            return 200, json.dumps([{"conversationId": "c9", "title": "Z", "participants": []}]).encode()
        return 200, json.dumps({"messages": []}).encode()
    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    convos = fetch_conversations(c)
    assert len(convos) == 1 and convos[0].id == "c9"

def test_conversation_unread_derived_from_messages():
    t = FakeTransport()
    t.add("/api/v2/conversations?limit=50&offset=0&inbox=OWN&inbox2=1&archived=false",
          {"conversations": [
              {"conversationId": "c1", "title": "Nursery 2", "participants": [{"title": "Nursery 2"}]},
              {"conversationId": "c2", "title": "Nursery 3", "participants": [{"title": "Nursery 3"}]},
          ]})
    t.add("/api/v2/conversations/c1",
          {"conversationId": "c1", "title": "Nursery 2", "participants": [{"title": "Nursery 2"}],
           "cursor": None, "messages": [
               {"messageId": "m1", "createdAt": "2026-06-01T09:00:00Z",
                "author": {"title": "Alex"}, "body": "hi", "unread": False, "images": [], "files": []},
               {"messageId": "m2", "createdAt": "2026-06-01T09:01:00Z",
                "author": {"title": "Alex"}, "body": "hi again", "unread": True, "images": [], "files": []},
           ]})
    t.add("/api/v2/conversations/c2",
          {"conversationId": "c2", "title": "Nursery 3", "participants": [{"title": "Nursery 3"}],
           "cursor": None, "messages": [
               {"messageId": "m3", "createdAt": "2026-06-01T09:00:00Z",
                "author": {"title": "Alex"}, "body": "hi", "unread": False, "images": [], "files": []},
           ]})
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    convos = fetch_conversations(c)
    by_id = {conv.id: conv for conv in convos}
    assert by_id["c1"].unread is True
    assert by_id["c2"].unread is False


def test_unread_only_peeks_first_page_and_skips_read_conversations():
    """--unread must not paginate the full history of every conversation:
    unread messages are the newest, so one first-page peek per conversation
    decides whether it's worth fetching at all."""
    read_msgs = [_msg(f"r{n}", f"2026-06-01T09:00:{59-n:02d}+00:00") for n in range(50)]
    unread_first = dict(_msg("u1", "2026-06-02T09:00:00+00:00"), unread=True)
    calls = []

    def transport(method, url, headers, body):
        calls.append(url)
        if "/api/v2/conversations?" in url:
            return 200, json.dumps({"conversations": [
                {"conversationId": "c-read", "title": "A", "participants": []},
                {"conversationId": "c-unread", "title": "B", "participants": []},
            ]}).encode()
        if "c-read" in url:
            return 200, json.dumps({"messages": read_msgs}).encode()
        if "olderThan" in url:
            return 200, json.dumps({"messages": []}).encode()
        return 200, json.dumps({"messages": [unread_first]}).encode()

    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    convos = fetch_conversations(c, unread_only=True)
    assert [x.id for x in convos] == ["c-unread"]
    assert convos[0].unread is True
    # The fully-read conversation was peeked exactly once — its 50-message
    # first page (a full page) was never paginated further.
    assert sum("c-read" in u for u in calls) == 1
