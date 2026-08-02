import pytest

from monitor.matcher import Topic, highlight, topics_from_config


def test_word_boundary():
    t = Topic(name="T", any=["nikel"])
    assert t.match("harga nikel naik") == ["nikel"]
    assert t.match("senyawa nikelin ditemukan") is None
    assert t.match("Nikel, timah, dan bauksit") == ["nikel"]


def test_phrase_and_case():
    t = Topic(name="T", any=["kecerdasan buatan"])
    assert t.match("Kecerdasan Buatan berkembang pesat") == ["kecerdasan buatan"]
    assert t.match("kecerdasan alami") is None


def test_exclude_and_all():
    t = Topic(name="T", any=["nikel"], exclude=["zodiak"])
    assert t.match("ramalan zodiak nikel") is None
    t2 = Topic(name="T2", all=["smelter", "nikel"])
    assert t2.match("smelter nikel dibangun") == ["smelter", "nikel"]
    assert t2.match("smelter tembaga dibangun") is None


def test_empty_topic_rejected():
    with pytest.raises(ValueError):
        Topic(name="kosong")


def test_topics_from_config():
    ts = topics_from_config([{"name": "A", "any": ["x"]}])
    assert ts[0].match("ada x di sini") == ["x"]


def test_highlight_preserves_case():
    out = highlight("Nikel dan nikel", ["nikel"])
    assert out == "**Nikel** dan **nikel**"
    out_html = highlight("nikel", ["nikel"], wrap=("<mark>", "</mark>"))
    assert out_html == "<mark>nikel</mark>"
