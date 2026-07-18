"""Human-facing progress output.

Everything here writes to STDERR only. Command *results* (JSON / tables) go to
stdout via ``output.emit``. Keeping progress on stderr means piping the CLI or
parsing its stdout as JSON stays clean — the same split the ``_safe``
warnings in ``photos`` already rely on.
"""
import sys

import click


def status(msg: str, quiet: bool = False) -> None:
    """Print one progress line to stderr, unless quiet."""
    if not quiet:
        click.echo(msg, err=True)


def track(items, label: str, quiet: bool = False):
    """Iterate ``items`` while showing a progress bar on stderr.

    When quiet — or when stderr isn't a TTY — nothing is rendered and this is a
    plain pass-through, so scripted and agent use is unaffected. ``items`` must
    be a sized sequence (e.g. a list) so the bar can show a percentage.
    """
    if quiet:
        yield from items
        return
    with click.progressbar(items, label=label, file=sys.stderr) as bar:
        yield from bar
