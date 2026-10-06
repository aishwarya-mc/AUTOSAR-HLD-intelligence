from __future__ import annotations

from app.core.logging import get_logger
from app.rag.retriever import BM25Retriever, RetrievedChunk
from app.rag.vector_store import VectorStore

logger = get_logger(__name__)

RRF_K = 60  # standard reciprocal-rank-fusion constant
# Calibrated on the sample HLD with bge-small: off-topic questions peak at ~0.57-0.60 cosine
# similarity, paraphrased in-domain questions score >= 0.62.
RELEVANCE_GATE = 0.60  # best semantic hit must reach this, otherwise nothing is retrieved
MIN_SEMANTIC_ONLY = 0.65  # semantic-only hits (no keyword overlap) need to be clearly similar


class HybridRetriever:
    """Semantic (BGE + ChromaDB) and lexical (BM25) retrieval fused with reciprocal rank fusion.

    Lexical search keeps exact identifiers such as IDoorStatus reliable; semantic search handles
    paraphrased questions. If the vector side is unavailable, BM25 results are returned alone.
    """

    def __init__(self, chunks: list[dict], document_id: str, store: VectorStore | None):
        self.bm25 = BM25Retriever(chunks)
        self.document_id = document_id
        self.store = store

    def search(self, query: str, top_k: int = 8) -> list[RetrievedChunk]:
        lexical = self.bm25.search(query, top_k=top_k * 2)
        semantic: list[RetrievedChunk] = []
        if self.store is not None:
            try:
                semantic = self.store.search(self.document_id, query, top_k=top_k * 2)
            except Exception as exc:
                logger.warning("Vector search failed, using BM25 only: %s", exc)
        if not semantic:
            return lexical[:top_k]
        if semantic[0].score < RELEVANCE_GATE:
            return []  # nothing in the document is semantically close: refuse rather than guess
        if not lexical:
            return [c for c in semantic if c.score >= MIN_SEMANTIC_ONLY][:top_k]

        fused: dict[str, float] = {}
        by_id: dict[str, RetrievedChunk] = {}
        for ranking in (lexical, semantic):
            for rank, c in enumerate(ranking):
                fused[c.chunk_id] = fused.get(c.chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
                by_id.setdefault(c.chunk_id, c)
        ordered = sorted(fused, key=lambda i: -fused[i])[:top_k]
        bm_scores = {c.chunk_id: c.score for c in lexical}
        return [
            RetrievedChunk(
                by_id[i].chunk_id, by_id[i].text, by_id[i].page_number, by_id[i].section,
                bm_scores.get(i, by_id[i].score * 4),
            )
            for i in ordered
        ]
