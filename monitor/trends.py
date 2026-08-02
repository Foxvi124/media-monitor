"""Riwayat run, tren 7 hari, rekap mingguan, dan grafik SVG murni-Python."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

_PALETTE = ["#0b5d8a", "#e09a2f", "#3d7a4a", "#a04a4a", "#6b5b95", "#7a7a3d",
            "#3d6b7a", "#8a5d0b"]


# --------------------------------- riwayat --------------------------------- #

def load_history(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("runs", [])
    except (json.JSONDecodeError, OSError):
        return []


def record_run(path: str, date_str: str, topic_counts: Dict[str, int],
               keyword_counts: Dict[str, int]) -> None:
    """Catat hasil run hari ini; run ulang di hari yang sama dijumlahkan
    (aman karena state.json sudah mencegah artikel dihitung dua kali)."""
    runs = load_history(path)
    entry = next((r for r in runs if r.get("date") == date_str), None)
    if entry is None:
        entry = {"date": date_str, "topics": {}, "keywords": {}}
        runs.append(entry)
    for name, n in topic_counts.items():
        entry["topics"][name] = entry["topics"].get(name, 0) + n
    for kw, n in keyword_counts.items():
        entry["keywords"][kw] = entry["keywords"].get(kw, 0) + n
    runs.sort(key=lambda r: r.get("date", ""))
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"runs": runs}, f, ensure_ascii=False, indent=1)


def _window(runs: List[dict], end: date, days: int) -> List[dict]:
    start = end - timedelta(days=days - 1)
    out = []
    for r in runs:
        try:
            d = date.fromisoformat(r["date"])
        except (KeyError, ValueError):
            continue
        if start <= d <= end:
            out.append(r)
    return out


def topic_daily_average(runs: List[dict], topic: str, end: date,
                        days: int = 7) -> Optional[float]:
    """Rata-rata artikel/hari untuk satu topik pada `days` hari SEBELUM `end`.
    None bila riwayat < 3 hari (belum layak dijadikan pembanding)."""
    window = _window(runs, end - timedelta(days=1), days)
    if len(window) < 3:
        return None
    total = sum(r["topics"].get(topic, 0) for r in window)
    return total / days


def trend_arrow(today: int, avg: Optional[float]) -> str:
    if avg is None:
        return ""
    if today > avg * 1.3:
        return "↑"
    if today < avg * 0.7:
        return "↓"
    return "→"


# ----------------------------- rekap mingguan ------------------------------ #

def svg_stacked_bars(days: List[str], series: Dict[str, List[int]],
                     width: int = 720, height: int = 260) -> str:
    """Grafik batang bertumpuk (artikel per hari per topik), tanpa dependensi."""
    topics = list(series.keys())
    pad_l, pad_b, pad_t = 36, 34, 24 + 16 * ((len(topics) + 2) // 3)
    plot_w, plot_h = width - pad_l - 12, height - pad_t - pad_b
    totals = [sum(series[t][i] for t in topics) for i in range(len(days))]
    peak = max(totals + [1])
    bar_w = plot_w / max(len(days), 1) * 0.58

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
             f'height="{height}" font-family="sans-serif" font-size="11">',
             f'<rect width="{width}" height="{height}" fill="#fbfaf7"/>']
    for i, t in enumerate(topics):  # legenda
        lx = 12 + (i % 3) * ((width - 24) // 3)
        ly = 14 + (i // 3) * 16
        col = _PALETTE[i % len(_PALETTE)]
        parts.append(f'<rect x="{lx}" y="{ly - 9}" width="10" height="10" '
                     f'fill="{col}"/>')
        parts.append(f'<text x="{lx + 14}" y="{ly}">{t[:28]}</text>')
    for i, day in enumerate(days):  # batang
        x = pad_l + plot_w * (i + 0.5) / len(days) - bar_w / 2
        y = height - pad_b
        for j, t in enumerate(topics):
            v = series[t][i]
            if v <= 0:
                continue
            h = plot_h * v / peak
            y -= h
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                f'height="{h:.1f}" fill="{_PALETTE[j % len(_PALETTE)]}"/>'
            )
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{height - pad_b + 14}" '
                     f'text-anchor="middle">{day[5:]}</text>')
        if totals[i]:
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 4:.1f}" '
                         f'text-anchor="middle" fill="#41505d">{totals[i]}</text>')
    parts.append(f'<line x1="{pad_l}" y1="{height - pad_b}" x2="{width - 12}" '
                 f'y2="{height - pad_b}" stroke="#22303c"/>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def weekly_report(history_path: str, end: date,
                  tz_label: str = "WIB") -> Tuple[str, str, str]:
    """Kembalikan (nama_pekan, markdown, svg) rekap 7 hari yang berakhir di `end`."""
    runs = load_history(history_path)
    week = _window(runs, end, 7)
    prev = _window(runs, end - timedelta(days=7), 7)
    days = [(end - timedelta(days=6 - i)).isoformat() for i in range(7)]
    by_date = {r["date"]: r for r in week}

    topics = sorted({t for r in week for t in r.get("topics", {})})
    series = {t: [by_date.get(d, {}).get("topics", {}).get(t, 0) for d in days]
              for t in topics}
    week_name = f"{end.isocalendar()[0]}-W{end.isocalendar()[1]:02d}"

    md = [f"# 📈 Rekap Mingguan — {week_name} "
          f"({days[0]} s.d. {days[-1]}, {tz_label})", ""]
    if not week:
        md.append("Belum ada data pada pekan ini.")
        return week_name, "\n".join(md) + "\n", svg_stacked_bars(days, {})

    md.append(f"![grafik mingguan](mingguan-{week_name}.svg)")
    md.append("")
    md.append("| topik | artikel | pekan lalu | perubahan |")
    md.append("|---|---|---|---|")
    for t in topics:
        now_n = sum(series[t])
        prev_n = sum(r.get("topics", {}).get(t, 0) for r in prev)
        if prev_n:
            delta = f"{(now_n - prev_n) / prev_n * 100:+.0f}%"
        else:
            delta = "baru" if now_n else "—"
        md.append(f"| {t} | {now_n} | {prev_n} | {delta} |")
    md.append("")

    kw_tot: Dict[str, int] = {}
    for r in week:
        for kw, n in r.get("keywords", {}).items():
            kw_tot[kw] = kw_tot.get(kw, 0) + n
    top = sorted(kw_tot.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    if top:
        md.append("**Kata kunci terpanas:** "
                  + ", ".join(f"{kw} ({n})" for kw, n in top))
        md.append("")
    md.append("_Dibuat otomatis oleh media-monitor dari history.json._")
    return week_name, "\n".join(md) + "\n", svg_stacked_bars(days, series)
