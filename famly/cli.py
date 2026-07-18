import getpass
import os
import sys
from pathlib import Path

import click

from . import __version__
from .auth import authenticated_client, TokenStore, login as auth_login
from .client import ApiClient, ApiError, AuthError
from .config import Config
from .export import export_all
from .gallery import render
from .output import emit
from .photos import ALL_SOURCES, download_all
from .progress import status
from .sources.children import fetch_children
from .sources.events import fetch_events
from .sources.feed import fetch_feed
from .sources.messages import fetch_conversations
from .sources.observations import fetch_observations


class FamlyGroup(click.Group):
    """Group that turns backend auth/API failures into clean CLI errors."""

    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except click.Abort:
            raise
        except click.exceptions.Exit:
            raise  # click's --help/ctx.exit(0) subclasses RuntimeError; never remap it
        except click.exceptions.ClickException:
            raise
        except AuthError:
            raise click.ClickException(
                "Authentication failed or token expired. Run `famly login` to re-authenticate."
            )
        except ApiError as e:
            raise click.ClickException(f"Famly API error: {e}")
        except RuntimeError as e:
            raise click.ClickException(
                f"{e}. Set FAMLY_EMAIL/FAMLY_PASSWORD or FAMLY_OP_ITEM, or run `famly login`."
            )


def _relogin(ctx, cfg, store):
    """Refresh hook for cached-token clients: when the token 401s and full
    credentials are resolvable, re-login transparently instead of failing."""
    def refresh():
        creds = cfg.resolve_credentials(ctx.obj.get("email"), ctx.obj.get("password"), None)
        if not (creds.email and creds.password):
            return None
        token = auth_login(ApiClient(cfg.base_url), creds.email, creds.password, cfg.device_id())
        store.save(token, email=creds.email)
        return token
    return refresh


def _client(ctx, need_login=False, use_cache=True):
    quiet = ctx.obj.get("quiet", False)
    cfg = Config(base_url=ctx.obj["base_url"])
    # 1. explicit access token (flag / FAMLY_ACCESS_TOKEN) always wins
    explicit = ctx.obj.get("token") or os.environ.get("FAMLY_ACCESS_TOKEN")
    if explicit:
        return ApiClient(cfg.base_url, token=explicit)
    store = TokenStore(cfg.config_dir)
    # 2. cached token — avoids re-auth AND the op/prompt path entirely, but only
    # when it plausibly belongs to the requested account: a run with credentials
    # for account B must not be answered with account A's cached token.
    if use_cache:
        record = store.load_record()
        cached, cached_email, requested = record.get("access_token"), record.get("email"), ctx.obj.get("email")
        mismatch = bool(cached and requested) and (
            cached_email != requested if cached_email else bool(ctx.obj.get("password"))
        )
        if cached and not mismatch:
            return ApiClient(cfg.base_url, token=cached, refresh=_relogin(ctx, cfg, store))
        use_cache = not mismatch  # a mismatched cache must not be reloaded below
    # 3. resolve full credentials (may shell to op / prompt), then login + cache
    status("Authenticating with Famly…", quiet)
    creds = cfg.resolve_credentials(ctx.obj.get("email"), ctx.obj.get("password"), ctx.obj.get("token"))
    if not (creds.email or creds.access_token) and need_login and sys.stdin.isatty():
        creds.email = click.prompt("Famly email")
        creds.password = getpass.getpass("Famly password: ")
    return authenticated_client(cfg.base_url, creds, config_dir=cfg.config_dir,
                                device_id=cfg.device_id(), force=(not use_cache))


@click.group(cls=FamlyGroup)
@click.version_option(__version__)
@click.option("--base-url", envvar="FAMLY_BASE_URL", default="https://app.famly.co")
@click.option("--email", envvar="FAMLY_EMAIL")
@click.option("--password", envvar="FAMLY_PASSWORD")
@click.option("--access-token", "token", envvar="FAMLY_ACCESS_TOKEN")
@click.option("--quiet", "-q", is_flag=True, help="Suppress progress output on stderr")
@click.pass_context
def main(ctx, base_url, email, password, token, quiet):
    """Read-only CLI for the Famly childcare/school app.

    Progress is printed to stderr; JSON results go to stdout, so piping
    stdout stays clean. Pass --quiet before the command to silence progress.
    """
    ctx.ensure_object(dict)
    ctx.obj.update(base_url=base_url, email=email, password=password, token=token,
                   quiet=quiet)


@main.command()
@click.pass_context
def login(ctx):
    """Prompt for credentials and cache an access token."""
    c = _client(ctx, need_login=True, use_cache=False)
    click.echo("Logged in." if c.token else "Login failed.")


@main.command()
@click.pass_context
def children(ctx):
    """List children accessible to the authenticated account."""
    c = _client(ctx, need_login=True)
    status("Fetching children…", ctx.obj["quiet"])
    emit(fetch_children(c))


@main.command()
@click.option("--child")
@click.option("--since")
@click.pass_context
def observations(ctx, child, since):
    """List learning-journey observations for a child."""
    c = _client(ctx, need_login=True)
    status("Fetching children…", ctx.obj["quiet"])
    kids = fetch_children(c)
    if not child and not kids:
        raise click.ClickException("No children found on this account.")
    cid = child or kids[0].id
    status("Fetching observations…", ctx.obj["quiet"])
    obs = fetch_observations(c, cid)
    if since:
        obs = [o for o in obs if (o.date or "") >= since]
    emit(obs)


@main.command()
@click.option("--since")
@click.pass_context
def feed(ctx, since):
    """List newsfeed items."""
    c = _client(ctx, need_login=True)
    status("Fetching newsfeed…", ctx.obj["quiet"])
    emit(fetch_feed(c, since=since))


@main.command()
@click.option("--unread", is_flag=True)
@click.option("--include-archived", is_flag=True)
@click.pass_context
def messages(ctx, unread, include_archived):
    """List conversations and their messages."""
    c = _client(ctx, need_login=True)
    status("Fetching conversations…", ctx.obj["quiet"])
    emit(fetch_conversations(c, include_archived=include_archived, unread_only=unread))


@main.command()
@click.option("--from", "frm", required=True)
@click.option("--to", required=True)
@click.option("--child")
@click.pass_context
def events(ctx, frm, to, child):
    """List calendar events for a child in a date range."""
    c = _client(ctx, need_login=True)
    status("Fetching children…", ctx.obj["quiet"])
    kids = fetch_children(c)
    if not child and not kids:
        raise click.ClickException("No children found on this account.")
    cid = child or kids[0].id
    status("Fetching events…", ctx.obj["quiet"])
    emit(fetch_events(c, cid, frm, to))


@main.command()
@click.option("--child")
@click.option("--since")
@click.option("--out", default="famly-photos")
@click.option("--sources", default=",".join(ALL_SOURCES))
@click.option("--incremental", is_flag=True)
@click.option("--include-videos", is_flag=True)
@click.option("--include-files", is_flag=True)
@click.option("--gallery", "make_gallery", is_flag=True)
@click.pass_context
def photos(ctx, child, since, out, sources, incremental, include_videos, include_files, make_gallery):
    """Download photos (and optionally videos/files) across all sources."""
    requested = [s.strip() for s in sources.split(",") if s.strip()]
    unknown = [s for s in requested if s not in ALL_SOURCES]
    if unknown or not requested:
        raise click.ClickException(
            f"Unknown source(s): {', '.join(unknown) or '(none)'}. "
            f"Valid sources: {', '.join(ALL_SOURCES)}")
    c = _client(ctx, need_login=True)
    status("Finding children…", ctx.obj["quiet"])
    kids = fetch_children(c)
    if not kids:
        raise click.ClickException("No children found on this account.")
    if child:
        target = next((k for k in kids if k.id == child), None)
        if target is None:
            raise click.ClickException(f"No child with id {child}")
    else:
        target = kids[0]
    summary = download_all(
        c,
        target,
        out,
        sources=requested,
        since=since,
        incremental=incremental,
        include_videos=include_videos,
        include_files=include_files,
        make_gallery=make_gallery,
        quiet=ctx.obj["quiet"],
    )
    emit(summary)


@main.command()
@click.option("--out", default="famly-export")
@click.option("--child")
@click.pass_context
def export(ctx, out, child):
    """Archive everything: all media plus messages, feed, observations, notes,
    and events as JSON. Idempotent — re-run any time to top up."""
    from datetime import date, timedelta

    c = _client(ctx, need_login=True)
    status("Finding children…", ctx.obj["quiet"])
    kids = fetch_children(c)
    if not kids:
        raise click.ClickException("No children found on this account.")
    selected = kids
    if child:
        selected = [k for k in kids if k.id == child]
        if not selected:
            raise click.ClickException(f"No child with id {child}")
    today = date.today()
    summary = export_all(c, out, selected, all_children=kids,
                         events_from=(today - timedelta(days=3 * 365)).isoformat(),
                         events_to=(today + timedelta(days=365)).isoformat(),
                         quiet=ctx.obj["quiet"])
    emit(summary)


@main.command()
@click.argument("directory")
@click.pass_context
def gallery(ctx, directory):
    """Render gallery.html from an existing photo manifest directory."""
    import json

    manifest = Path(directory) / "_manifest.json"
    try:
        recs = json.loads(manifest.read_text())
    except FileNotFoundError:
        raise click.ClickException(
            f"No manifest at {manifest} — run `famly photos --out {directory}` first.")
    except (OSError, ValueError) as e:
        raise click.ClickException(f"Could not read {manifest}: {e}")
    status("Rendering gallery.html…", ctx.obj["quiet"])
    (Path(directory) / "gallery.html").write_text(render(recs))
    click.echo(f"Wrote {directory}/gallery.html")


@main.command()
@click.pass_context
def whoami(ctx):
    """Report whether the CLI can currently authenticate."""
    try:
        c = _client(ctx)
        c.get("/api/me/me/me")
        emit({"authenticated": True})
    except (AuthError, ApiError, RuntimeError):
        emit({"authenticated": False})
