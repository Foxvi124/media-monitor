import os
from datetime import timezone

from monitor.feeds import fetch_feed, parse_date, parse_feed, strip_html

HERE = os.path.dirname(os.path.abspath(__file__))


def _read(name):
    with open(os.path.join(HERE, "fixtures", name), "rb") as f:
        return f.read()


def test_parse_rss():
    items = parse_feed(_read("sample_rss.xml"), "Fixture")
    assert len(items) == 3
    first = items[0]
    assert first.title.startswith("Smelter nikel")
    assert first.link == "https://example.com/smelter-nikel"
    assert "hilirisasi" in first.summary and "<" not in first.summary
    assert "&" in first.summary  # entity &amp; terurai
    assert first.published.tzinfo is not None


def test_parse_atom():
    items = parse_feed(_read("sample_atom.xml"), "Atom")
    assert len(items) == 2
    assert items[0].link == "https://example.com/startup-ai"
    assert items[1].link == "https://example.com/banjir"
    assert items[0].published.astimezone(timezone.utc).hour == 3


def test_parse_date_variants():
    assert parse_date("Sat, 01 Aug 2026 08:30:00 +0700").utcoffset().total_seconds() == 7 * 3600
    assert parse_date("2026-08-01T03:15:00Z").tzinfo is not None
    assert parse_date("bukan tanggal") is None
    assert parse_date("") is None


def test_strip_html():
    assert strip_html("<p>Halo <b>dunia</b> &amp; kawan</p>") == "Halo dunia & kawan"


def test_fetch_feed_error_is_captured():
    bad = fetch_feed("Rusak", "file:///tidak/ada/feed.xml")
    assert bad.error is not None and bad.items == []


def test_fetch_feed_file_url():
    url = "file://" + os.path.join(HERE, "fixtures", "sample_rss.xml")
    ok = fetch_feed("Fixture", url)
    assert ok.error is None and len(ok.items) == 3
