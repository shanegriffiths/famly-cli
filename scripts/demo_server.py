#!/usr/bin/env python3
"""Mock Famly backend for demos and local trials — serves entirely fake data.

Point the CLI at it and every command runs against synthetic content, so a
screen recording never touches a real account:

    python3 scripts/demo_server.py &                 # starts https://localhost:8765
    export FAMLY_BASE_URL=https://localhost:8765
    export SSL_CERT_FILE=scripts/.demo/cert.pem      # trust the self-signed cert
    export FAMLY_ACCESS_TOKEN=demo                    # skip the login prompt
    famly children
    famly photos --incremental --gallery --out ~/Pictures/famly-demo

The child ("Robin"), nursery ("Sunny Days Nursery"), staff ("Alex"), messages,
and photos are all invented. Media URLs point back here and are served as
generated placeholder images, so nothing real is ever downloaded. It talks
HTTPS with a self-signed cert (generated on first run into scripts/.demo/, which
is git-ignored) because the CLI only downloads media over HTTPS.
"""
from __future__ import annotations

import json
import os
import ssl
import struct
import subprocess
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get("FAMLY_DEMO_PORT", "8765"))
BASE = f"https://localhost:{PORT}"
CERT_DIR = Path(__file__).parent / ".demo"
CERT, KEY = CERT_DIR / "cert.pem", CERT_DIR / "key.pem"


def img(name, w, h):
    return {"imageId": name, "id": name, "width": w, "height": h, "url": f"{BASE}/media/{name}.png"}


# --- Synthetic account -------------------------------------------------------

CHILDREN = [
    {"targetType": "Famly.Daycare:Child", "targetId": "child-robin", "title": "Robin",
     "subtitle": "Sunny Days Nursery", "image": f"{BASE}/media/profile-robin.png"},
    {"targetType": "Famly.Daycare:Child", "targetId": "child-sam", "title": "Sam",
     "subtitle": "Sunny Days Nursery", "image": f"{BASE}/media/profile-sam.png"},
]

ME = {"name": {"fullName": "Demo Parent"}, "loginId": "demo", "roles2": CHILDREN}

FEED = {"feedItems": [
    {"feedItemId": "feed-1", "createdDate": "2026-06-20T09:12:00+00:00",
     "sender": {"title": "Sunflower Room"}, "body": "Water play in the garden this morning. Robin did not want to come inside!",
     "images": [img("feed-1a", 1200, 1600), img("feed-1b", 1600, 1200)], "videos": [], "files": []},
    {"feedItemId": "feed-2", "createdDate": "2026-06-17T14:30:00+00:00",
     "sender": {"title": "Sunflower Room"}, "body": "Pancake day! Lots of very sticky faces.",
     "images": [img("feed-2a", 1200, 1600)], "videos": [], "files": []},
    {"feedItemId": "feed-3", "createdDate": "2026-06-12T10:05:00+00:00",
     "sender": {"title": "Sunny Days Nursery"}, "body": "Reminder: the summer show is on the 15th of July.",
     "images": [], "videos": [], "files": []},
]}

CONVERSATIONS = {"conversations": [
    {"conversationId": "conv-1", "title": "Sunflower Room",
     "participants": [{"title": "Alex (Key Person)"}, {"title": "You"}], "archived": False},
]}

MESSAGES = {"messages": [
    {"messageId": "msg-1", "createdAt": "2026-06-30T08:12:00Z", "author": {"title": "Alex"},
     "body": "Good morning! Robin settled straight in and is busy with the train set.", "unread": True,
     "images": [img("msg-1a", 1200, 1600)], "files": []},
    {"messageId": "msg-2", "createdAt": "2026-06-28T16:40:00Z", "author": {"title": "You"},
     "body": "Thank you, that is lovely to hear!", "unread": False, "images": [], "files": []},
]}

OBSERVATIONS = {"data": {"childDevelopment": {"observations": {"next": None, "results": [
    {"id": "obs-1", "variant": "REGULAR_OBSERVATION", "status": {"createdAt": "2026-06-25T13:21:48Z"},
     "createdBy": {"name": {"fullName": "Alex"}},
     "remark": {"body": "Robin built a tall tower with the wooden blocks and counted each one to ten."},
     "images": [img("obs-1a", 1080, 1920), img("obs-1b", 1080, 1920)],
     "videos": [], "files": [], "children": [{"id": "child-robin"}]},
    {"id": "obs-2", "variant": "PARENT_OBSERVATION", "status": {"createdAt": "2026-06-11T18:00:00Z"},
     "createdBy": {"name": {"fullName": "Demo Parent"}},
     "remark": {"body": "Rode a balance bike all the way round the park at the weekend."},
     "images": [img("obs-2a", 1600, 1200)], "videos": [], "files": [], "children": [{"id": "child-robin"}]},
]}}}}

NOTES = {"data": {"childNotes": {"next": None, "result": [
    {"noteId": "note-1", "createdAt": "2026-06-05T10:00:00Z", "createdBy": {"name": {"fullName": "Alex"}},
     "text": "Settling in wonderfully and making friends quickly.", "images": [img("note-1a", 1200, 1600)]},
]}}}

CALENDAR = [{"days": [{"events": [
    {"title": "Summer Show", "from": "2026-07-15T10:00:00Z", "to": "2026-07-15T11:00:00Z",
     "originator": {"id": "event-1"}, "allDay": False},
    {"title": "Nursery closed (staff training)", "from": "2026-07-22T00:00:00Z",
     "to": "2026-07-22T23:59:00Z", "originator": {"id": "event-2"}, "allDay": True},
]}]}]

TAGGED = [img("tagged-1", 1200, 1600), img("tagged-2", 1600, 1200)]
for t in TAGGED:
    t["createdAt"] = "2026-06-18T14:00:00Z"


def obs_for(child_id):
    if child_id == "child-robin":
        return OBSERVATIONS
    return {"data": {"childDevelopment": {"observations": {"next": None, "results": []}}}}


def notes_for(child_id):
    if child_id == "child-robin":
        return NOTES
    return {"data": {"childNotes": {"next": None, "result": []}}}


def tagged_for(child_id):
    return TAGGED if child_id == "child-robin" else []


# --- Placeholder image -------------------------------------------------------

def placeholder_png(name: str, w: int = 480, h: int = 480) -> bytes:
    """A solid-colour PNG, colour derived from the name so tiles differ. Pure stdlib."""
    seed = zlib.crc32(name.encode())
    rgb = (120 + seed % 120, 90 + (seed >> 8) % 140, 140 + (seed >> 16) % 100)

    def chunk(typ, data):
        return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    raw = (b"\x00" + bytes(rgb) * w) * h
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))


# --- HTTP handler ------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep the demo terminal clean
        pass

    def _send(self, body: bytes, ctype: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj):
        self._send(json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        child = (q.get("childId") or [""])[0]

        if p.startswith("/media/"):
            return self._send(placeholder_png(Path(p).stem), "image/png")
        if p == "/api/me/me/me":
            return self._json(ME)
        if p == "/api/feed/feed/feed":
            return self._json({"feedItems": []} if "olderThan" in q else FEED)
        if p == "/api/v2/conversations":
            paged = int((q.get("offset") or ["0"])[0]) > 0 or (q.get("archived") or ["false"])[0] == "true"
            return self._json({"conversations": []} if paged else CONVERSATIONS)
        if p.startswith("/api/v2/conversations/"):
            return self._json({"messages": []} if "olderThan" in q else MESSAGES)
        if p == "/api/v2/calendar":
            return self._json(CALENDAR)
        if p == "/api/v2/images/tagged":
            return self._json([] if "olderThan" in q else tagged_for(child))
        if p.startswith("/api/v2/children/"):
            return self._json({})  # profile comes from the me role image; summary not needed
        if p == "/":
            return self._send(b"famly-cli demo server (all data is fake)\n", "text/plain")
        return self._json({})

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except Exception:
            payload = {}
        op = payload.get("operationName") or urlparse(self.path).query.split("&")[0]
        child = (payload.get("variables") or {}).get("childId", "child-robin")
        if op == "LearningJourneyQuery":
            return self._json(obs_for(child))
        if op == "GetChildNotes":
            return self._json(notes_for(child))
        if op == "Authenticate":
            return self._json({"data": {"me": {"authenticateWithPassword": {
                "__typename": "AuthenticationSucceeded", "status": "Succeeded",
                "accessToken": "demo-token", "deviceId": "demo"}}}})
        return self._json({"data": {}})


def ensure_cert():
    if CERT.exists() and KEY.exists():
        return
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
        "-keyout", str(KEY), "-out", str(CERT), "-days", "3650",
        "-subj", "/CN=localhost",
        "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
    ], check=True, capture_output=True)


def main():
    ensure_cert()
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(str(CERT), str(KEY))
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    print(f"famly-cli demo server on {BASE} (all data is fake). Ctrl-C to stop.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
