from ..models import Conversation, Message, MediaRef
from ..media import full_res_url

def _list(client, archived):
    out, offset = [], 0
    while True:
        data = client.get("/api/v2/conversations",
                          params={"limit": 50, "offset": offset, "inbox": "OWN", "inbox2": 1,
                                  "archived": str(archived).lower()})
        arr = (data or {}).get("conversations", []) if isinstance(data, dict) else (data or [])
        if not arr:
            break
        out.extend(arr); offset += len(arr)
        if len(arr) < 50:
            break
    return out

def _messages(client, cid):
    msgs, older, seen = [], None, set()
    while True:
        params = {"limit": 50}
        if older:
            params["olderThan"] = older
        data = client.get(f"/api/v2/conversations/{cid}", params=params)
        page = (data or {}).get("messages", [])
        if not page:
            break
        advanced = False
        for m in page:
            mid = m.get("messageId", "")
            if mid in seen:
                continue
            seen.add(mid); advanced = True
            date = m.get("createdAt", "")
            msgs.append(Message(id=mid, date=date,
                                author=(m.get("author") or {}).get("title", ""), body=m.get("body", "") or "",
                                images=[MediaRef(id=im.get("imageId") or im.get("id"), url=full_res_url(im),
                                                 kind="image", width=im.get("width"), height=im.get("height"),
                                                 source="message", date=date, ref_id=cid) for im in (m.get("images") or [])],
                                files=[MediaRef(id=f.get("fileId") or f.get("id"), url=f.get("url", ""), kind="file",
                                                source="message", date=date, ref_id=cid) for f in (m.get("files") or [])],
                                unread=m.get("unread", False)))
        nxt = page[-1].get("createdAt")
        if not advanced or nxt == older or len(page) < 50:
            break
        older = nxt
    return msgs

def _has_unread(client, cid):
    """Peek at the newest page only: unread messages are by definition the most
    recent, so a fully-read first page means a fully-read conversation."""
    data = client.get(f"/api/v2/conversations/{cid}", params={"limit": 50})
    return any(m.get("unread") for m in (data or {}).get("messages", []))

def fetch_conversations(client, include_archived: bool = False, unread_only: bool = False) -> list[Conversation]:
    raw = _list(client, False) + (_list(client, True) if include_archived else [])
    out = []
    for c in raw:
        cid = c.get("conversationId") or c.get("id")
        if unread_only and not _has_unread(client, cid):
            continue  # skip without paginating this conversation's full history
        messages = _messages(client, cid)
        out.append(Conversation(id=cid, title=c.get("title", "") or "",
                                participants=[p.get("title") or p.get("name") for p in (c.get("participants") or [])],
                                archived=bool(c.get("archived")), messages=messages,
                                unread=any(msg.unread for msg in messages)))
    return out
