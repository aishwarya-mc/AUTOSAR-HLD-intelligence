from __future__ import annotations

from app.core.logging import get_logger
from app.rag.retriever import BM25Retriever, RetrievedChunk, tokenize
from app.rag.vector_store import VectorStore

logger = get_logger(__name__)

RRF_K = 60  # standard reciprocal-rank-fusion constant
# Dense weight tuned on the development documents (retrieval_experiments.py): held-out MRR 0.869
# vs 0.837 with equal weights. BM25 acts mainly as a tie-breaker and keeps exact identifiers findable.
DENSE_WEIGHT = 10.0
LEXICAL_WEIGHT = 1.0
# Legacy hand-set thresholds (used when no trained answerability model is available).
# Calibrated on the sample HLD with bge-small: off-topic questions peak at ~0.57-0.60 cosine
# similarity, paraphrased in-domain questions score >= 0.62.
RELEVANCE_GATE = 0.60  # best semantic hit must reach this, otherwise nothing is retrieved
MIN_SEMANTIC_ONLY = 0.65  # semantic-only hits (no keyword overlap) need to be clearly similar

FEATURE_NAMES = [
    "sem_top1", "sem_top2", "sem_margin", "sem_mean5",
    "bm25_top1", "bm25_per_token", "coverage", "uncovered", "n_tokens",
    "agree", "top_chunk_cov", "entity_match",
]


class HybridRetriever:
    """Semantic (BGE + ChromaDB) and lexical (BM25) retrieval fused with reciprocal rank fusion.

    Lexical search keeps exact identifiers such as IDoorStatus reliable; semantic search handles
    paraphrased questions. If the vector side is unavailable, BM25 results are returned alone.
    `retrieve_with_features` additionally returns the numeric features used by the trained
    answerability classifier (see app/rag/answerability.py).
    """

    def __init__(self, chunks: list[dict], document_id: str, store: VectorStore | None):
        self.bm25 = BM25Retriever(chunks)
        self.document_id = document_id
        self.store = store
        self._index = {c["chunk_id"]: i for i, c in enumerate(chunks)}

    # -- retrieval ---------------------------------------------------------

    def _semantic(self, query: str, top_k: int) -> list[RetrievedChunk]:
        if self.store is None:
            return []
        try:
            return self.store.search(self.document_id, query, top_k=top_k)
        except Exception as exc:
            logger.warning("Vector search failed, using BM25 only: %s", exc)
            return []

    def _fuse(self, lexical: list[RetrievedChunk], semantic: list[RetrievedChunk],
              top_k: int) -> list[RetrievedChunk]:
        fused: dict[str, float] = {}
        by_id: dict[str, RetrievedChunk] = {}
        for weight, ranking in ((LEXICAL_WEIGHT, lexical), (DENSE_WEIGHT, semantic)):
            for rank, c in enumerate(ranking):
                fused[c.chunk_id] = fused.get(c.chunk_id, 0.0) + weight / (RRF_K + rank + 1)
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

    def search(self, query: str, top_k: int = 8) -> list[RetrievedChunk]:
        """Retrieve with the legacy hand-set relevance gate."""
        lexical = self.bm25.search(query, top_k=top_k * 2)
        semantic = self._semantic(query, top_k * 2)
        if not semantic:
            return lexical[:top_k]
        if semantic[0].score < RELEVANCE_GATE:
            return []  # nothing in the document is semantically close: refuse rather than guess
        if not lexical:
            return [c for c in semantic if c.score >= MIN_SEMANTIC_ONLY][:top_k]
        return self._fuse(lexical, semantic, top_k)

    def retrieve_with_features(self, query: str, top_k: int = 8
                               ) -> tuple[list[RetrievedChunk], dict[str, float] | None]:
        """Retrieve without the hand gate and compute answerability features.

        Returns (chunks, features); features is None when the vector side is unavailable.
        """
        lexical = self.bm25.search(query, top_k=top_k * 2)
        semantic = self._semantic(query, top_k * 2)
        if not semantic:
            return lexical[:top_k], None

        q_tokens = set(tokenize(query))
        n = len(q_tokens)
        covered = sum(t in self.bm25.idf for t in q_tokens)
        top = semantic[0]
        top_tokens = set(self.bm25.docs[self._index[top.chunk_id]]) if top.chunk_id in self._index else set()
        sims = [c.score for c in semantic]
        feats = {
            "sem_top1": sims[0],
            "sem_top2": sims[1] if len(sims) > 1 else sims[0],
            "sem_margin": sims[0] - (sims[1] if len(sims) > 1 else sims[0]),
            "sem_mean5": sum(sims[:5]) / len(sims[:5]),
            "bm25_top1": lexical[0].score if lexical else 0.0,
            "bm25_per_token": (lexical[0].score / n) if lexical and n else 0.0,
            "coverage": covered / n if n else 0.0,
            "uncovered": float(n - covered),
            "n_tokens": float(n),
            "agree": 1.0 if lexical and lexical[0].chunk_id == top.chunk_id else 0.0,
            "top_chunk_cov": (len(q_tokens & top_tokens) / n) if n else 0.0,
            "entity_match": 0.0,  # filled in by the answerer, which owns the graph
        }
        if not lexical:
            chunks = [c for c in semantic if c.score >= MIN_SEMANTIC_ONLY][:top_k]
            if not chunks:  # keep the evidence trail even for borderline questions
                chunks = semantic[:3]
            return chunks, feats
        return self._fuse(lexical, semantic, top_k), feats
