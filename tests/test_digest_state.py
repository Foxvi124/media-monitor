import os
from datetime import datetime, timedelta, timezone

from monitor.digest import State, build_digest
from monitor.feeds import FeedResult, Item

NOW = datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc)


def _item(title="Judul", link="https://x/1", summary="ringkasan nikel"):
    return Item(title=title, link=link, summary=summary,
                published=NOW, source="Sumber")


def test_state_dedupe_and_prune(tmp_path):
    p = str(tmp_path / "state.json")
    s = State(p)
    it = _item()
    assert s.is_new(it)
    s.mark(it, NOW)
    s.save()
    s2 = State(p)
    assert not s2.is_new(it)
    s2.seen["lama"] = (NOW - timedelta(days=40)).isoformat()
    s2.prune(NOW)
    assert "lama" not in s2.seen and s2.key(it) in s2.seen


def test_build_digest_contents():
    matches = {"Topik A": [(_item(), ["nikel"])], "Topik B": []}
    feeds = [FeedResult("OK", "u"), FeedResult("Gagal", "v", error="HTTPError: 404")]
    md, html = build_digest(matches, date_label="2026-08-02",
                            generated_at="02 Aug 2026 05:00 WIB",
                            feeds=feeds, total_scanned=10)
    assert "## Topik A (1)" in md and "Topik B" not in md
    assert "[Judul](https://x/1)" in md and "**nikel**" in md
    assert "Gagal (HTTPError: 404)" in md
    assert "<mark>nikel</mark>" in html and "<h2>Topik A (1)</h2>" in html


def test_build_digest_empty():
    md, html = build_digest({"T": []}, date_label="d", generated_at="g",
                            feeds=[FeedResult("A", "u")], total_scanned=0)
    assert "Tidak ada berita" in md and "Tidak ada berita" in html
