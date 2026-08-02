"""Klaster lintas media: berita yang sama dari beberapa sumber digabung jadi satu,
diberi skor, dan ditandai 🔥 bila ramai (multi kata kunci / multi media)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Set, Tuple

from .feeds import Item

_STOPWORDS = {
    "yang", "di", "ke", "dari", "dan", "untuk", "pada", "dengan", "ini", "itu",
    "akan", "dalam", "the", "a", "an", "of", "in", "on", "for", "to", "and",
}
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _norm_words(title: str) -> Set[str]:
    return {w for w in _WORD_RE.findall((title or "").lower())
            if w not in _STOPWORDS and len(w) >= 2}


def similarity(title_a: str, title_b: str) -> float:
    """Kemiripan Jaccard atas himpunan kata judul (0..1)."""
    a, b = _norm_words(title_a), _norm_words(title_b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class Cluster:
    """Satu berita utama + daftar media lain yang memberitakan hal serupa."""
    item: Item
    keywords: List[str]
    also: List[Item] = field(default_factory=list)

    @property
    def score(self) -> int:
        return len(set(self.keywords)) + len(self.also)

    @property
    def hot(self) -> bool:
        return len(set(self.keywords)) >= 2 or len(self.also) >= 1

    @property
    def also_sources(self) -> List[str]:
        seen, out = set(), []
        for it in self.also:
            if it.source not in seen and it.source != self.item.source:
                seen.add(it.source)
                out.append(it.source)
        return out


def cluster_matches(matches: List[Tuple[Item, List[str]]],
                    threshold: float = 0.55) -> List[Cluster]:
    """Gabungkan artikel berjudul mirip; hasil diurutkan 🔥 dulu, lalu skor, lalu waktu."""
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    ordered = sorted(matches, key=lambda m: m[0].published or epoch, reverse=True)
    clusters: List[Cluster] = []
    for item, kws in ordered:
        placed = False
        for cl in clusters:
            if similarity(item.title, cl.item.title) >= threshold:
                cl.also.append(item)
                for kw in kws:
                    if kw not in cl.keywords:
                        cl.keywords.append(kw)
                placed = True
                break
        if not placed:
            clusters.append(Cluster(item=item, keywords=list(kws)))
    clusters.sort(
        key=lambda c: (c.hot, c.score, c.item.published or epoch), reverse=True
    )
    return clusters
