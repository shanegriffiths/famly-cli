import re
from dataclasses import dataclass, field, asdict

@dataclass
class MediaRef:
    id: str; url: str; kind: str
    width: int | None = None; height: int | None = None
    source: str = ""; date: str | None = None
    caption: str = ""; author: str = ""; ref_id: str = ""
    def filename(self, index: int) -> str:
        # `date` is server-controlled; strip it to digits/hyphens so a hostile
        # value like "../../etc" or "/tmp/x" can't turn the filename into a
        # path that escapes the output directory.
        day = re.sub(r"[^0-9-]", "", (self.date or "")[:10]) or "unknown"
        raw_ext = {"video": "mp4", "file": "bin"}.get(self.kind, "jpg") if "." not in self.url.split("?")[0][-5:] \
                  else self.url.split("?")[0].rsplit(".", 1)[-1]
        ext = re.sub(r"[^A-Za-z0-9]", "", raw_ext) or "jpg"
        safe_id = re.sub(r"[^A-Za-z0-9]", "", (self.id or ""))[:8] or "img"
        return f"{day}_{index:02d}_{self.source}_{safe_id}.{ext}"
    def to_dict(self): return asdict(self)

@dataclass
class Child: id: str; name: str; institution_id: str = ""; room: str = ""; institution: str = ""
@dataclass
class Observation:
    id: str; variant: str; date: str; author: str; caption: str
    images: list = field(default_factory=list); videos: list = field(default_factory=list)
    files: list = field(default_factory=list); children: list = field(default_factory=list)
@dataclass
class FeedItem:
    id: str; date: str; sender: str; body: str
    images: list = field(default_factory=list); videos: list = field(default_factory=list)
    files: list = field(default_factory=list); embed_observation_id: str | None = None
@dataclass
class Message:
    id: str; date: str; author: str; body: str
    images: list = field(default_factory=list); files: list = field(default_factory=list)
    unread: bool = False
@dataclass
class Conversation:
    id: str; title: str; participants: list; archived: bool; messages: list = field(default_factory=list)
    unread: bool = False
@dataclass
class Note:
    id: str; date: str; author: str; body: str; images: list = field(default_factory=list)
@dataclass
class Event: id: str; title: str; start: str; end: str; all_day: bool = False
