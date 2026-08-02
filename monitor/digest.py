"""Penyimpanan state (anti-duplikat + kesehatan feed) dan perender digest."""

from __future__ import annotations

import html as html_lib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from .cluster import Cluster
from .feeds import FeedResult, Item
from .matcher import highlight

# --------------------------------- state ---------------------------------- #


class State:
    """Tautan yang sudah dilaporkan + hitungan kegagalan beruntun per feed."""

    def __init__(self, path: str):
        self.path = path
        self.seen: Dict[str, str] = {}
        self.feed_health: Dict[str, int] = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self.seen = data.get("seen", {})
                self.feed_health = data.get("feed_health", {})
            except (json.JSONDecodeError, OSError):
                pass

    @staticmethod
    def key(item: Item) -> str:
        return item.link or f"title:{item.title}"

    def is_new(self, item: Item) -> bool:
        return self.key(item) not in self.seen

    def mark(self, item: Item, now: datetime) -> None:
        self.seen[self.key(item)] = now.isoformat()

    def record_feed(self, name: str, ok: bool) -> int:
        """Catat sukses/gagalnya sebuah feed; kembalikan gagal-beruntun terkini."""
        self.feed_health[name] = 0 if ok else self.feed_health.get(name, 0) + 1
        return self.feed_health[name]

    def stale_feeds(self, threshold: int = 3) -> List[str]:
        return sorted(n for n, c in self.feed_health.items() if c >= threshold)

    def prune(self, now: datetime, keep_days: int = 21) -> None:
        limit = now - timedelta(days=keep_days)
        kept = {}
        for k, ts in self.seen.items():
            try:
                if datetime.fromisoformat(ts) >= limit:
                    kept[k] = ts
            except ValueError:
                pass
        self.seen = kept

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"seen": self.seen, "feed_health": self.feed_health},
                      f, ensure_ascii=False, indent=1)


# --------------------------------- digest --------------------------------- #

_HTML_HEAD = """<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><style>
body{{font-family:Georgia,'Times New Roman',serif;max-width:760px;margin:0 auto;
padding:28px 18px;color:#22303c;background:#fbfaf7;line-height:1.55}}
h1{{font-size:26px;border-bottom:3px double #22303c;padding-bottom:10px}}
h2{{font-size:19px;margin-top:30px;color:#1d4e6b}}
.meta{{color:#6b7683;font-size:13px}} .item{{margin:14px 0 18px}}
.item a{{color:#0b5d8a;text-decoration:none;font-weight:bold}}
.item a:hover{{text-decoration:underline}}
.snippet{{margin:5px 0 0;color:#41505d;font-size:15px}}
.also{{color:#6b7683;font-size:13px;font-style:italic}}
mark{{background:#ffe9a8;padding:0 2px}}
footer{{margin-top:36px;border-top:1px solid #cfd6dc;padding-top:10px;
color:#6b7683;font-size:12px}}
</style></head><body>
"""


def _fmt_time(item: Item, tzinfo: timezone, tz_label: str) -> str:
    if not item.published:
        return ""
    return item.published.astimezone(tzinfo).strftime(f"%d %b %H:%M {tz_label}")


def build_digest(
    clusters_by_topic: Dict[str, List[Cluster]],
    *,
    date_label: str,
    generated_at: str,
    feeds: List[FeedResult],
    total_scanned: int,
    snippet_chars: int = 220,
    tz: timezone = timezone.utc,
    tz_label: str = "UTC",
    topic_trend: Optional[Dict[str, str]] = None,
    stale_feeds: Optional[List[str]] = None,
) -> Tuple[str, str]:
    """Kembalikan (markdown, html) untuk satu digest harian."""
    topic_trend = topic_trend or {}
    stale_feeds = stale_feeds or []
    total_matched = sum(len(v) for v in clusters_by_topic.values())
    ok_feeds = [f for f in feeds if f.error is None]
    err_feeds = [f for f in feeds if f.error is not None]

    md: List[str] = [f"# 📰 Digest Media — {date_label}", ""]
    md.append(f"_{total_matched} berita cocok · {total_scanned} artikel dipindai "
              f"dari {len(ok_feeds)} feed · dibuat {generated_at}_")
    md.append("")

    hp: List[str] = [_HTML_HEAD.format(title=f"Digest Media — {date_label}")]
    hp.append(f"<h1>📰 Digest Media — {html_lib.escape(date_label)}</h1>")
    hp.append(f'<p class="meta">{total_matched} berita cocok · {total_scanned} '
              f"artikel dipindai dari {len(ok_feeds)} feed · dibuat "
              f"{html_lib.escape(generated_at)}</p>")

    if total_matched == 0:
        md += ["Tidak ada berita yang cocok dengan topik hari ini.", ""]
        hp.append("<p>Tidak ada berita yang cocok dengan topik hari ini.</p>")

    for topic, clusters in clusters_by_topic.items():
        if not clusters:
            continue
        arrow = topic_trend.get(topic, "")
        head = f"{topic} ({len(clusters)})" + (f" {arrow}" if arrow else "")
        md += [f"## {head}", ""]
        hp.append(f"<h2>{html_lib.escape(head)}</h2>")
        for cl in clusters:
            item, kws = cl.item, cl.keywords
            fire = "🔥 " if cl.hot else ""
            waktu = _fmt_time(item, tz, tz_label)
            info = " · ".join(x for x in [item.source, waktu] if x)
            snippet = item.summary[:snippet_chars].rstrip()
            if len(item.summary) > snippet_chars:
                snippet += "…"
            md.append(f"- {fire}**[{item.title}]({item.link})** — {info} · "
                      f"kata kunci: {', '.join(f'**{k}**' for k in kws)}")
            if cl.also_sources:
                md.append(f"  _diberitakan juga oleh: "
                          f"{', '.join(cl.also_sources)}_")
            if snippet:
                md.append(f"  > {highlight(snippet, kws)}")
            hp.append('<div class="item">')
            hp.append(f'{fire}<a href="{html_lib.escape(item.link, quote=True)}">'
                      f"{html_lib.escape(item.title)}</a>"
                      f'<div class="meta">{html_lib.escape(info)} · kata kunci: '
                      f"{html_lib.escape(', '.join(kws))}</div>")
            if cl.also_sources:
                hp.append(f'<div class="also">diberitakan juga oleh: '
                          f"{html_lib.escape(', '.join(cl.also_sources))}</div>")
            if snippet:
                esc = highlight(html_lib.escape(snippet), kws,
                                wrap=("<mark>", "</mark>"))
                hp.append(f'<p class="snippet">{esc}</p>')
            hp.append("</div>")
        md.append("")

    md.append("---")
    foot_html: List[str] = []
    if err_feeds:
        md.append(f"⚠ {len(err_feeds)} feed gagal diambil: "
                  + "; ".join(f"{f.name} ({f.error})" for f in err_feeds))
        foot_html.append("⚠ Feed gagal: " + html_lib.escape(
            "; ".join(f"{f.name} ({f.error})" for f in err_feeds)))
    if stale_feeds:
        md.append(f"💀 Feed diduga mati (gagal ≥3 run beruntun): "
                  + ", ".join(stale_feeds) + " — periksa/ganti URL-nya.")
        foot_html.append("💀 Feed diduga mati: "
                         + html_lib.escape(", ".join(stale_feeds)))
    md.append("_Dibuat otomatis oleh [media-monitor](https://github.com/"
              "Foxvi124/media-monitor)._")
    foot_html.append("Dibuat otomatis oleh media-monitor.")
    hp.append("<footer>" + "<br>".join(foot_html) + "</footer></body></html>")
    return "\n".join(md) + "\n", "\n".join(hp) + "\n"
