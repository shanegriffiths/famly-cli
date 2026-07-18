"""Self-contained HTML gallery generator for a famly-cli photo manifest.

A dark-theme, filterable gallery rendered as a pure function:
`render(records) -> str`. No I/O — the caller (photos.py / cli.py) is
responsible for writing the returned string to disk.
"""

import html as _html
import json

# Real manifest `source` values come from famly/sources/*.py (lowercase):
# "observation", "feed", "message", "note", "profile", "tagged".
_SOURCE_LABELS = {
    "observation": "Observation",
    "feed": "Newsfeed",
    "profile": "Profile",
    "message": "Message",
    "note": "Note",
    "tagged": "Tagged",
}

_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root{ --bg:#0d0d0f; --card:#17171a; --line:#26262b; --txt:#e8e8ea; --dim:#9a9aa2; --accent:#6ea8fe; --new:#ffb454; }
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,system-ui,sans-serif}
  header{position:sticky;top:0;z-index:5;background:rgba(13,13,15,.92);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);padding:16px 22px}
  h1{margin:0 0 4px;font-size:18px;font-weight:600}.sub{color:var(--dim);font-size:13px}
  .controls{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:12px}
  button.f{background:var(--card);color:var(--txt);border:1px solid var(--line);padding:6px 12px;border-radius:999px;cursor:pointer;font-size:13px}
  button.f.active{background:var(--accent);color:#0d0d0f;border-color:var(--accent);font-weight:600}
  input#q{background:var(--card);border:1px solid var(--line);color:var(--txt);padding:7px 12px;border-radius:8px;min-width:220px;flex:1}
  .count{color:var(--dim);font-size:12px;margin-left:auto} main{padding:18px 22px 80px}
  .month{margin:26px 0 12px;font-size:13px;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid var(--line);padding-bottom:6px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
  .card a.imgwrap{display:block;aspect-ratio:1/1;background:#000;overflow:hidden}
  .card img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .2s}.card a.imgwrap:hover img{transform:scale(1.04)}
  .meta{padding:9px 11px 11px}.row{display:flex;align-items:center;gap:6px;margin-bottom:5px}.date{font-size:12px;color:var(--dim)}
  .badge{font-size:10px;padding:2px 7px;border-radius:999px;font-weight:600;letter-spacing:.03em}
  .b-obs{background:#20303f;color:#8ecbff}.b-feed{background:#3a2f1a;color:var(--new)}.b-prof{background:#2a2340;color:#c3aaff}.b-other{background:#242430;color:#a9a9b4}
  .author{font-size:11px;color:var(--dim);margin-bottom:4px}
  .cap{font-size:12px;color:#c7c7cd;max-height:3.2em;overflow:hidden}.dim{font-size:10px;color:#5f5f68;margin-top:6px}
</style></head><body>
<header><h1>__TITLE__</h1>
<div class="sub">__SUBTITLE__</div>
<div class="controls">
  <button class="f active" data-f="all">All</button>
  <button class="f" data-f="observation">Observations</button>
  <button class="f" data-f="feed">Newsfeed</button>
  <button class="f" data-f="profile">Profile</button>
  <input id="q" placeholder="Search captions or authors&hellip;">
  <span class="count" id="count"></span>
</div></header><main id="main"></main>
<script>
const SOURCE_LABELS = __LABELS__;
const DATA = __DATA__;
const main=document.getElementById('main'),countEl=document.getElementById('count');let filter='all',q='';
const MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
const MONTHS_SHORT=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
/* Dates are parsed from the ISO string, never via the viewer's local clock:
   the same manifest must group photos into the same months on every machine
   (and agree with the manifest's own UTC day keys). */
function mk(d){const m=/^(\\d{4})-(\\d{2})/.exec(d||'');return m?m[1]+'-'+m[2]:'0000-00';}
function ml(k){const parts=k.split('-');const y=parts[0],i=+parts[1]-1;return (MONTHS[i]||'Undated')+' '+y;}
function fd(d){const m=/^(\\d{4})-(\\d{2})-(\\d{2})/.exec(d||'');if(!m)return '';return (+m[3])+' '+(MONTHS_SHORT[+m[2]-1]||'')+' '+m[1];}
function esc(s){return(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function badgeClass(s){return s==='observation'?'b-obs':s==='feed'?'b-feed':s==='profile'?'b-prof':'b-other';}
function badge(s){const label=SOURCE_LABELS[s]||s||'Unknown';return '<span class="badge '+badgeClass(s)+'">'+esc(label)+'</span>';}
function render(){
  main.innerHTML='';
  const rows=DATA.filter(function(r){
    if(filter!=='all'&&r.source!==filter)return false;
    if(q&&!((r.caption||'').toLowerCase().includes(q)||(r.author||'').toLowerCase().includes(q)))return false;
    return true;
  });
  countEl.textContent=rows.length+' of '+DATA.length+' shown';
  let cur=null,grid=null;
  for(const r of rows){
    const k=mk(r.date);
    if(k!==cur){
      cur=k;
      const h=document.createElement('div');h.className='month';h.textContent=ml(k);main.appendChild(h);
      grid=document.createElement('div');grid.className='grid';main.appendChild(grid);
    }
    const c=document.createElement('div');c.className='card';
    const file=r.file||'';
    c.innerHTML='<a class="imgwrap" href="'+encodeURI(file)+'" target="_blank" rel="noopener"><img loading="lazy" src="'+encodeURI(file)+'" alt="'+esc(r.caption||'')+'"></a>'+
      '<div class="meta"><div class="row"><span class="date">'+fd(r.date)+'</span>'+badge(r.source)+'</div>'+
      (r.author?'<div class="author">'+esc(r.author)+'</div>':'')+(r.caption?'<div class="cap">'+esc(r.caption)+'</div>':'')+
      '<div class="dim">'+(+r.w||'?')+'&times;'+(+r.h||'?')+'</div></div>';
    grid.appendChild(c);
  }
  if(!rows.length)main.innerHTML='<p style="color:var(--dim);padding:40px 0">No photos match.</p>';
}
document.querySelectorAll('button.f').forEach(function(b){b.onclick=function(){document.querySelectorAll('button.f').forEach(function(x){x.classList.remove('active');});b.classList.add('active');filter=b.dataset.f;render();};});
document.getElementById('q').addEventListener('input',function(e){q=e.target.value.toLowerCase().trim();render();});
render();
</script></body></html>"""


def _subtitle(records):
    count = len(records)
    noun = "photo" if count == 1 else "photos"
    dates = sorted(d for d in (r.get("date") for r in records) if d)
    if dates:
        date_range = f"{dates[0][:10]} → {dates[-1][:10]}"
        return f"{count} {noun} · {date_range}"
    return f"{count} {noun}"


def render(records) -> str:
    """Render a self-contained gallery.html string for a manifest.

    `records` is a list of manifest dicts, each shaped like:
    {"file", "id", "source", "date", "author", "caption", "w", "h", "ref"}.
    Pure function: no filesystem access, no side effects.
    """
    records = list(records or [])

    title = "Famly photos"
    subtitle = _subtitle(records)

    # Escape "</" so a caption/author containing "</script>" can't break out
    # of the inline <script> block. ensure_ascii keeps the payload plain
    # ASCII (emoji/curly-quotes become \uXXXX), which also sidesteps any
    # U+2028/U+2029 JS-string-literal line-terminator issues.
    labels_json = json.dumps(_SOURCE_LABELS, ensure_ascii=True).replace("</", "<\\/").replace("<!--", "<\\!--")
    data_json = json.dumps(records, ensure_ascii=True).replace("</", "<\\/").replace("<!--", "<\\!--")

    out = _TEMPLATE
    out = out.replace("__TITLE__", _html.escape(title))
    out = out.replace("__SUBTITLE__", _html.escape(subtitle))
    out = out.replace("__LABELS__", labels_json)
    # __DATA__ goes last and is not followed by further global replacements,
    # so arbitrary caption/author text embedded in it can't accidentally
    # match a later placeholder token.
    out = out.replace("__DATA__", data_json)
    return out
