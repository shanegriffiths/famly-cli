# Contributing to famly-cli

Thanks for your interest. `famly-cli` is a small, read-only client for the
[Famly](https://www.famly.co) childcare app. It is an **unofficial** project,
not affiliated with or endorsed by Famly ApS.

## Ground rules

- **Read-only by design.** The CLI never writes, sends, or deletes anything on
  Famly's side. Please don't add commands that mutate a Famly account. That is
  intentionally out of scope.
- **Never commit personal data.** This tool handles a child's photos and
  messages. Downloaded media, `token.json`, and `_manifest.json` are git-ignored,
  so keep it that way. The JSON test fixtures are **scrubbed** of all real data
  (see below); never replace them with an unscrubbed capture from a live account.

## Development setup

Requires Python 3.11+. The only runtime dependency is `click`.

```bash
git clone https://github.com/shanegriffiths/famly-cli.git
cd famly-cli
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## Running the tests

```bash
.venv/bin/python -m pytest -q
```

The suite is fully offline and fixture-driven (no network, no credentials).
A single live-smoke test (`tests/test_live_smoke.py`) is skipped unless you set
`FAMLY_EMAIL` and `FAMLY_PASSWORD`; only ever run it against your own account.
CI runs the suite on Linux, macOS, and Windows across Python 3.11, 3.12, and
3.13, plus an install smoke test (`pip install .` then `famly --help`) on each
OS, for every pull request.

To try the tool in a clean Linux container (Docker or OrbStack), install the
published version and run it. The slim image has no git, so add it first:

```bash
docker run --rm -it python:3.11-slim bash -c \
  "apt-get update -qq && apt-get install -y -qq git && pip install git+https://github.com/shanegriffiths/famly-cli.git && famly --help"
```

To test your local working copy instead (no git needed, since pip installs from
the mounted directory):

```bash
docker run --rm -it -v "$PWD":/src -w /src python:3.11-slim bash -c \
  "pip install . && famly --help"
```

For an interactive shell to poke around, drop the `bash -c "..."`:

```bash
docker run --rm -it python:3.11-slim bash
```

## Test fixtures

The large fixtures (`tests/fixtures/feed_full.json` and
`observations_all_variants.json`) mirror real Famly API shapes but are scrubbed:
names and free text are redacted, all identifiers and image content-hashes are
zeroed, and dates are replaced with a synthetic constant.
`tests/fixtures/_build_fixtures.py` performs this scrub in place, and
`tests/test_fixtures.py` fails the build if any real identifier, image hash, or
non-synthetic date sneaks back in. If you add or update a fixture, scrub it the
same way and keep that guard passing.

## Making changes

- Match the surrounding code style. It is compact and deliberately
  dependency-light.
- Add or update tests for any behaviour change, and keep them offline.
- Treat the Famly API response as **untrusted input**. Anything that turns an
  API value into a filename, a filesystem path, a URL to fetch, or HTML in the
  generated gallery must sanitize or escape it. The relevant spots are
  `famly/models.py`, `famly/media.py`, `famly/export.py`, `famly/gallery.py`,
  and `famly/client.py`.
- Open a pull request with a clear description, and make sure `pytest` passes.

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
