import json
import os

import yaml

from monitor.cli import run

HERE = os.path.dirname(os.path.abspath(__file__))


def _config(tmp_path):
    cfg = {
        "utc_offset_hours": 7,
        "tz_label": "WIB",
        "max_age_hours": 0,  # fixture berisi tanggal tetap
        "feeds": [
            {"name": "RSS Fixture",
             "url": "file://" + os.path.join(HERE, "fixtures", "sample_rss.xml")},
            {"name": "Atom Fixture",
             "url": "file://" + os.path.join(HERE, "fixtures", "sample_atom.xml")},
            {"name": "Feed Mati", "url": "file:///tidak/ada.xml"},
        ],
        "topics": [
            {"name": "Pertambangan", "any": ["nikel", "smelter"],
             "exclude": ["zodiak"]},
            {"name": "Teknologi", "any": ["kecerdasan buatan", "pusat data"]},
            {"name": "Iklim", "any": ["iklim", "banjir"]},
        ],
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return str(path)


def _args(tmp_path, cfg):
    return ["--config", cfg,
            "--output", str(tmp_path / "digests"),
            "--state", str(tmp_path / "state.json"),
            "--history", str(tmp_path / "history.json")]


def test_end_to_end(tmp_path):
    cfg = _config(tmp_path)
    out = str(tmp_path / "digests")

    assert run(_args(tmp_path, cfg)) == 0
    latest = open(os.path.join(out, "latest.md"), encoding="utf-8").read()
    # cocok: smelter-nikel (RSS), startup-ai & banjir (Atom); zodiak tereksklusi
    assert "Smelter nikel baru" in latest
    assert "Startup AI lokal" in latest and "Banjir rob" in latest
    assert "zodiak" not in latest.split("⚠")[0]
    assert "1 feed gagal diambil" in latest
    assert os.path.exists(os.path.join(out, "latest.html"))

    data = json.load(open(os.path.join(out, "latest.json"), encoding="utf-8"))
    assert {t["name"] for t in data["topics"]} == {"Pertambangan", "Teknologi",
                                                   "Iklim"}
    assert any(not f["ok"] for f in data["feeds"])

    hist = json.load(open(str(tmp_path / "history.json"), encoding="utf-8"))
    assert hist["runs"][0]["topics"]["Pertambangan"] == 1

    # run kedua: state mencegah duplikat → digest kosong, riwayat tak bertambah
    assert run(_args(tmp_path, cfg)) == 0
    latest2 = open(os.path.join(out, "latest.md"), encoding="utf-8").read()
    assert "Tidak ada berita yang cocok" in latest2
    hist2 = json.load(open(str(tmp_path / "history.json"), encoding="utf-8"))
    assert hist2["runs"][0]["topics"]["Pertambangan"] == 1


def test_check_and_weekly_and_opml(tmp_path, capsys):
    cfg = _config(tmp_path)

    assert run(["--config", cfg, "--check"]) == 0
    out = capsys.readouterr().out
    assert "✓ RSS Fixture: 3 artikel" in out and "✗ Feed Mati" in out

    # weekly setelah satu run harian
    assert run(_args(tmp_path, cfg)) == 0
    assert run(_args(tmp_path, cfg) + ["--weekly"]) == 0
    files = os.listdir(tmp_path / "digests")
    assert any(f.startswith("mingguan-") and f.endswith(".md") for f in files)
    assert any(f.endswith(".svg") for f in files)

    # ekspor lalu impor OPML
    opml = str(tmp_path / "feeds.opml")
    assert run(["--config", cfg, "--export-opml", opml]) == 0
    assert run(["--import-opml", opml]) == 0
    out = capsys.readouterr().out
    assert "feeds:" in out and "RSS Fixture" in out
