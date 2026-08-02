"""CLI utama: run harian, --check, --weekly, --import-opml, --export-opml."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Tuple

import yaml

from . import __version__
from .cluster import Cluster, cluster_matches
from .digest import State, build_digest
from .feeds import FeedResult, Item, fetch_feed
from .matcher import topics_from_config
from .notify import digest_summary_text, notify_all
from .opml import export_opml, import_opml, to_yaml_snippet
from .trends import record_run, load_history, topic_daily_average, trend_arrow, \
    weekly_report


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    if not cfg.get("feeds"):
        sys.exit("config: daftar 'feeds' kosong.")
    if not cfg.get("topics"):
        sys.exit("config: daftar 'topics' kosong.")
    return cfg


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="media-monitor",
        description="Pantau kata kunci di feed RSS/Atom, hasilkan digest harian, "
                    "rekap mingguan, dan notifikasi.",
    )
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--output", default="digests")
    ap.add_argument("--state", default="state.json")
    ap.add_argument("--history", default="history.json")
    ap.add_argument("--dry-run", action="store_true",
                    help="cetak digest ke layar tanpa menulis file/state")
    ap.add_argument("--version", action="version", version=__version__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="uji setiap feed di config lalu keluar")
    mode.add_argument("--weekly", action="store_true",
                      help="buat rekap mingguan dari history.json")
    mode.add_argument("--import-opml", metavar="FILE",
                      help="baca OPML → cetak potongan YAML 'feeds:'")
    mode.add_argument("--export-opml", metavar="FILE",
                      help="tulis daftar feed config ke berkas OPML")
    return ap


# ------------------------------- sub-perintah ------------------------------ #

def cmd_check(cfg: dict) -> int:
    print(f"memeriksa {len(cfg['feeds'])} feed…")
    bad = 0
    for f in cfg["feeds"]:
        fr = fetch_feed(str(f.get("name", f.get("url"))), str(f["url"]))
        if fr.error:
            bad += 1
            print(f"  ✗ {fr.name}: {fr.error}")
        else:
            print(f"  ✓ {fr.name}: {len(fr.items)} artikel")
    print(f"selesai: {len(cfg['feeds']) - bad} sehat, {bad} bermasalah")
    return 0


def cmd_weekly(cfg: dict, args: argparse.Namespace) -> int:
    off = int(cfg.get("utc_offset_hours", 7))
    today = datetime.now(timezone(timedelta(hours=off))).date()
    week_name, md, svg = weekly_report(
        args.history, today, tz_label=str(cfg.get("tz_label", "WIB")))
    if args.dry_run:
        print(md)
        return 0
    os.makedirs(args.output, exist_ok=True)
    md_path = os.path.join(args.output, f"mingguan-{week_name}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(args.output, f"mingguan-{week_name}.svg"),
              "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"rekap mingguan ditulis: {md_path}")
    return 0


def cmd_import_opml(path: str) -> int:
    feeds = import_opml(path)
    if not feeds:
        print("tidak ada feed di OPML tersebut.")
        return 1
    print(f"# {len(feeds)} feed dari {os.path.basename(path)} — "
          "tempel ke config.yaml:")
    print(to_yaml_snippet(feeds), end="")
    return 0


def cmd_export_opml(cfg: dict, path: str) -> int:
    with open(path, "w", encoding="utf-8") as f:
        f.write(export_opml(cfg["feeds"]))
    print(f"OPML ditulis: {path} ({len(cfg['feeds'])} feed)")
    return 0


# --------------------------------- run harian ------------------------------ #

def _latest_json(clusters_by_topic: Dict[str, List[Cluster]],
                 feeds: List[FeedResult], date_label: str,
                 generated_at: str) -> dict:
    def item_dict(it: Item, kws: List[str], also: List[Item]) -> dict:
        return {
            "title": it.title, "link": it.link, "source": it.source,
            "published": it.published.isoformat() if it.published else None,
            "keywords": kws,
            "also_reported_by": [{"source": a.source, "link": a.link}
                                 for a in also],
        }

    return {
        "date": date_label, "generated_at": generated_at,
        "topics": [
            {"name": name,
             "items": [item_dict(c.item, c.keywords, c.also) for c in cls]}
            for name, cls in clusters_by_topic.items() if cls
        ],
        "feeds": [{"name": f.name, "ok": f.error is None, "error": f.error}
                  for f in feeds],
    }


def cmd_daily(cfg: dict, args: argparse.Namespace) -> int:
    off = int(cfg.get("utc_offset_hours", 7))
    tz = timezone(timedelta(hours=off))
    tz_label = str(cfg.get("tz_label", "WIB"))
    max_age = int(cfg.get("max_age_hours", 36))
    limit = int(cfg.get("limit_per_topic", 25))
    snippet_chars = int(cfg.get("snippet_chars", 220))
    threshold = float(cfg.get("cluster_threshold", 0.55))

    now = datetime.now(timezone.utc)
    topics = topics_from_config(cfg["topics"])
    state = State(args.state)

    results: List[FeedResult] = []
    for f in cfg["feeds"]:
        fr = fetch_feed(str(f.get("name", f.get("url"))), str(f["url"]))
        state.record_feed(fr.name, fr.error is None)
        results.append(fr)

    scanned = 0
    raw: Dict[str, List[Tuple[Item, List[str]]]] = {t.name: [] for t in topics}
    for fr in results:
        for item in fr.items:
            scanned += 1
            if max_age and item.published and \
               item.published < now - timedelta(hours=max_age):
                continue
            if not state.is_new(item):
                continue
            text = f"{item.title}\n{item.summary}"
            hit = False
            for topic in topics:
                kws = topic.match(text)
                if kws:
                    raw[topic.name].append((item, kws))
                    hit = True
            if hit:
                state.mark(item, now)

    clusters_by_topic = {
        name: cluster_matches(pairs, threshold=threshold)[:limit]
        for name, pairs in raw.items()
    }

    # tren: bandingkan dengan rata-rata 7 hari SEBELUM hari ini
    local_now = now.astimezone(tz)
    date_label = local_now.strftime("%Y-%m-%d")
    runs = load_history(args.history)
    topic_trend = {}
    for name, cls in clusters_by_topic.items():
        avg = topic_daily_average(runs, name, date.fromisoformat(date_label))
        arrow = trend_arrow(len(cls), avg)
        if arrow:
            topic_trend[name] = arrow

    generated_at = local_now.strftime(f"%d %b %Y %H:%M {tz_label}")
    md, html_out = build_digest(
        clusters_by_topic, date_label=date_label, generated_at=generated_at,
        feeds=results, total_scanned=scanned, snippet_chars=snippet_chars,
        tz=tz, tz_label=tz_label, topic_trend=topic_trend,
        stale_feeds=state.stale_feeds(),
    )

    if args.dry_run:
        print(md)
    else:
        os.makedirs(args.output, exist_ok=True)
        day_path = os.path.join(args.output, f"digest-{date_label}.md")
        for path, content in [
            (day_path, md),
            (os.path.join(args.output, "latest.md"), md),
            (os.path.join(args.output, "latest.html"), html_out),
        ]:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
        with open(os.path.join(args.output, "latest.json"), "w",
                  encoding="utf-8") as f:
            json.dump(_latest_json(clusters_by_topic, results, date_label,
                                   generated_at), f, ensure_ascii=False, indent=1)
        state.prune(now)
        state.save()
        kw_counts: Dict[str, int] = {}
        for cls in clusters_by_topic.values():
            for c in cls:
                for kw in c.keywords:
                    kw_counts[kw] = kw_counts.get(kw, 0) + 1
        record_run(args.history, date_label,
                   {n: len(c) for n, c in clusters_by_topic.items()}, kw_counts)
        print(f"digest ditulis: {day_path}")

        matched_total = sum(len(v) for v in clusters_by_topic.values())
        if matched_total and (cfg.get("notify") or {}):
            summary = digest_summary_text(clusters_by_topic, date_label)
            for line in notify_all(
                cfg.get("notify"), dict(os.environ),
                summary_text=summary, html_body=html_out,
                subject=f"[media-monitor] Digest {date_label}",
            ):
                print(f"notifikasi — {line}")

    matched = sum(len(v) for v in clusters_by_topic.values())
    errs = sum(1 for r in results if r.error)
    print(f"{matched} berita cocok · {scanned} dipindai · "
          f"{len(results) - errs}/{len(results)} feed sukses")
    return 0


def run(argv: List[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.import_opml:
        return cmd_import_opml(args.import_opml)
    cfg = load_config(args.config)
    if args.check:
        return cmd_check(cfg)
    if args.weekly:
        return cmd_weekly(cfg, args)
    if args.export_opml:
        return cmd_export_opml(cfg, args.export_opml)
    return cmd_daily(cfg, args)


def main() -> None:
    sys.exit(run())
