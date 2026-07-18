import sys
from pathlib import Path
from .client import AuthError
from .media import dedupe, download, write_manifest, load_manifest
from .progress import status, track
from .gallery import render
from .sources.observations import fetch_observations
from .sources.feed import fetch_feed
from .sources.messages import fetch_conversations
from .sources.notes import fetch_notes
from .sources.tagged import fetch_tagged
from .sources.profile import fetch_profile

ALL_SOURCES = ["observations", "feed", "messages", "notes", "tagged", "profile"]


def _safe(label, fn):
    """Run one source's fetch; on failure warn and return [] so a single broken
    or permission-denied source can't abort the whole archive. Auth failures do
    abort: every remaining source would fail the same way, and the run must not
    masquerade as a successful empty archive."""
    try:
        return fn()
    except AuthError:
        raise
    except Exception as e:
        print(f"warning: famly source '{label}' failed, skipping: {e}", file=sys.stderr)
        return []


def _collect(client, child_id, sources, since, include_videos, include_files, quiet=False):
    refs = []
    if "observations" in sources:
        status("Fetching observations…", quiet)
        for o in _safe("observations", lambda: fetch_observations(client, child_id)):
            refs += o.images + (o.videos if include_videos else []) + (o.files if include_files else [])
    if "feed" in sources:
        status("Fetching newsfeed…", quiet)
        for f in _safe("feed", lambda: fetch_feed(client, since=since)):
            refs += f.images + (f.videos if include_videos else []) + (f.files if include_files else [])
    if "messages" in sources:
        status("Fetching messages…", quiet)
        for c in _safe("messages", lambda: fetch_conversations(client, include_archived=True)):
            for m in c.messages:
                refs += m.images + (m.files if include_files else [])
    if "notes" in sources:
        status("Fetching notes…", quiet)
        for n in _safe("notes", lambda: fetch_notes(client, child_id)):
            refs += n.images
    if "tagged" in sources:
        status("Fetching tagged photos…", quiet)
        refs += _safe("tagged", lambda: fetch_tagged(client, child_id))
    if "profile" in sources:
        status("Fetching profile photo…", quiet)
        if (p := _safe("profile", lambda: fetch_profile(client, child_id))):
            refs.append(p)
    if since:
        # Undated refs are kept: silently dropping them (e.g. a tagged photo
        # whose createdAt shape didn't parse) would be data loss.
        refs = [r for r in refs if not r.date or r.date >= since]
    return [r for r in refs if r.kind == "image" or (include_videos and r.kind == "video") or (include_files and r.kind == "file")]


def download_refs(client, refs, out_dir, *, incremental, make_gallery, quiet=False) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    refs = dedupe(refs)
    existing = {r["id"] for r in load_manifest(out_dir)} if incremental else set()
    refs.sort(key=lambda r: (r.date or "", r.id))
    records, per_day, done, failed = (load_manifest(out_dir) if incremental else []), {}, 0, 0
    to_download = [r for r in refs if r.id not in existing]
    if incremental and (skipped := len(refs) - len(to_download)):
        status(f"Skipping {skipped} already-downloaded item(s).", quiet)
    status(f"Downloading {len(to_download)} item(s) to {out_dir}…", quiet)
    try:
        for r in track(to_download, "Downloading", quiet):
            day = (r.date or "unknown")[:10]; per_day[day] = per_day.get(day, 0) + 1
            try:
                path = download(client, r, out_dir, per_day[day])
            except AuthError:
                raise
            except Exception as e:
                failed += 1
                print(f"warning: download failed for {r.source} item {r.id or '?'}: {e}", file=sys.stderr)
                continue
            records.append({"file": path.name, "id": r.id, "source": r.source, "date": r.date,
                            "author": r.author, "caption": r.caption, "w": r.width, "h": r.height, "ref": r.ref_id})
            done += 1
    finally:
        # Always persist what made it to disk — an interrupt or auth failure
        # halfway through a long run must not orphan the downloaded files.
        # Sorting also merges incremental back-fills into date order.
        records.sort(key=lambda rec: (rec.get("date") or "", rec.get("id") or ""))
        write_manifest(out_dir, records)
    if make_gallery:
        status("Rendering gallery.html…", quiet)
        (out_dir / "gallery.html").write_text(render(records), encoding="utf-8")
    status(f"Done: {done} downloaded, {failed} failed, {len(refs)} total refs → {out_dir}", quiet)
    return {"downloaded": done, "failed": failed, "total_refs": len(refs), "out_dir": str(out_dir)}


def download_all(client, child, out_dir, *, sources, since, incremental,
                 include_videos, include_files, make_gallery, quiet=False) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)  # before _collect, as pre-split — a failed run still leaves the dir
    status(f"Collecting media for {child.name}…", quiet)
    refs = _collect(client, child.id, sources, since, include_videos, include_files, quiet)
    return download_refs(client, refs, out_dir, incremental=incremental,
                         make_gallery=make_gallery, quiet=quiet)
