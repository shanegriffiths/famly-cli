import json

from famly.sources.observations import fetch_observations, VARIANTS
from famly.client import ApiClient
from tests.conftest import FakeTransport

def _obs_page(next_cursor):
    return {"data": {"childDevelopment": {"observations": {
        "next": next_cursor,
        "results": [{"id": "o1", "variant": "REGULAR_OBSERVATION",
                     "status": {"createdAt": "2026-06-25T13:00:00Z"},
                     "createdBy": {"name": {"fullName": "Alex"}},
                     "remark": {"body": "Father's Day cards"},
                     "images": [{"id": "img1", "width": 1920, "height": 2560,
                                 "url": "https://img.famly.co/image/H/1080x1920/a.jpg?expires=Z"}],
                     "videos": [], "files": [], "children": [{"id": "child-1", "name": "Robin"}]}]}}}}

def test_requests_all_five_variants_and_paginates():
    t = FakeTransport()
    t.routes.append(("/graphql?LearningJourneyQuery", 200, json.dumps(_obs_page(None)).encode()))
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    obs = fetch_observations(c, "child-1")
    assert len(obs) == 1 and obs[0].images[0].id == "img1"
    assert obs[0].images[0].url == "https://img.famly.co/image/H/1920x2560/a.jpg?expires=Z"
    assert set(VARIANTS) == {"ASSESSMENT","REGULAR_OBSERVATION","PARENT_OBSERVATION","UP_TO_SPEED_OBSERVATION","TWO_YEAR_PROGRESS"}
    assert t.calls[0]["body"]["variables"]["variants"] == VARIANTS


def test_paginates_across_two_pages():
    pages = [
        {"data": {"childDevelopment": {"observations": {
            "next": "CURSOR",
            "results": [{"id": "o1", "variant": "REGULAR_OBSERVATION",
                         "status": {"createdAt": "2026-06-25T13:00:00Z"},
                         "createdBy": {"name": {"fullName": "Alex"}},
                         "remark": {"body": "Page one"},
                         "images": [], "videos": [], "files": [], "children": []}]}}}},
        {"data": {"childDevelopment": {"observations": {
            "next": None,
            "results": [{"id": "o2", "variant": "REGULAR_OBSERVATION",
                         "status": {"createdAt": "2026-06-26T13:00:00Z"},
                         "createdBy": {"name": {"fullName": "Alex"}},
                         "remark": {"body": "Page two"},
                         "images": [], "videos": [], "files": [], "children": []}]}}}},
    ]
    state = {"n": 0}
    calls = []

    def transport(method, url, headers, body):
        parsed = json.loads(body) if body else None
        calls.append({"method": method, "url": url, "headers": headers, "body": parsed})
        page = pages[min(state["n"], len(pages) - 1)]
        state["n"] += 1
        return 200, json.dumps(page).encode()

    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    obs = fetch_observations(c, "child-1")
    assert [o.id for o in obs] == ["o1", "o2"]
    assert len(calls) == 2
    assert calls[1]["body"]["variables"]["next"] == "CURSOR"


def test_stops_on_non_advancing_cursor():
    # Server keeps returning the same non-null cursor — must not loop forever.
    page = {"data": {"childDevelopment": {"observations": {
        "next": "SAME",
        "results": [{"id": "o1", "variant": "REGULAR_OBSERVATION",
                     "status": {"createdAt": "2026-06-25T13:00:00Z"},
                     "createdBy": {"name": {"fullName": "Alex"}},
                     "remark": {"body": "stuck"},
                     "images": [], "videos": [], "files": [], "children": []}]}}}}
    calls = []

    def transport(method, url, headers, body):
        calls.append(url)
        return 200, json.dumps(page).encode()

    c = ApiClient("https://app.famly.co", token="T", transport=transport)
    obs = fetch_observations(c, "child-1")
    # First page fetched (cursor None → "SAME"), second page fetched (cursor "SAME"
    # equals previous), then break — exactly two requests, no infinite loop.
    assert len(calls) == 2
    assert len(obs) == 2


def test_minimal_observation_no_crash():
    minimal = {"data": {"childDevelopment": {"observations": {
        "next": None,
        "results": [{"id": "o1", "images": [], "videos": [], "files": []}]}}}}
    t = FakeTransport()
    t.routes.append(("/graphql?LearningJourneyQuery", 200, json.dumps(minimal).encode()))
    c = ApiClient("https://app.famly.co", token="T", transport=t)
    obs = fetch_observations(c, "child-1")
    assert len(obs) == 1
    o = obs[0]
    assert o.id == "o1"
    assert o.date == ""
    assert o.author == ""
    assert o.caption == ""
    assert o.images == [] and o.videos == [] and o.files == []
