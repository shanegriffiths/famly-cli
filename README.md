<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/famly-logo-dark.png">
    <img alt="Famly" src="docs/famly-logo-light.png" width="200">
  </picture>
</p>
<p align="center">
  <a href="https://github.com/shanegriffiths/famly-cli/actions/workflows/ci.yml"><img src="https://github.com/shanegriffiths/famly-cli/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
</p>

A read-only command-line client for the [Famly](https://www.famly.co) childcare
app. It archives every full-resolution photo of your child from every source
Famly exposes to a parent: observations, newsfeed, messages, notes, tagged
photos, and profile. It also exposes Famly's read surface (children, feed,
messages, events, observations) as JSON. It never writes, sends, or deletes
anything on your account.

> **Unofficial.** Not affiliated with or endorsed by Famly ApS; "Famly" is a
> trademark of its owner. It uses Famly's private API with **your own**
> credentials and may break without notice. Use it only with an account you
> control, per Famly's Terms of Service, at your own risk.

## Install

Requires Python 3.11+.

### Manual install

```bash
pipx install git+https://github.com/shanegriffiths/famly-cli.git
```

### Install with an AI assistant

Not comfortable in a terminal? Paste the prompt below into an AI assistant
(ChatGPT, Claude, Gemini, or a coding assistant like Claude Code) and it will
walk you through installing, logging in, and downloading your photos, one step
at a time. It never asks for your password in the chat.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/openai-logo-dark.svg">
    <img alt="OpenAI" src="docs/openai-logo-light.svg" height="28">
  </picture>
  &nbsp;&nbsp;&nbsp;
  <img alt="Claude" src="docs/claude-logo.svg" height="28">
</p>

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
   privately in the terminal). Then run "famly whoami" and check for
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
8. Briefly mention the other things I can do: newest newsfeed posts
   ("famly feed"), unread messages ("famly messages --unread"), upcoming events
   ("famly events --from ... --to ..."), and a complete archive of everything
   ("famly export"). Then point me to the README for the details.

Remember: one step at a time, plain language, and stop to help me whenever
something does not go as expected.
```

</details>

## Auth

Log in once; the token is cached (owner-only) at `~/.config/famly/token.json`
and reused automatically afterwards.

```bash
famly login     # prompts for email + password, caches a token
famly whoami    # -> {"authenticated": true}
```

For headless use (cron, CI, a server), skip the prompt with environment
variables:

```bash
export FAMLY_EMAIL="you@example.com" FAMLY_PASSWORD="…"
# or:  export FAMLY_OP_ITEM="Famly"       # read user/pass from a 1Password item
# or:  export FAMLY_ACCESS_TOKEN="…"       # a token you already have
```

**Two-factor accounts:** password login can't complete on its own. Copy a token
from a logged-in browser (`localStorage['famly.accessToken']`) and set
`FAMLY_ACCESS_TOKEN`.

## Usage

Every command needs auth and prints JSON to stdout (except `gallery`, which reads
a local manifest).

```bash
famly children                                               # list children + ids
famly photos --incremental --gallery --out ~/Pictures/famly  # archive all photos + build gallery
famly feed --since 2026-06-01                                # newsfeed since a date
famly messages --unread                                      # unread messages
famly events --from 2026-07-01 --to 2026-07-31               # calendar events
famly observations --since 2026-06-01                        # learning-journey observations
famly export --out ~/Pictures/famly-export                   # full archive: media + all JSON
```

Add `--child <id>` to child-scoped commands (`observations`, `events`, `photos`,
`export`) for multi-child accounts; they default to your first child. `photos`
downloads at native resolution, dedupes, and with `--incremental` skips anything
already saved, so re-runs just top up. Progress prints to stderr and results to
stdout (piping stays clean); add `--quiet` to silence progress. Run
`famly <command> --help` for all flags.

## Development

```bash
git clone https://github.com/shanegriffiths/famly-cli.git
cd famly-cli
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
```

Tests are offline and fixture-driven (fixtures are scrubbed of personal data).
See [CONTRIBUTING](CONTRIBUTING.md) for more.

## License

[MIT](LICENSE) © Shane Griffiths.
