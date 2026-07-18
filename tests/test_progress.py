from famly.progress import status, track


def test_status_writes_to_stderr_not_stdout(capsys):
    status("working…")
    out, err = capsys.readouterr()
    assert out == ""
    assert "working…" in err


def test_status_quiet_is_silent(capsys):
    status("working…", quiet=True)
    out, err = capsys.readouterr()
    assert out == "" and err == ""


def test_track_yields_all_items_and_keeps_stdout_clean(capsys):
    assert list(track([1, 2, 3], "Downloading")) == [1, 2, 3]
    out, _ = capsys.readouterr()
    assert out == ""


def test_track_quiet_is_pure_passthrough(capsys):
    assert list(track([1, 2, 3], "Downloading", quiet=True)) == [1, 2, 3]
    out, err = capsys.readouterr()
    assert out == "" and err == ""
