"""Re-scrub the committed test fixtures so they carry no real personal data.

The two large fixtures (`observations_all_variants.json`, `feed_full.json`)
preserve the exact JSON shape and all counts the tests rely on, but every
value that could identify a real person or their photos is neutralised. This
script is idempotent — running it again is a no-op — and reads/writes the
committed fixtures in place, so it needs no external source captures.

Scrubbing rules:
- Names/titles (keys name/fullName/title/sender/author) -> "Redacted Name";
  free text (keys body/caption/remark) -> "Redacted text". Empty stays empty.
- Any UUID (8-4-4-4-12 hex)   -> "00000000-0000-0000-0000-000000000000".
- Any ULID (26-char base32)   -> "00000000000000000000000000".
- Any 64-hex content hash (Famly's content-addressed image id, embedded in
  img.famly.co URLs) -> 64 zeros. These are direct handles to real images.
- img.famly.co URL query strings (signed, expiring tokens) are dropped.
- Real capture dates/times are replaced with a synthetic constant
  (2020-01-01), including the YYYY/MM/DD/HH segment inside image URL paths,
  so the fixtures leak no real timeline. Timezone suffixes are preserved.
- Numeric fields and list lengths are never touched.

Run with: .venv/bin/python tests/fixtures/_build_fixtures.py
"""

from __future__ import annotations

import json
import pathlib

import re

FIXTURES = pathlib.Path(__file__).parent
TARGETS = ("observations_all_variants.json", "feed_full.json")

UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
UUID_PLACEHOLDER = "00000000-0000-0000-0000-000000000000"

ULID_RE = re.compile(r"\b[0-9A-HJKMNP-TV-Z]{26}\b")
ULID_PLACEHOLDER = "00000000000000000000000000"

# Famly content-addressed image hash: 64 lowercase hex chars in the URL path.
HASH_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
HASH_PLACEHOLDER = "0" * 64

# archive/YYYY/MM/DD/HH path segment inside image URLs.
ARCHIVE_DATE_RE = re.compile(r"archive/\d{4}/\d{2}/\d{2}/\d{2}")
ARCHIVE_DATE_PLACEHOLDER = "archive/2020/01/01/00"

# ISO datetime then bare date; datetime first so its date part isn't clipped.
DATETIME_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
DATETIME_PLACEHOLDER = "2020-01-01T00:00:00"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DATE_PLACEHOLDER = "2020-01-01"

NAME_KEYS = {"name", "fullname", "title", "sender", "author"}
TEXT_KEYS = {"body", "caption", "remark"}
IMG_HOST = "img.famly.co"


def _scrub_string(key: str, value: str) -> str:
    v = value
    if key.lower() == "url" and IMG_HOST in v and "?" in v:
        v = v.split("?", 1)[0]

    lk = key.lower()
    if lk in NAME_KEYS:
        return "Redacted Name" if v else v
    if lk in TEXT_KEYS:
        return "Redacted text" if v else v

    v = UUID_RE.sub(UUID_PLACEHOLDER, v)
    v = ULID_RE.sub(ULID_PLACEHOLDER, v)
    v = HASH_RE.sub(HASH_PLACEHOLDER, v)
    v = ARCHIVE_DATE_RE.sub(ARCHIVE_DATE_PLACEHOLDER, v)
    v = DATETIME_RE.sub(DATETIME_PLACEHOLDER, v)
    v = DATE_RE.sub(DATE_PLACEHOLDER, v)
    return v


def _scrub(obj, parent_key: str = ""):
    if isinstance(obj, dict):
        return {k: _scrub(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v, parent_key) for v in obj]
    if isinstance(obj, str):
        return _scrub_string(parent_key, obj)
    return obj


def main() -> None:
    for name in TARGETS:
        path = FIXTURES / name
        data = json.loads(path.read_text())
        scrubbed = _scrub(data)
        path.write_text(json.dumps(scrubbed, indent=2) + "\n")
        print(f"{name}: re-scrubbed in place")


if __name__ == "__main__":
    main()
