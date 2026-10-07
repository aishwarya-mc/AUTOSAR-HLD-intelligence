from __future__ import annotations

import re

from app.core.config import get_settings
from app.core.logging import get_logger
from app.rag.embeddings import get_embedder
from app.rag.retriever import RetrievedChunk

logger = get_logger(__name__)


def _collection_name(document_id: str) -> str:
    # One collection per document keeps retrieval isolated between documents/projects.
    return "hld_" + re.sub(r"[^a-zA-Z0-9]", "_", document_id)[:60]


class VectorStore:
    """Persistent ChromaDB store with one collection per document."""

    def __init__(self, persist_dir: str | None = None):
        import chromadb

        path = persist_dir or str(get_settings().vector_dir)
        self.client = chromadb.PersistentClient(path=path)

    def index(self, document_id: str, chunks: list[dict]) -> int:
        embedder = get_embedder()
        if embedder is None or not chunks:
            return 0
        self.delete(document_id)
        col = self.client.create_collection(
            _collection_name(document_id), metadata={"hnsw:space": "cosine"}
        )
        texts = [c["text"] for c in chunks]
        col.add(
            ids=[c["chunk_id"] for c in chunks],
            embeddings=embedder.embed_passages(texts),
            documents=texts,
            metadatas=[
                {"page_number": c["page_number"], "section": c.get("section", "")} for c in chunks
            ],
        )
        return len(chunks)

    def search(self, document_id: str, query: str, top_k: int = 8) -> list[RetrievedChunk]:
        embedder = get_embedder()
        if embedder is None:
            return []
        try:
            col = self.client.get_collection(_collection_name(document_id))
        except Exception:
            return []
        res = col.query(
            query_embeddings=[embedder.embed_query(query)],
            n_results=min(top_k, col.count() or 1),
        )
        out = []
        for cid, doc, meta, dist in zip(
            res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]
        ):
            out.append(
                RetrievedChunk(cid, doc, meta["page_number"], meta.get("section", ""),
                               1.0 - float(dist))
            )
        return out

    def delete(self, document_id: str) -> None:
        try:
            self.client.delete_collection(_collection_name(document_id))
        except Exception:
            pass
