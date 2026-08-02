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


def test_end_to_end(tmp_path, capsys):
    cfg = _config(tmp_path)
    out = str(tmp_path / "digests")
    state = str(tmp_path / "state.json")

    code = run(["--config", cfg, "--output", out, "--state", state])
    assert code == 0
    latest = open(os.path.join(out, "latest.md"), encoding="utf-8").read()
    # cocok: smelter-nikel (RSS), startup-ai & banjir (Atom); zodiak tereksklusi
    assert "Smelter nikel baru" in latest
    assert "Startup AI lokal" in latest and "Banjir rob" in latest
    assert "zodiak" not in latest.split("Feed gagal")[0].split("⚠")[0]
    assert "1 feed gagal diambil" in latest
    assert os.path.exists(os.path.join(out, "latest.html"))

    # run kedua: state mencegah duplikat → digest kosong
    code = run(["--config", cfg, "--output", out, "--state", state])
    assert code == 0
    latest2 = open(os.path.join(out, "latest.md"), encoding="utf-8").read()
    assert "Tidak ada berita yang cocok" in latest2
