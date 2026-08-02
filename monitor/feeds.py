"""Pengambilan dan parsing feed RSS 2.0 / Atom — hanya pustaka standar."""

from __future__ import annotations

import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional

USER_AGENT = "media-monitor/1.0 (open-source RSS keyword monitor)"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@dataclass
class Item:
    title: str
    link: str
    summary: str
    published: Optional[datetime]
    source: str


@dataclass
class FeedResult:
    name: str
    url: str
    items: List[Item] = field(default_factory=list)
    error: Optional[str] = None


def strip_html(text: str) -> str:
    """Buang tag HTML, urai entity, rapikan spasi."""
    cleaned = _TAG_RE.sub(" ", text or "")
    return _WS_RE.sub(" ", html.unescape(cleaned)).strip()


def parse_date(raw: str) -> Optional[datetime]:
    """Terima RFC 822 (RSS) maupun ISO 8601 (Atom); kembalikan datetime ber-timezone."""
    raw = (raw or "").strip()
    if not raw:
        return None
    dt: Optional[datetime] = None
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(el: ET.Element, name: str) -> str:
    for c in el:
        if _local(c.tag) == name:
            return (c.text or "").strip()
    return ""


def parse_feed(xml_bytes: bytes, source_name: str) -> List[Item]:
    """Parse RSS 2.0 atau Atom menjadi daftar Item. Melempar ValueError jika bukan feed."""
    root = ET.fromstring(xml_bytes)
    tag = _local(root.tag)
    items: List[Item] = []

    if tag == "rss":
        channel = next((c for c in root if _local(c.tag) == "channel"), None)
        parent = channel if channel is not None else root
        entries = [c for c in parent if _local(c.tag) == "item"]
        for it in entries:
            items.append(
                Item(
                    title=strip_html(_child_text(it, "title")),
                    link=_child_text(it, "link"),
                    summary=strip_html(_child_text(it, "description")),
                    published=parse_date(_child_text(it, "pubDate")
                                         or _child_text(it, "date")),
                    source=source_name,
                )
            )
    elif tag == "feed":  # Atom
        for it in (c for c in root if _local(c.tag) == "entry"):
            link = ""
            for c in it:
                if _local(c.tag) == "link":
                    href = c.get("href", "")
                    if c.get("rel", "alternate") == "alternate" and href:
                        link = href
                        break
                    link = link or href
            items.append(
                Item(
                    title=strip_html(_child_text(it, "title")),
                    link=link,
                    summary=strip_html(_child_text(it, "summary")
                                       or _child_text(it, "content")),
                    published=parse_date(_child_text(it, "published")
                                         or _child_text(it, "updated")),
                    source=source_name,
                )
            )
    else:
        raise ValueError(f"bukan feed RSS/Atom (root: <{tag}>)")
    return items


def fetch_feed(name: str, url: str, timeout: int = 20) -> FeedResult:
    """Ambil dan parse satu feed; kegagalan dicatat, tidak menghentikan program."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        return FeedResult(name=name, url=url, items=parse_feed(data, name))
    except Exception as exc:  # jaringan, HTTP, XML — semua dilaporkan sebagai error feed
        return FeedResult(name=name, url=url, error=f"{type(exc).__name__}: {exc}")
