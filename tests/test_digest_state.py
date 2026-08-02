from datetime import datetime, timedelta, timezone

from monitor.cluster import Cluster
from monitor.digest import State, build_digest
from monitor.feeds import FeedResult, Item

NOW = datetime(2026, 8, 2, 0, 0, tzinfo=timezone.utc)


def _item(title="Judul", link="https://x/1", summary="ringkasan nikel",
          source="Sumber"):
    return Item(title=title, link=link, summary=summary,
                published=NOW, source=source)


def _cluster(**kw):
    return Cluster(item=_item(**kw), keywords=["nikel"])


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


def test_state_feed_health(tmp_path):
    p = str(tmp_path / "state.json")
    s = State(p)
    for _ in range(3):
        s.record_feed("Mati", ok=False)
    s.record_feed("Sehat", ok=False)
    s.record_feed("Sehat", ok=True)  # sukses me-reset hitungan
    s.save()
    s2 = State(p)
    assert s2.stale_feeds() == ["Mati"]


def test_build_digest_contents():
    cl = _cluster()
    cl.also.append(_item(source="Media Lain", link="https://y/1"))
    clusters = {"Topik A": [cl], "Topik B": []}
    feeds = [FeedResult("OK", "u"), FeedResult("Gagal", "v", error="HTTPError: 404")]
    md, html = build_digest(clusters, date_label="2026-08-02",
                            generated_at="02 Aug 2026 05:00 WIB",
                            feeds=feeds, total_scanned=10,
                            topic_trend={"Topik A": "↑"},
                            stale_feeds=["Feed Zombi"])
    assert "## Topik A (1) ↑" in md and "Topik B" not in md
    assert "🔥 **[Judul](https://x/1)**" in md and "**nikel**" in md
    assert "diberitakan juga oleh: Media Lain" in md
    assert "Gagal (HTTPError: 404)" in md
    assert "Feed Zombi" in md
    assert "<mark>nikel</mark>" in html and "Topik A (1) ↑" in html
    assert "Media Lain" in html and "Feed Zombi" in html


def test_build_digest_empty():
    md, html = build_digest({"T": []}, date_label="d", generated_at="g",
                            feeds=[FeedResult("A", "u")], total_scanned=0)
    assert "Tidak ada berita" in md and "Tidak ada berita" in html
