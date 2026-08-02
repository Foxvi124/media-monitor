"""Impor/ekspor daftar feed dalam format OPML (standar aplikasi pembaca RSS)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List
from xml.sax.saxutils import quoteattr


def import_opml(path: str) -> List[Dict[str, str]]:
    """Baca berkas OPML → daftar {name, url}. Outline tanpa xmlUrl diabaikan."""
    tree = ET.parse(path)
    feeds: List[Dict[str, str]] = []
    for node in tree.iter():
        if node.tag.rsplit("}", 1)[-1] != "outline":
            continue
        url = node.get("xmlUrl", "").strip()
        if not url:
            continue
        name = (node.get("title") or node.get("text") or url).strip()
        feeds.append({"name": name, "url": url})
    return feeds


def to_yaml_snippet(feeds: List[Dict[str, str]]) -> str:
    """Potongan YAML siap tempel ke config.yaml."""
    lines = ["feeds:"]
    for f in feeds:
        lines.append(f"  - name: {f['name']}")
        lines.append(f"    url: {f['url']}")
    return "\n".join(lines) + "\n"


def export_opml(feeds: List[Dict[str, str]], title: str = "media-monitor feeds") -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<opml version="2.0">',
             f"  <head><title>{title}</title></head>", "  <body>"]
    for f in feeds:
        lines.append(
            "    <outline type=\"rss\" text={t} title={t} xmlUrl={u}/>".format(
                t=quoteattr(str(f.get("name", ""))),
                u=quoteattr(str(f.get("url", ""))),
            )
        )
    lines += ["  </body>", "</opml>"]
    return "\n".join(lines) + "\n"
