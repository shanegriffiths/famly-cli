from famly.gallery import render


def test_render_embeds_cards_and_filters():
    html = render([{"file": "2026-01-01_01_feed_x.jpg", "id": "x", "source": "feed",
                    "date": "2026-01-01T00:00:00Z", "author": "L", "caption": "hi", "w": 1, "h": 1, "ref": "r"}])
    assert "2026-01-01_01_feed_x.jpg" in html
    assert "Observations" in html and "Newsfeed" in html  # filter buttons
    assert html.strip().startswith("<!DOCTYPE html>")


def test_gallery_dates_are_timezone_independent():
    """Month grouping and display dates must come from the ISO string in the
    manifest, not the viewer's local clock — otherwise the same manifest files
    a 23:30Z photo under different months on different machines."""
    html = render([{"file": "a.jpg", "id": "x", "source": "feed",
                    "date": "2026-06-30T23:30:00Z", "author": "", "caption": "",
                    "w": 1, "h": 1, "ref": "r"}])
    for local_time_api in ("getFullYear(", "getMonth(", "toLocaleDateString("):
        assert local_time_api not in html


def test_gallery_escapes_script_breakout():
    rec = {"file": "a.jpg", "id": "x", "source": "feed",
           "date": "2026-01-01T00:00:00Z",
           "caption": "</script><script>alert(1)</script>",
           "author": "<!--<script>alert(2)</script>-->", "w": 1, "h": 1, "ref": "r"}
    out = render([rec])
    # Only the ONE real closing </script> tag may appear; the injected ones must be neutralized.
    assert out.lower().count("</script") == 1
    # And the injected comment-open must not survive as a raw sequence in the data payload.
    assert "<!--<script" not in out


def test_gallery_coerces_dimensions_to_numbers():
    """Image width/height are server-controlled and reach innerHTML directly, so
    the renderer must coerce them to numbers (+r.w) — otherwise markup in a
    dimension field would execute as stored XSS in the opened gallery."""
    out = render([])
    assert "(+r.w||'?')" in out and "(+r.h||'?')" in out
    assert "(r.w||'?')" not in out and "(r.h||'?')" not in out
