from monitor.opml import export_opml, import_opml, to_yaml_snippet


def test_roundtrip(tmp_path):
    feeds = [{"name": "BBC Indonesia", "url": "https://feeds.bbci.co.uk/indonesia/rss.xml"},
             {"name": "Media \"Aneh\" & Co", "url": "https://x/rss"}]
    p = tmp_path / "feeds.opml"
    p.write_text(export_opml(feeds), encoding="utf-8")
    back = import_opml(str(p))
    assert back == feeds
    snippet = to_yaml_snippet(back)
    assert snippet.startswith("feeds:") and "BBC Indonesia" in snippet
