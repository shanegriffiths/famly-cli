import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from ..models import MediaRef

CHILD_TARGET = "Famly.Daycare:Child"


def profile_full_res(url: str) -> str:
    url = re.sub(r"/\d+x\d+/", "/1600x1600/", url, count=1)
    parts = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "crop"]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def fetch_profile(client, child_id: str) -> MediaRef | None:
    """The child-summary endpoint frequently omits the profile image; the
    child's role relation in /api/me/me/me carries `image` (a face-cropped
    avatar). Prefer that, fall back to the summary endpoint."""
    url = None
    me = client.get("/api/me/me/me")
    if isinstance(me, dict):
        for r in (me.get("roles2") or me.get("roles") or []):
            if r.get("targetType") == CHILD_TARGET and r.get("targetId") == child_id and r.get("image"):
                url = r["image"]
                break
    if not url:
        data = client.get(f"/api/v2/children/{child_id}/summary")
        url = ((data or {}).get("profileImage") or {}).get("url") if isinstance(data, dict) else None
    if not url:
        return None
    return MediaRef(id=f"profile-{child_id[:8]}", url=profile_full_res(url), kind="image",
                    width=1600, height=1600, source="profile", date=None, caption="Profile photo")
