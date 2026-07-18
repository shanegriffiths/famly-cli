import json
import os
import urllib.error
import urllib.parse
import urllib.request
from . import __version__

DEFAULT_TIMEOUT = 60.0  # seconds; override with FAMLY_HTTP_TIMEOUT


def _urllib_transport(method, url, headers, body):
    req = urllib.request.Request(url=url, headers=headers, method=method, data=body)
    try:
        timeout = float(os.environ.get("FAMLY_HTTP_TIMEOUT") or DEFAULT_TIMEOUT)
    except ValueError:
        timeout = DEFAULT_TIMEOUT
    try:
        with urllib.request.urlopen(req, timeout=timeout) as f:
            return f.status, f.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        raise ApiError(f"network error: {e.reason}") from e
    except TimeoutError as e:
        # A timeout mid-read raises bare TimeoutError, not URLError.
        raise ApiError(f"network error: timed out after {timeout}s") from e


class ApiClient:
    def __init__(self, base_url, token=None, transport=None, refresh=None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._transport = transport or _urllib_transport
        # refresh: () -> new access token or None; called once on a 401 so an
        # expired cached token can be replaced without aborting the command.
        self._refresh = refresh

    def _headers(self):
        h = {"Content-Type": "application/json", "User-Agent": f"famly-cli/{__version__}"}
        if self.token:
            h["x-famly-accesstoken"] = self.token
        return h

    def _send(self, method, url, body, make_headers):
        """One HTTP exchange; on 401, re-authenticate via the refresh hook and
        retry exactly once before giving up with AuthError."""
        status, raw = self._transport(method, url, make_headers(), body)
        if status == 401 and self._refresh and (token := self._refresh()):
            self.token = token
            status, raw = self._transport(method, url, make_headers(), body)
        if status == 401:
            raise AuthError("unauthorized")
        return status, raw

    def _request(self, method, path, params=None, body=None):
        url = self.base_url + path
        if params:
            url += ("&" if "?" in path else "?") + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        status, raw = self._send(method, url, data, self._headers)
        if status >= 400:
            raise ApiError(f"{status}: {raw[:200]!r}")
        return json.loads(raw) if raw else None

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def download(self, url) -> bytes:
        """Fetch an absolute media URL as bytes. The media URL is server-supplied,
        so it is constrained to https: this blocks file://, ftp:// and data:// URLs
        (which urllib would happily open as a local-file read) and prevents the
        access token being sent over cleartext http. The token is additionally sent
        only to Famly hosts so it can't leak to foreign CDNs (e.g. presigned S3)."""
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https":
            raise ApiError(f"refusing to download non-https URL: {url}")

        def make_headers():
            h = {"User-Agent": f"famly-cli/{__version__}"}
            host = parts.hostname or ""
            base_host = urllib.parse.urlsplit(self.base_url).hostname or ""
            if self.token and (host == base_host or host.endswith(".famly.co")):
                h["x-famly-accesstoken"] = self.token
            return h

        status, raw = self._send("GET", url, None, make_headers)
        if status >= 400 or not raw:
            raise ApiError(f"download failed {status} for {url}")
        return raw

    def graphql(self, operation, variables, query):
        resp = self._request("POST", f"/graphql?{operation}",
                             body={"operationName": operation, "variables": variables, "query": query})
        if resp.get("errors"):
            raise ApiError(str(resp["errors"]))
        if "data" not in resp:
            raise ApiError(f"malformed graphql response: {resp!r}")
        return resp["data"]


class ApiError(Exception):
    pass


class AuthError(ApiError):
    pass
