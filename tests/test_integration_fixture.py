"""End-to-end fixture test.

Replays the real 2026-07-01 Famly capture (scrubbed of PII, see
tests/fixtures/_build_fixtures.py) through the actual GraphQL client and
`fetch_observations` source module — the same code path `famly observations`
and `famly photos` use in production. This is the empirical proof behind the
whole project: a single day's real account had >=60 images across its
learning-journey observations, and the photo engine must not lose any of
them.

Note: the fixture's own `id`/`obsId` fields were scrubbed to a single
placeholder UUID (see tests/fixtures/_build_fixtures.py), so they can't be
used as unique MediaRef ids here without collapsing during dedupe. We
regenerate synthetic per-image ids (matching real-world uniqueness) while
keeping every other captured field — url, width, height, author, caption,
variant, date — untouched. That keeps this a genuine replay of the captured
API shape rather than a re-assertion of the fixture's own counters (already
covered by tests/test_fixtures.py).
"""

import json

from famly.client import ApiClient
from famly.sources.observations import VARIANTS, fetch_observations
from tests.conftest import FakeTransport, load_fixture


def _synthetic_observations_page(cap: dict) -> dict:
    """Fold the flattened capture's per-image records back into a single
    GraphQL `LearningJourneyQuery` observation node, as the real API would
    return it."""
    images = cap["images"]
    first = images[0]
    obs_node = {
        "id": first["obsId"],
        "variant": first["variant"],
        "status": {"createdAt": first["createdAt"]},
        "createdBy": {"name": {"fullName": first["author"]}},
        "remark": {"body": first["body"]},
        "images": [
            {"id": f"img-{i:04d}", "width": img["w"], "height": img["h"], "url": img["url"]}
            for i, img in enumerate(images)
        ],
        "videos": [],
        "files": [],
        "children": [],
    }
    return {"data": {"childDevelopment": {"observations": {"next": None, "results": [obs_node]}}}}


def test_observations_source_against_real_capture():
    """Feed the real 2026-07-01 capture through the GraphQL layer and assert >=60 images extracted."""
    cap = load_fixture("observations_all_variants.json")
    assert cap.get("imageCount", len(cap.get("images", []))) >= 60

    page = _synthetic_observations_page(cap)
    t = FakeTransport()
    t.routes.append(("/graphql?LearningJourneyQuery", 200, json.dumps(page).encode()))
    client = ApiClient("https://app.famly.co", token="T", transport=t)

    obs = fetch_observations(client, "child-1")

    # Assert the request asked for all five observation variants
    assert t.calls[0]["body"]["variables"]["variants"] == VARIANTS

    assert len(obs) == 1
    images = obs[0].images
    assert len(images) >= 60
    assert len(images) == len(cap["images"])

    # Spot-check the full-resolution rewrite ran on real captured URLs
    # (famly/media.py:full_res_url swaps the thumbnail size segment for
    # the image's actual width x height).
    sample_src, sample_out = cap["images"][0], images[0]
    assert f"/{sample_src['w']}x{sample_src['h']}/" in sample_out.url
