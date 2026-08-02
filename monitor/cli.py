"""CLI utama: baca config.yaml → ambil feed → cocokkan topik → tulis digest."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import yaml

from .digest import Match, State, build_digest
from .feeds import FeedResult, fetch_feed
from .matcher import topics_from_config


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if not cfg.get("feeds"):
        sys.exit("config: daftar 'feeds' kosong.")
    if not cfg.get("topics"):
        sys.exit("config: daftar 'topics' kosong.")
    return cfg


def run(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="media-monitor",
        description="Pantau kata kunci di feed RSS/Atom dan hasilkan digest harian.",
    )
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--output", default="digests", help="folder keluaran digest")
    ap.add_argument("--state", default="state.json", help="berkas anti-duplikat")
    ap.add_argument("--dry-run", action="store_true",
                    help="cetak digest ke layar tanpa menulis file/state")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    off = int(cfg.get("utc_offset_hours", 7))
    tz = timezone(timedelta(hours=off))
    tz_label = str(cfg.get("tz_label", "WIB"))
    max_age = int(cfg.get("max_age_hours", 36))  # 0 = tanpa batas umur
    limit = int(cfg.get("limit_per_topic", 25))
    snippet_chars = int(cfg.get("snippet_chars", 220))

    now = datetime.now(timezone.utc)
    topics = topics_from_config(cfg["topics"])
    state = State(args.state)

    # 1) ambil seluruh feed
    results: List[FeedResult] = [
        fetch_feed(str(f.get("name", f.get("url"))), str(f["url"]))
        for f in cfg["feeds"]
    ]
    scanned = 0

    # 2) saring umur + duplikat, lalu cocokkan topik
    matches: Dict[str, List[Match]] = {t.name: [] for t in topics}
    for fr in results:
        for item in fr.items:
            scanned += 1
            if max_age and item.published and \
               item.published < now - timedelta(hours=max_age):
                continue
            if not state.is_new(item):
                continue
            text = f"{item.title}\n{item.summary}"
            hit_any_topic = False
            for topic in topics:
                kws = topic.match(text)
                if kws and len(matches[topic.name]) < limit:
                    matches[topic.name].append((item, kws))
                    hit_any_topic = True
            if hit_any_topic:
                state.mark(item, now)

    for name in matches:  # terbaru dulu
        matches[name].sort(
            key=lambda m: m[0].published or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )

    # 3) render + tulis
    local_now = now.astimezone(tz)
    date_label = local_now.strftime("%Y-%m-%d")
    generated_at = local_now.strftime(f"%d %b %Y %H:%M {tz_label}")
    md, html_out = build_digest(
        matches, date_label=date_label, generated_at=generated_at,
        feeds=results, total_scanned=scanned, snippet_chars=snippet_chars,
        tz=tz, tz_label=tz_label,
    )

    if args.dry_run:
        print(md)
    else:
        os.makedirs(args.output, exist_ok=True)
        day_path = os.path.join(args.output, f"digest-{date_label}.md")
        with open(day_path, "w", encoding="utf-8") as f:
            f.write(md)
        with open(os.path.join(args.output, "latest.md"), "w",
                  encoding="utf-8") as f:
            f.write(md)
        with open(os.path.join(args.output, "latest.html"), "w",
                  encoding="utf-8") as f:
            f.write(html_out)
        state.prune(now)
        state.save()
        print(f"digest ditulis: {day_path}")

    matched = sum(len(v) for v in matches.values())
    errs = sum(1 for r in results if r.error)
    print(f"{matched} artikel cocok · {scanned} dipindai · "
          f"{len(results) - errs}/{len(results)} feed sukses")
    return 0


def main() -> None:
    sys.exit(run())
