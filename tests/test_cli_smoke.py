from click.testing import CliRunner
from famly.cli import main

def test_help_lists_core_commands():
    res = CliRunner().invoke(main, ["--help"])
    assert res.exit_code == 0
    for cmd in ["login", "children", "feed", "messages", "events", "observations", "photos"]:
        assert cmd in res.output
