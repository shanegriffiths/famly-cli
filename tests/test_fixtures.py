import json
import re

from tests.conftest import load_fixture

ULID_RE = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")
ULID_PLACEHOLDER = "00000000000000000000000000"

UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
UUID_PLACEHOLDER = "00000000-0000-0000-0000-000000000000"

# Famly content-addressed image hash: 64 hex chars in the image URL path. Real
# ones are direct handles to real photos, so only the all-zero placeholder is allowed.
HASH_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
HASH_PLACEHOLDER = "0" * 64

# Every real capture date is replaced with this synthetic constant.
DATE_RE = re.compile(r"20\d\d-\d\d-\d\d")
DATE_PLACEHOLDER = "2020-01-01"


def test_fixtures_contain_no_real_pii():
    for name in ("observations_all_variants.json", "feed_full.json"):
        data = load_fixture(name)
        blob = json.dumps(data)
        assert "Ava" not in blob
        assert set(ULID_RE.findall(blob)) <= {ULID_PLACEHOLDER}
        assert set(UUID_RE.findall(blob)) <= {UUID_PLACEHOLDER}
        assert set(HASH_RE.findall(blob)) <= {HASH_PLACEHOLDER}
        assert set(DATE_RE.findall(blob)) <= {DATE_PLACEHOLDER}


def test_observation_fixture_has_all_variants_and_images():
    data = load_fixture("observations_all_variants.json")
    assert data.get("imageCount", len(data.get("images", []))) >= 60
    assert len(data.get("images", [])) >= 60


def test_feed_fixture_has_direct_images():
    data = load_fixture("feed_full.json")
    assert len(data.get("directImgs", [])) >= 30
    assert data.get("directImageCount", 0) >= 30


def test_conversations_fixture_shape():
    data = load_fixture("conversations.json")
    assert "list" in data and "detail" in data
    convos = data["list"]["conversations"]
    assert len(convos) >= 1
    assert convos[0]["conversationId"] == "c1"
    detail = data["detail"]
    assert detail["messages"][0]["messageId"] == "m1"


def test_me_fixture_shape():
    data = load_fixture("me.json")
    assert data["name"]["fullName"]
    # children come from role relations (targetType Famly.Daycare:Child), not a `children` key
    child_roles = [r for r in data["roles2"] if r.get("targetType") == "Famly.Daycare:Child"]
    assert len(child_roles) == 1
    assert child_roles[0]["targetId"] == "child-1"
