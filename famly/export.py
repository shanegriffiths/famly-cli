import json
import re
import sys
from pathlib import Path

from .client import AuthError
from .output import to_jsonable
from .photos import download_refs
from .progress import status
from .sources.events import fetch_events
from .sources.feed import fetch_feed
from .sources.messages import fetch_conversations
from .sources.notes import fetch_notes
from .sources.observations import fetch_observations
from .sources.profile import fetch_profile
from .sources.tagged import fetch_tagged

_FAILED = object()


def child_slug(name, child_id, taken):
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    if not slug or slug in taken:
        # child_id is server-controlled: filter it too so a hostile id like
        # "../../etc" can't make the slug a directory-traversal path.
        suffix = re.sub(r"[^a-z0-9]", "", (child_id or "").lower())[:8]
        slug = f"{slug}-{suffix}".strip("-") or "child"
    return slug


def _write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(to_jsonable(obj), indent=2, ensure_ascii=False))
    tmp.replace(path)  # atomic: a crash mid-write can't destroy the previous good copy


def _try(label, fn):
    """Like photos._safe, but returns _FAILED instead of [] so a failed source
    never overwrites a previous run's good JSON with an empty list."""
    try:
        return fn()
    except AuthError:
        raise
    except Exception as e:
        print(f"warning: famly source '{label}' failed, skipping: {e}", file=sys.stderr)
        return _FAILED


def export_all(client, out_dir, children, *, events_from, events_to, quiet=False,
                all_children=None) -> dict:
    """`all_children`, if given, is the full set of children on the account —
    used for children.json and slug assignment so a --child run (which passes
    a narrowed `children` subset) can't rewrite account-level state or
    reassign another child's folder slug."""
    out = Path(out_dir)
    data = out / "data"
    refs = []
    all_children = all_children or list(children)
    summary = {"out_dir": str(out), "children": len(children)}

    _write_json(data / "children.json", all_children)

    status("Fetching newsfeed…", quiet)
    feed = _try("feed", lambda: fetch_feed(client))
    if feed is not _FAILED:
        _write_json(data / "feed.json", feed)
        for f in feed:
            refs += f.images + f.videos + f.files
    summary["feed_items"] = 0 if feed is _FAILED else len(feed)

    status("Fetching messages…", quiet)
    convos = _try("messages", lambda: fetch_conversations(client, include_archived=True))
    if convos is not _FAILED:
        _write_json(data / "messages.json", convos)
        for c in convos:
            for m in c.messages:
                refs += m.images + m.files
    summary["conversations"] = 0 if convos is _FAILED else len(convos)

    slugs, taken = {}, set()
    for child in all_children:
        slug = child_slug(child.name, child.id, taken)
        taken.add(slug)
        slugs[child.id] = slug

    obs_n = notes_n = events_n = 0
    for child in children:
        cdir = data / slugs[child.id]
        status(f"Fetching observations for {child.name}…", quiet)
        obs = _try("observations", lambda: fetch_observations(client, child.id))
        if obs is not _FAILED:
            _write_json(cdir / "observations.json", obs)
            obs_n += len(obs)
            for o in obs:
                refs += o.images + o.videos + o.files
        status(f"Fetching notes for {child.name}…", quiet)
        notes = _try("notes", lambda: fetch_notes(client, child.id))
        if notes is not _FAILED:
            _write_json(cdir / "notes.json", notes)
            notes_n += len(notes)
            for n in notes:
                refs += n.images
        status(f"Fetching events for {child.name}…", quiet)
        events = _try("events", lambda: fetch_events(client, child.id, events_from, events_to))
        if events is not _FAILED:
            _write_json(cdir / "events.json", events)
            events_n += len(events)
        status(f"Fetching tagged photos for {child.name}…", quiet)
        tagged = _try("tagged", lambda: fetch_tagged(client, child.id))
        if tagged is not _FAILED:
            refs += tagged
        status(f"Fetching profile photo for {child.name}…", quiet)
        profile = _try("profile", lambda: fetch_profile(client, child.id))
        if profile is not _FAILED and profile:
            refs.append(profile)

    summary.update(observations=obs_n, notes=notes_n, events=events_n)
    photos_summary = download_refs(client, refs, out / "photos",
                                   incremental=True, make_gallery=True, quiet=quiet)
    photos_summary.pop("out_dir")
    summary["photos"] = photos_summary
    return summary
