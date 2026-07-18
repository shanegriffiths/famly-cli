from ..models import Event


def fetch_events(client, child_id: str, frm: str, to: str) -> list[Event]:
    """`/api/v2/calendar` returns a list of period objects, each with `days`,
    each day with `events`. An event has `title`, `from`, `to`, and an
    `originator` ({type, id}). Flatten that into Event records."""
    data = client.get("/api/v2/calendar", params={"type": "RANGE", "day": frm, "to": to, "childId": child_id})
    periods = data if isinstance(data, list) else ([data] if isinstance(data, dict) else [])
    out = []
    for p in periods:
        for day in (p or {}).get("days", []) or []:
            for e in day.get("events", []) or []:
                out.append(Event(
                    id=((e.get("originator") or {}).get("id")) or e.get("id", "") or "",
                    title=e.get("title", "") or "",
                    start=e.get("from", "") or e.get("start", "") or "",
                    end=e.get("to", "") or e.get("end", "") or "",
                    all_day=bool(e.get("allDay") or e.get("allday") or False)))
    return out
