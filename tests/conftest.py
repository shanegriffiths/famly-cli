import json
import pathlib


class FakeTransport:
    """Records requests; returns queued (status, body) responses keyed by substring of URL."""
    def __init__(self):
        self.routes = []
        self.calls = []

    def add(self, url_contains: str, payload, status: int = 200):
        self.routes.append((url_contains, status, json.dumps(payload).encode()))

    def __call__(self, method, url, headers, body):
        self.calls.append({
            "method": method,
            "url": url,
            "headers": headers,
            "body": json.loads(body) if body else None
        })
        for frag, status, data in self.routes:
            if frag in url:
                return status, data
        return 404, b'{"error":"no route"}'


class SequenceTransport:
    """Returns queued (status, raw_bytes) responses in call order; records requests."""
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append({"method": method, "url": url, "headers": headers,
                           "body": json.loads(body) if body else None})
        status, raw = self.responses.pop(0)
        return status, raw


FIX = pathlib.Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIX / name).read_text())
