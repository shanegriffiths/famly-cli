from ..models import MediaRef
from ..media import full_res_url

PAGE = 100


def _created(i):
    raw = i.get("createdAt")
    return (raw or {}).get("date") if isinstance(raw, dict) else raw


def fetch_tagged(client, child_id: str) -> list[MediaRef]:
    out, seen, older = [], set(), None
    while True:
        params = {"childId": child_id, "limit": PAGE}
        if older:
            params["olderThan"] = older
        data = client.get("/api/v2/images/tagged", params=params)
        rows = data if isinstance(data, list) else []
        advanced = False
        for i in rows:
            iid = i.get("imageId") or i.get("id") or ""
            if iid:
                if iid in seen:
                    continue
                seen.add(iid); advanced = True
            out.append(MediaRef(id=iid, url=full_res_url(i), kind="image",
                                width=i.get("width"), height=i.get("height"),
                                source="tagged", date=_created(i)))
        # Stop on a short page, an unusable cursor, or no progress — the last
        # two guard against the endpoint ignoring or repeating the cursor.
        cursor = _created(rows[-1]) if rows else None
        if not advanced or len(rows) < PAGE or not cursor or cursor == older:
            break
        older = cursor
    return out
