from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

_TOKEN = re.compile(r"[A-Za-z0-9]+")
_CAMEL = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")
_STOP = {
    "the", "a", "an", "of", "to", "and", "or", "is", "are", "in", "on", "for", "by", "with",
    "what", "which", "who", "how", "does", "do", "this", "that", "it", "as", "at", "be",
    "me", "tell", "show", "list", "give",
}


def tokenize(text: str) -> list[str]:
    """Lower-case tokens; identifiers are indexed whole and split on CamelCase/underscores."""
    out: list[str] = []
    for raw in _TOKEN.findall(text.replace("_", " ")):
        out.append(raw.lower())
        parts = [p.lower() for p in _CAMEL.findall(raw)]
        if len(parts) > 1:
            out.extend(parts)
    return [t for t in out if t not in _STOP and len(t) > 1]


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    page_number: int
    section: str
    score: float


class BM25Retriever:
    """Dependency-free BM25 over section-aware chunks (deterministic and auditable)."""

    def __init__(self, chunks: list[dict], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(c["text"] + " " + c.get("section", ""))) for c in chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, top_k: int = 8) -> list[RetrievedChunk]:
        q = set(tokenize(query))
        scored = []
        for i, d in enumerate(self.docs):
            score = 0.0
            for t in q:
                tf = d.get(t, 0)
                if tf:
                    denom = tf + self.k1 * (1 - self.b + self.b * self.lengths[i] / (self.avg or 1))
                    score += self.idf.get(t, 0) * tf * (self.k1 + 1) / denom
            if score > 0:
                c = self.chunks[i]
                scored.append(
                    RetrievedChunk(c["chunk_id"], c["text"], c["page_number"], c.get("section", ""), score)
                )
        scored.sort(key=lambda r: -r.score)
        return scored[:top_k]
