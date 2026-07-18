from ..models import Child

CHILD_TARGET = "Famly.Daycare:Child"


def fetch_children(client) -> list[Child]:
    """Children come from the parent's role relations in /api/me/me/me
    (roles2, falling back to roles) — each child is a role whose targetType is
    'Famly.Daycare:Child': targetId=child id, title=name, subtitle=institution
    name. There is no top-level `children` key on this endpoint."""
    me = client.get("/api/me/me/me")
    if not isinstance(me, dict):
        return []
    roles = me.get("roles2") or me.get("roles") or []
    kids, seen = [], set()
    for r in roles:
        if r.get("targetType") != CHILD_TARGET:
            continue
        cid = r.get("targetId") or r.get("childId") or r.get("id")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        kids.append(Child(id=cid, name=r.get("title", "") or "",
                          institution=r.get("subtitle", "") or ""))
    return kids
