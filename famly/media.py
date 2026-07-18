import re
import json
from pathlib import Path


def full_res_url(image_obj: dict) -> str:
    p, k = image_obj.get("prefix"), image_obj.get("key")
    w, h = image_obj.get("width"), image_obj.get("height")
    if p and k and w and h:
        return f"{p}/{w}x{h}/{k}"
    url = image_obj.get("url_big") or image_obj.get("url") or ""
    if url and w and h:
        swapped = re.sub(r"/\d+x\d+/", f"/{w}x{h}/", url, count=1)
        if swapped != url:
            return swapped
    return url


def dedupe(refs):
    seen, out = set(), []
    for r in refs:
        if not r.id:
            out.append(r)  # can't dedupe without an id, but never drop data
        elif r.id not in seen:
            seen.add(r.id); out.append(r)
    return out


def download(client, ref, out_dir: Path, index: int) -> Path:
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    data = client.download(ref.url)
    path = out_dir / ref.filename(index)
    # Defence in depth: ref.filename() already sanitises the API-supplied date,
    # but never write outside out_dir even if a future field slips through.
    if not path.resolve().is_relative_to(out_dir.resolve()):
        raise ValueError(f"refusing to write outside output dir: {ref.filename(index)!r}")
    path.write_bytes(data)
    return path


def load_manifest(out_dir: Path):
    f = Path(out_dir) / "_manifest.json"
    return json.loads(f.read_text()) if f.exists() else []


def write_manifest(out_dir: Path, records):
    (Path(out_dir) / "_manifest.json").write_text(json.dumps(records, indent=2))
