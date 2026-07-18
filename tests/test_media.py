from famly.models import MediaRef
from famly.media import full_res_url

def test_full_res_url_reconstructs_from_prefix_key_dims():
    img = {"prefix": "https://img.famly.co/image/HASH", "key": "archive/x/y.jpg?expires=Z",
           "width": 1920, "height": 2560, "url": "https://img.famly.co/image/HASH/600x800/archive/x/y.jpg?expires=Z"}
    assert full_res_url(img) == "https://img.famly.co/image/HASH/1920x2560/archive/x/y.jpg?expires=Z"

def test_full_res_url_falls_back_to_url_when_no_prefix():
    assert full_res_url({"url": "https://img/x.jpg"}) == "https://img/x.jpg"

def test_full_res_url_swaps_downscaled_size_to_native():
    img = {"url": "https://img.famly.co/image/H/1080x1920/a.jpg?expires=Z",
           "width": 1920, "height": 2560}
    assert full_res_url(img) == "https://img.famly.co/image/H/1920x2560/a.jpg?expires=Z"

def test_filename_is_dated_sourced_and_extensioned():
    r = MediaRef(id="abcd1234efgh", url="https://x/y.jpg", kind="image", width=1, height=1,
                 source="feed", date="2026-01-09T08:00:00Z")
    assert r.filename(3) == "2026-01-09_03_feed_abcd1234.jpg"

def test_filename_file_kind_does_not_masquerade_as_jpg():
    r = MediaRef(id="abcd1234efgh", url="https://x/download", kind="file",
                 source="message", date="2026-01-09T08:00:00Z")
    assert r.filename(1).endswith(".bin")
