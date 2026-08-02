"""Pencocokan kata kunci per topik: batas kata, frasa, any/all/exclude, sorot hasil."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def _compile(keyword: str) -> re.Pattern:
    """Regex batas-kata yang aman untuk frasa ("smelter nikel") dan istilah ber-tanda."""
    return re.compile(r"(?<!\w)" + re.escape(keyword.strip()) + r"(?!\w)",
                      re.IGNORECASE)


@dataclass
class Topic:
    name: str
    any: List[str] = field(default_factory=list)
    all: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.any and not self.all:
            raise ValueError(f"topik '{self.name}' butuh minimal satu kata kunci "
                             "di 'any' atau 'all'")
        self._any = [(kw, _compile(kw)) for kw in self.any]
        self._all = [(kw, _compile(kw)) for kw in self.all]
        self._exclude = [_compile(kw) for kw in self.exclude]

    def match(self, text: str) -> Optional[List[str]]:
        """Kembalikan daftar kata kunci yang kena, atau None bila tidak cocok."""
        if any(rx.search(text) for rx in self._exclude):
            return None
        hits_all = [kw for kw, rx in self._all if rx.search(text)]
        if self._all and len(hits_all) != len(self._all):
            return None
        hits_any = [kw for kw, rx in self._any if rx.search(text)]
        if self._any and not hits_any:
            return None
        return hits_any + [kw for kw in hits_all if kw not in hits_any]


def topics_from_config(raw_topics: List[Dict]) -> List[Topic]:
    topics = []
    for t in raw_topics:
        topics.append(Topic(
            name=str(t.get("name", "Tanpa nama")),
            any=[str(k) for k in (t.get("any") or [])],
            all=[str(k) for k in (t.get("all") or [])],
            exclude=[str(k) for k in (t.get("exclude") or [])],
        ))
    return topics


def highlight(text: str, keywords: List[str],
              wrap: Tuple[str, str] = ("**", "**")) -> str:
    """Bungkus setiap kemunculan kata kunci (mempertahankan huruf aslinya)."""
    out = text
    for kw in sorted(set(keywords), key=len, reverse=True):
        out = _compile(kw).sub(lambda m: f"{wrap[0]}{m.group(0)}{wrap[1]}", out)
    return out
