from datetime import date, timedelta

from monitor.trends import (load_history, record_run, svg_stacked_bars,
                            topic_daily_average, trend_arrow, weekly_report)


def _seed(path):
    for i in range(7):  # 2026-07-26 .. 2026-08-01
        d = (date(2026, 7, 26) + timedelta(days=i)).isoformat()
        record_run(path, d, {"Tambang": i + 1, "Iklim": 1}, {"nikel": i + 1})


def test_record_merges_same_date(tmp_path):
    p = str(tmp_path / "history.json")
    record_run(p, "2026-08-01", {"A": 2}, {"x": 2})
    record_run(p, "2026-08-01", {"A": 3}, {"x": 1})
    runs = load_history(p)
    assert len(runs) == 1
    assert runs[0]["topics"]["A"] == 5 and runs[0]["keywords"]["x"] == 3


def test_average_and_arrow(tmp_path):
    p = str(tmp_path / "history.json")
    _seed(p)
    runs = load_history(p)
    avg = topic_daily_average(runs, "Tambang", date(2026, 8, 2))
    assert avg == (1 + 2 + 3 + 4 + 5 + 6 + 7) / 7
    assert trend_arrow(10, avg) == "↑"
    assert trend_arrow(1, avg) == "↓"
    assert trend_arrow(4, avg) == "→"
    assert trend_arrow(5, None) == ""
    assert topic_daily_average(runs[:2], "Tambang", date(2026, 8, 2)) is None


def test_weekly_report(tmp_path):
    p = str(tmp_path / "history.json")
    _seed(p)
    week_name, md, svg = weekly_report(p, date(2026, 8, 1))
    assert week_name == "2026-W31"
    assert "| Tambang | 28 | 0 | baru |" in md
    assert "nikel (28)" in md
    assert svg.startswith("<svg") and svg.count("<rect") > 7


def test_weekly_report_empty(tmp_path):
    p = str(tmp_path / "history.json")
    _, md, svg = weekly_report(p, date(2026, 8, 1))
    assert "Belum ada data" in md and svg.startswith("<svg")
