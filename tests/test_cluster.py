from datetime import datetime, timezone

from monitor.cluster import cluster_matches, similarity
from monitor.feeds import Item

NOW = datetime(2026, 8, 2, tzinfo=timezone.utc)


def _it(title, source, link):
    return Item(title=title, link=link, summary="", published=NOW, source=source)


def test_similarity():
    assert similarity("Smelter nikel diresmikan di Sulawesi",
                      "Smelter nikel di Sulawesi diresmikan hari ini") > 0.55
    assert similarity("Harga emas naik", "Banjir melanda Jakarta") == 0.0


def test_cluster_merges_same_story():
    a = _it("Smelter nikel diresmikan di Sulawesi", "Media A", "https://a/1")
    b = _it("Smelter nikel di Sulawesi diresmikan hari ini", "Media B", "https://b/1")
    c = _it("Resep rendang untuk pemula", "Media C", "https://c/1")
    clusters = cluster_matches([(a, ["nikel"]), (b, ["smelter"]), (c, ["rendang"])])
    assert len(clusters) == 2
    top = clusters[0]
    assert top.hot and top.score >= 2
    assert set(top.keywords) == {"nikel", "smelter"}
    assert top.also_sources in (["Media A"], ["Media B"])  # salah satu jadi primer


def test_cluster_hot_by_keywords():
    a = _it("Hilirisasi nikel dipercepat", "Media A", "https://a/2")
    clusters = cluster_matches([(a, ["hilirisasi", "nikel"])])
    assert clusters[0].hot
    b = _it("Berita biasa saja", "Media B", "https://b/2")
    clusters2 = cluster_matches([(b, ["biasa"])])
    assert not clusters2[0].hot
