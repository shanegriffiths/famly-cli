from urllib.parse import quote
from ..models import Note, MediaRef
from ..auth import _query
from ..media import full_res_url


def _note_image_url(im: dict) -> str:
    """Note images expose `secret` (prefix/path/expires), not a ready `url`.
    Build the full-res URL from the secret; fall back to `full_res_url` when a
    plain `url` is present (some responses / older shapes)."""
    if im.get("url"):
        return full_res_url(im)
    s = im.get("secret") or {}
    if s.get("prefix") and s.get("path") and im.get("width") and im.get("height"):
        u = f"{s['prefix']}/{im['width']}x{im['height']}/{s['path']}"
        if s.get("expires"):
            u += f"?expires={quote(str(s['expires']), safe='')}"
        return u
    return ""


def fetch_notes(client, child_id: str) -> list[Note]:
    q = _query("GetChildNotes"); out, cursor, prev = [], None, None
    while True:
        data = client.graphql("GetChildNotes", {"childId": child_id, "noteTypes": ["Classic"],
                              "parentVisible": True, "safeguardingConcern": False, "sensitive": False,
                              "limit": 50, "cursor": cursor}, q)
        node = (data or {}).get("childNotes") or {}
        for n in node.get("result", []):
            date = n.get("createdAt", "")
            note_id = n.get("noteId") or n.get("id") or ""  # live schema names it noteId
            out.append(Note(id=note_id, date=date,
                            author=((n.get("createdBy") or {}).get("name") or {}).get("fullName", ""),
                            body=n.get("text") or n.get("body") or "",
                            images=[MediaRef(id=i["id"], url=_note_image_url(i), kind="image", width=i.get("width"),
                                             height=i.get("height"), source="note", date=date,
                                             ref_id=note_id) for i in (n.get("images") or [])]))
        cursor = node.get("next")
        if not cursor or cursor == prev:
            break
        prev = cursor
    return out
