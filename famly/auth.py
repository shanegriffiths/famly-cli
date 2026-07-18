import json, os
from pathlib import Path
from importlib.resources import files
from .client import ApiClient, ApiError

def _query(name: str) -> str:
    return files("famly.graphql").joinpath(f"{name}.graphql").read_text()

def login(client: ApiClient, email: str, password: str, device_id: str) -> str:
    data = client.graphql("Authenticate",
                          {"email": email, "password": password, "deviceId": device_id, "legacy": False},
                          _query("Authenticate"))
    result = (data.get("me") or {}).get("authenticateWithPassword") or {}
    token = result.get("accessToken")
    if token:
        return token
    if result.get("__typename") == "AuthenticationChallenged" or result.get("loginId"):
        raise ApiError("Famly requires two-factor authentication, which this tool does not support. "
                       "Log in via the Famly app/browser and supply the token with FAMLY_ACCESS_TOKEN instead.")
    title = result.get("errorTitle") or result.get("status") or "login failed"
    detail = result.get("errorDetails") or ""
    raise ApiError(f"Famly login failed: {title}. {detail}".strip())

class TokenStore:
    def __init__(self, config_dir: Path):
        self.path = Path(config_dir) / "token.json"
    def load_record(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}
    def load(self) -> str | None:
        return self.load_record().get("access_token")
    def save(self, token: str, email: str | None = None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {"access_token": token} | ({"email": email} if email else {})
        # Owner-only from the moment of creation — never world-readable, even briefly.
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(json.dumps(record))
        os.chmod(self.path, 0o600)  # pre-existing files keep tight perms too

def authenticated_client(base_url, creds, *, config_dir, transport=None, device_id, force=False) -> ApiClient:
    store = TokenStore(config_dir)
    client = ApiClient(base_url, transport=transport)
    if creds.access_token:
        client.token = creds.access_token
        return client
    if not force and (cached := store.load()):
        client.token = cached
        return client
    if creds.email and creds.password:
        token = login(client, creds.email, creds.password, device_id)
        store.save(token, email=creds.email)
        client.token = token
        return client
    raise RuntimeError("no credentials available")
