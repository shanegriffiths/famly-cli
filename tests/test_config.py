from famly.config import Config, Credentials

def test_device_id_stable(tmp_path):
    c = Config(base_url="https://x", config_dir=tmp_path)
    first = c.device_id()
    assert first == Config(base_url="https://x", config_dir=tmp_path).device_id()
    assert len(first) == 36  # uuid

def test_credentials_precedence_flags_over_env(tmp_path, monkeypatch):
    monkeypatch.delenv("FAMLY_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("FAMLY_EMAIL", "env@x.com"); monkeypatch.setenv("FAMLY_PASSWORD", "envpw")
    c = Config(base_url="https://x", config_dir=tmp_path)
    creds = c.resolve_credentials(cli_email="cli@x.com", cli_password="clipw")
    assert (creds.email, creds.password) == ("cli@x.com", "clipw")

def test_credentials_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FAMLY_EMAIL", "env@x.com"); monkeypatch.setenv("FAMLY_PASSWORD", "envpw")
    monkeypatch.delenv("FAMLY_ACCESS_TOKEN", raising=False)
    c = Config(base_url="https://x", config_dir=tmp_path)
    creds = c.resolve_credentials()
    assert creds.email == "env@x.com" and creds.password == "envpw"

def test_op_lookup_partial_item_falls_through(tmp_path, monkeypatch):
    import json
    import subprocess

    monkeypatch.setenv("FAMLY_OP_ITEM", "test-item")
    monkeypatch.delenv("FAMLY_EMAIL", raising=False)
    monkeypatch.delenv("FAMLY_PASSWORD", raising=False)
    monkeypatch.delenv("FAMLY_ACCESS_TOKEN", raising=False)

    class _Result:
        # only a username, no password → partial item
        stdout = json.dumps({"fields": [{"id": "username", "value": "a@b.com"}]})

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Result())

    c = Config(base_url="https://x", config_dir=tmp_path)
    creds = c.resolve_credentials()
    assert creds == Credentials()  # fell through to empty (caller prompts)


def test_op_lookup_warning_on_failed_call(tmp_path, monkeypatch, capsys):
    import subprocess
    monkeypatch.setenv("FAMLY_OP_ITEM", "test-item")
    monkeypatch.delenv("FAMLY_EMAIL", raising=False)
    monkeypatch.delenv("FAMLY_PASSWORD", raising=False)
    monkeypatch.delenv("FAMLY_ACCESS_TOKEN", raising=False)

    def mock_run(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "op")

    monkeypatch.setattr("subprocess.run", mock_run)

    c = Config(base_url="https://x", config_dir=tmp_path)
    creds = c.resolve_credentials()

    assert creds == Credentials()
    captured = capsys.readouterr()
    assert "warning: 1Password lookup for FAMLY_OP_ITEM failed" in captured.err
