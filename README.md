<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/famly-logo-dark.png">
    <img alt="Famly" src="docs/famly-logo-light.png" width="200">
  </picture>
</p>
<p align="center">
  <a href="https://github.com/shanegriffiths/famly-cli/actions/workflows/ci.yml"><img src="https://github.com/shanegriffiths/famly-cli/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

<p align="center"><em>An unofficial, read-only command-line client for Famly — not affiliated with Famly ApS.</em></p>

A read-only command-line client for the [Famly](https://www.famly.co)
childcare/school app. It talks to the same API the Famly mobile/web app uses,
and does two things well:

1. **Reliably archive every full-resolution photo** of your child across every
   source Famly exposes to a parent — learning-journey observations, newsfeed,
   messages, notes, tagged photos, and profile photo.
2. **Expose Famly's read surface as JSON** — children, feed, messages, events,
   observations — so it composes cleanly with scripts, cron jobs, and agents.

Every read command prints structured JSON to stdout. `famly` never writes,
sends, or deletes anything on Famly's side; the only files it touches are local
(downloaded photos, a manifest, an HTML gallery, and a cached auth token).

> **Unofficial project.** Not affiliated with, endorsed by, or supported by
> Famly ApS. "Famly" is a trademark of its respective owner. This tool uses
> Famly's private, undocumented API with **your own** account credentials; that
> API can change or break at any time. It is read-only by design. Use it only
> with an account you control and in accordance with Famly's Terms of Service,
> entirely at your own risk.

## Install

Requires Python 3.11+. The only runtime dependency is `click`.

### Manual install

Install the latest from GitHub with [pipx](https://pipx.pypa.io):

```bash
pipx install git+https://github.com/shanegriffiths/famly-cli.git
```

Then continue with [Auth](#auth) and [Usage](#usage) below. (For a local
development checkout instead, see [Development](#development).)

### Install with an AI assistant

Not comfortable in a terminal? You don't have to be. Copy the prompt below and
paste it into an AI assistant — [ChatGPT](https://chatgpt.com),
[Claude](https://claude.ai), Gemini, or a coding assistant such as Claude Code —
and it will walk you through installing the tool, logging into your own Famly
account, and downloading your photos, one step at a time. It never asks for your
password in the chat.

<details>
<summary><strong>Click to copy the setup prompt</strong></summary>

```
You are helping me install and set up "famly-cli", a free, open-source
command-line tool that downloads full-resolution photos and exports data from
my own child's Famly nursery/school account. I am not very technical, so please
guide me patiently.

About the tool:
- It is unofficial and READ-ONLY: it never changes, sends, or deletes anything
  in my Famly account. It only reads my data and saves files onto my computer.
- Source code and full docs: https://github.com/shanegriffiths/famly-cli
- It needs Python 3.11 or newer and is installed with a tool called "pipx".
- It works on macOS, Windows, and Linux.

How to work with me:
- If you are able to run terminal commands yourself, do that and show me what
  happened. If you cannot, give me ONE command at a time, tell me exactly where
  to type it (Terminal on macOS/Linux, PowerShell on Windows), and wait for me
  to paste the result back before moving on.
- Explain each step in plain language and define any jargon.
- IMPORTANT: never ask me to paste my Famly password into this chat. When it is
  time to log in, have me run the tool's own "famly login" command, which asks
  for my password privately in my terminal and never reveals it to you.
- If a step produces an error, help me understand the message and fix it before
  continuing. Do not skip ahead.

Please take me through this, step by step:
1. Work out my operating system, and check whether Python 3.11+ is installed
   (try "python3 --version"). If it is missing or too old, walk me through
   installing it (python.org installer, or Homebrew on macOS).
2. Check whether "pipx" is installed (try "pipx --version"). If not, install it
   ("python3 -m pip install --user pipx" then "python3 -m pipx ensurepath") and
   have me open a new terminal window afterwards.
3. Install the tool:
   pipx install git+https://github.com/shanegriffiths/famly-cli.git
4. Confirm it worked: "famly --help" should list commands.
5. Log me in with "famly login" (it will prompt for my Famly email and password
   privately in the terminal). Then run "famly whoami" — I want to see
   {"authenticated": true}. If my account uses two-factor authentication,
   "famly login" will tell me; in that case explain how to copy an access token
   from a browser where I am logged into Famly (open the developer console and
   read localStorage['famly.accessToken']) and set it as the FAMLY_ACCESS_TOKEN
   environment variable instead.
6. Show my children and their ids: "famly children".
7. Help me with the main thing I want: download every full-resolution photo of
   my child into a folder and build a browsable gallery:
   famly photos --incremental --gallery --out ~/Pictures/famly
   Then tell me where the photos and the "gallery.html" file are, and how to
   open the gallery in my web browser.
8. Briefly mention the other things I can do — newest newsfeed posts
   ("famly feed"), unread messages ("famly messages --unread"), upcoming events
   ("famly events --from ... --to ..."), and a complete archive of everything
   ("famly export") — and point me to the README for the details.

Remember: one step at a time, plain language, and stop to help me whenever
something does not go as expected.
```

</details>

## Auth

Credentials are resolved in this order (first match wins — see
`famly/cli.py:_client` and `famly/config.py:resolve_credentials`):

1. **Explicit access token** — `--access-token` flag or `FAMLY_ACCESS_TOKEN`
   env var.
2. **Cached token** on disk at `~/.config/famly/token.json` (override the
   directory with `FAMLY_CONFIG_DIR`, or `XDG_CONFIG_HOME`). The file is written
   owner-only (`0600`). Once a token is cached, later commands use it directly —
   no re-auth, no prompt. The cache records the login email: if
   `--email`/`FAMLY_EMAIL` names a *different* account, the cache is bypassed and
   a fresh login runs instead of silently answering as the cached account. If a
   cached token expires mid-use, the CLI re-logins automatically with whatever
   credentials are resolvable below and caches the new token — headless runs
   self-heal.
3. `--email` / `--password` flags.
4. `FAMLY_EMAIL` + `FAMLY_PASSWORD` env vars.
5. **1Password**, via `FAMLY_OP_ITEM` — shells out to
   `op item get "$FAMLY_OP_ITEM" --format json` and reads its
   `username`/`password` fields. Requires the `op` CLI installed and signed in.
6. Interactive prompt (email + password), if stdin is a terminal.

Only the access token is ever written to disk; your password is never
persisted. A wrong email/password is reported as a clean error, not a
traceback.

**Interactive login:**

```bash
famly login     # prompts for email/password, caches the token
famly whoami    # -> {"authenticated": true}
```

**Headless (cron, CI, a server):**

```bash
export FAMLY_EMAIL="you@example.com"
export FAMLY_PASSWORD="…"
famly children
# …or keep the password out of the environment with 1Password:
export FAMLY_OP_ITEM="Famly"   # a 1Password Login item with username + password
famly children
```

### Two-factor accounts

If your account enforces two-factor auth, password login can't complete on its
own — `famly login` will say so. Grab a token from a logged-in browser
(`localStorage['famly.accessToken']`) and pass it via `FAMLY_ACCESS_TOKEN`.

## Usage

Every command except `gallery` (which only reads a local manifest) requires auth
and prints JSON to stdout.

```bash
# List children on the account (find the ids used by --child below)
famly children

# Archive every full-resolution photo of a child, all sources, deduped,
# skip anything already downloaded, and (re)build a browsable gallery
famly photos --incremental --gallery --out ~/Pictures/famly

# What's new on the newsfeed since a date
famly feed --since 2026-06-01

# Unread messages from staff
famly messages --unread

# Upcoming calendar events (trips, closures, parents' evenings)
famly events --from 2026-07-01 --to 2026-07-31

# Learning-journey observations for a child
famly observations --since 2026-06-01

# Rebuild gallery.html from an existing manifest, no re-download
famly gallery ~/Pictures/famly

# Complete archive: all media at full res AND all text (messages, feed,
# observations, notes, events) as JSON. Safe to re-run — tops up.
famly export --out ~/Pictures/famly-export
```

`famly children` returns each child's `id`, `name`, and `institution` (the
nursery/school name). Pass `--child <id>` on `observations`, `events`, `photos`,
and `export` for multi-child accounts (child-scoped commands default to the
first child from `famly children`). `famly feed` and `famly messages` are
account-level, not child-scoped.

`famly photos` flags of note: `--sources` (comma-separated, default is all of
`observations,feed,messages,notes,tagged,profile`; unknown names error
immediately), `--incremental` (skip already-downloaded ids from
`_manifest.json`), `--include-videos`, `--include-files`, `--gallery` (write
`gallery.html` alongside the photos). Photos are downloaded at their true native
resolution (e.g. 1920×2560), not the downscaled sizes the API returns by
default. The summary reports `downloaded`, `failed` (per-item download errors,
each detailed on stderr), and `total_refs`; the manifest is written even if a
run is interrupted, so `--incremental` always resumes cleanly. HTTP requests
time out after 60s (set `FAMLY_HTTP_TIMEOUT` to change).

`famly export [--out DIR] [--child ID]` writes a complete account archive:
`data/` holds `children.json`, `feed.json`, `messages.json`, and a folder per
child (`observations.json`, `notes.json`, `events.json` for −3y…+1y); `photos/`
is a single combined media archive (photos, videos, files, all sources, all
children) with the same manifest, dedupe, and gallery as `famly photos`. Re-runs
re-fetch the JSON, skip already-downloaded media, and never overwrite a good
JSON file with the result of a failed fetch. It exports all children by default;
`--child` narrows the child-scoped content.

## Progress output

Every command narrates what it's doing (`Fetching observations…`, per-source
fetch lines, and a live `Downloading … NN%` bar for `photos`) so a long run
never looks hung. **All of this goes to stderr; results stay on stdout**, so
piping or parsing the JSON is unaffected — `famly children > kids.json` gets
clean JSON while progress prints to the terminal. The download bar auto-hides
when stdout/stderr isn't a TTY (pipes, cron), and the global `--quiet`/`-q` flag
(placed before the command, e.g. `famly --quiet photos …`) silences progress
entirely.

## Read-only

`famly` has no commands to send a message, reply to staff, RSVP, or acknowledge
a post — those require the Famly app directly. Scheduling (cron, digests,
"what's new since last time") is the caller's job, not this tool's; `famly` just
answers the query it's given and prints JSON.

## Development

```bash
.venv/bin/pip install -e .
.venv/bin/python -m pytest -q
```

The test suite is offline and fixture-driven (the fixtures are scrubbed of all
personal data — see `tests/fixtures/_build_fixtures.py`). A single live-smoke
test is skipped unless `FAMLY_EMAIL` and `FAMLY_PASSWORD` are set in the
environment.

## License

[MIT](LICENSE) © Shane Griffiths.
