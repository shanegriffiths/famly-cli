from ..models import FeedItem, MediaRef
from ..media import full_res_url

def _img_ref(im, date, sender, ref_id):
    return MediaRef(id=im.get("imageId") or im.get("id"), url=full_res_url(im), kind="image",
                    width=im.get("width"), height=im.get("height"), source="feed",
                    date=date, author=sender, ref_id=ref_id)

def fetch_feed(client, since: str | None = None) -> list[FeedItem]:
    older_than, seen, out = None, set(), []
    while True:
        params = {"heightTarget": 4000}
        if older_than:
            params["olderThan"] = older_than
        data = client.get("/api/feed/feed/feed", params=params)
        items = (data or {}).get("feedItems", [])
        if not items:
            break
        advanced = False
        fresh_in_page = False
        for it in items:
            fid = it["feedItemId"]
            if fid in seen:
                continue
            seen.add(fid); advanced = True
            date = it.get("createdDate", "")
            if since and date and date < since:
                continue  # skip, but keep scanning: a pinned old post may precede newer items
            fresh_in_page = True
            sender = (it.get("sender") or {}).get("title", "")
            out.append(FeedItem(
                id=fid, date=date, sender=sender, body=(it.get("body") or "").strip(),
                images=[_img_ref(im, date, sender, fid) for im in (it.get("images") or [])],
                videos=[MediaRef(id=v.get("videoId") or v.get("id"), url=v.get("videoUrl") or v.get("url", ""),
                                 kind="video", source="feed", date=date, ref_id=fid)
                        for v in (it.get("videos") or []) if v.get("videoUrl") or v.get("url")],
                files=[MediaRef(id=f.get("fileId") or f.get("id"), url=f.get("url", ""), kind="file",
                                source="feed", date=date, ref_id=fid) for f in (it.get("files") or [])],
                embed_observation_id=(it.get("embed") or {}).get("observationId")))
        nxt = items[-1].get("createdDate")
        if not advanced or nxt == older_than:
            break
        if since and not fresh_in_page:
            break  # the whole page predates `since`; older pages can only be older
        older_than = nxt
    return out
