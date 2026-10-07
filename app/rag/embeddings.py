from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# BGE models are trained with this instruction prefix on retrieval queries.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    """Local ONNX embedding model (BGE by default); nothing leaves the machine after download."""

    def __init__(self, model_name: str):
        from fastembed import TextEmbedding

        self.model_name = model_name
        self.model = TextEmbedding(model_name)

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self.model.embed(texts)]

    def embed_query(self, query: str) -> list[float]:
        prefix = BGE_QUERY_PREFIX if "bge" in self.model_name.lower() else ""
        return next(iter(self.model.embed([prefix + query]))).tolist()


@lru_cache
def get_embedder() -> Embedder | None:
    """Return the shared embedder, or None when disabled/unavailable (BM25-only fallback)."""
    settings = get_settings()
    if not settings.embeddings_enabled:
        return None
    try:
        return Embedder(settings.embedding_model)
    except Exception as exc:
        logger.warning("Embedding model unavailable, falling back to BM25 only: %s", exc)
        return None
