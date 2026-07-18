from ..models import Observation, MediaRef
from ..auth import _query
from ..media import full_res_url

VARIANTS = ["ASSESSMENT", "REGULAR_OBSERVATION", "PARENT_OBSERVATION",
            "UP_TO_SPEED_OBSERVATION", "TWO_YEAR_PROGRESS"]

def fetch_observations(client, child_id: str) -> list[Observation]:
    q = _query("LearningJourneyQuery")
    out, cursor, prev = [], None, None
    while True:
        data = client.graphql("LearningJourneyQuery",
                              {"childId": child_id, "variants": VARIANTS, "first": 50, "next": cursor}, q)
        node = data["childDevelopment"]["observations"]
        for ob in node["results"]:
            date = (ob.get("status") or {}).get("createdAt", "")
            author = ((ob.get("createdBy") or {}).get("name") or {}).get("fullName", "")
            cap = (ob.get("remark") or {}).get("body", "") or ""
            imgs = [MediaRef(id=i["id"], url=full_res_url(i), kind="image", width=i.get("width"),
                             height=i.get("height"), source="observation", date=date,
                             caption=cap, author=author, ref_id=ob["id"]) for i in (ob.get("images") or [])]
            vids = [MediaRef(id=v["id"], url=v.get("videoUrl", ""), kind="video", width=v.get("width"),
                             height=v.get("height"), source="observation", date=date, ref_id=ob["id"])
                    for v in (ob.get("videos") or []) if v.get("videoUrl")]
            files = [MediaRef(id=f["id"], url=f.get("url", ""), kind="file", width=None, height=None,
                              source="observation", date=date, ref_id=ob["id"]) for f in (ob.get("files") or [])]
            out.append(Observation(id=ob["id"], variant=ob.get("variant", ""), date=date, author=author,
                                   caption=cap, images=imgs, videos=vids, files=files,
                                   children=[c["id"] for c in (ob.get("children") or [])]))
        cursor = node.get("next")
        if not cursor or cursor == prev:
            break
        prev = cursor
    return out
