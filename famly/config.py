import os, sys, uuid
from dataclasses import dataclass
from pathlib import Path

@dataclass
class Credentials:
    email: str | None = None
    password: str | None = None
    access_token: str | None = None

def default_config_dir() -> Path:
    if env := os.environ.get("FAMLY_CONFIG_DIR"):
        return Path(env)
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "famly"

class Config:
    def __init__(self, base_url: str, config_dir: Path | None = None):
        self.base_url = base_url
        self.config_dir = config_dir or default_config_dir()

    def device_id(self) -> str:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        f = self.config_dir / "device_id"
        if f.exists():
            return f.read_text(encoding="utf-8").strip()
        did = str(uuid.uuid4())
        f.write_text(did, encoding="utf-8")
        return did

    def _op_lookup(self) -> Credentials | None:
        item = os.environ.get("FAMLY_OP_ITEM")
        if not item:
            return None
        import subprocess, json
        try:
            out = subprocess.run(["op", "item", "get", item, "--format", "json"],
                                 capture_output=True, text=True, check=True).stdout
            data = json.loads(out)
            fields = {f.get("id") or f.get("label"): f.get("value") for f in data.get("fields", [])}
            email, password = fields.get("username"), fields.get("password")
            if not (email and password):
                return None  # partial/empty item — fall through to next credential source
            return Credentials(email=email, password=password)
        except FileNotFoundError:
            return None
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            print(f"warning: 1Password lookup for FAMLY_OP_ITEM failed: {e}", file=sys.stderr)
            return None

    def resolve_credentials(self, cli_email=None, cli_password=None, cli_token=None) -> Credentials:
        if cli_token or os.environ.get("FAMLY_ACCESS_TOKEN"):
            return Credentials(access_token=cli_token or os.environ.get("FAMLY_ACCESS_TOKEN"))
        if cli_email and cli_password:
            return Credentials(email=cli_email, password=cli_password)
        if os.environ.get("FAMLY_EMAIL") and os.environ.get("FAMLY_PASSWORD"):
            return Credentials(email=os.environ["FAMLY_EMAIL"], password=os.environ["FAMLY_PASSWORD"])
        if (op := self._op_lookup()):
            return op
        return Credentials()  # caller prompts if interactive
