from __future__ import annotations

import re

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.schemas import Citation, QueryResponse
from app.graph.builder import ArchitectureGraph
from app.rag.retriever import RetrievedChunk, tokenize

logger = get_logger(__name__)

NOT_FOUND = "The requested information was not found in the document."


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def find_entities(question: str, graph: ArchitectureGraph) -> list[str]:
    """Entities named in the question (exact identifier, or the same words without CamelCase)."""
    squashed = _squash(question)
    found = [n for n in graph.nodes if len(n) > 3 and _squash(n) in squashed]
    # Drop entities whose name is merely a substring of a longer matched one.
    return [n for n in found if not any(n != m and _squash(n) in _squash(m) for m in found)]


def graph_facts(entity: str, graph: ArchitectureGraph) -> list[tuple[str, int | None]]:
    facts = []
    for e in graph.neighbors(entity):
        facts.append((f"{e.source} {e.relation.replace('_', ' ').lower()} {e.target}", e.page))
    return facts


def _best_excerpt(text: str, query_tokens: set[str], limit: int = 460) -> str:
    """Best-matching sentence plus the one after it (answers often continue in the next sentence)."""
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if x.strip()]
    if not sentences:
        return text.strip()
    best = max(range(len(sentences)),
               key=lambda i: len(query_tokens & set(tokenize(sentences[i]))))
    excerpt = " ".join(sentences[best:best + 2])
    return excerpt if len(excerpt) <= limit else excerpt[: limit - 1] + "…"


class GroundedAnswerer:
    """
    Answers questions strictly from retrieved evidence.

    1. BM25 retrieval over section-aware chunks.
    2. Structured graph facts for any architecture entity named in the question.
    3. Optional LLM synthesis (Anthropic API) constrained to that evidence; if no key is
       configured, an extractive answer is returned so the system works fully offline.
    """

    def __init__(self, retriever, graph: ArchitectureGraph, document_id: str, version: str):
        self.retriever = retriever
        self.graph = graph
        self.document_id = document_id
        self.version = version

    def answer(self, question: str, top_k: int = 8) -> QueryResponse:
        hits = self.retriever.search(question, top_k=top_k)
        entities = find_entities(question, self.graph)
        facts: list[tuple[str, int | None]] = []
        for ent in entities:
            facts.extend(graph_facts(ent, self.graph))

        if not hits and not facts:
            return QueryResponse(
                answer=NOT_FOUND, confidence=0.0, grounded=False,
                limitations=["No chunk in the document matched the question."],
            )

        q_tokens = set(tokenize(question))
        citations = [
            Citation(
                citation_id=f"C{i + 1}", page_number=h.page_number, section=h.section,
                document_id=self.document_id, document_version=self.version,
                excerpt=_best_excerpt(h.text, q_tokens),
            )
            for i, h in enumerate(hits[:5])
        ]

        answer_text = self._llm_answer(question, hits[:5], facts) or self._extractive_answer(
            hits, facts, q_tokens
        )

        top = hits[0].score if hits else 0.0
        confidence = min(0.95, 0.35 + min(top, 12.0) / 24.0 + (0.15 if entities else 0.0))
        limitations = ["AI-assisted answer; verify against the cited pages before engineering use."]
        if not entities:
            limitations.append("No specific architecture entity was recognised in the question.")
        return QueryResponse(
            answer=answer_text, citations=citations, confidence=round(confidence, 2),
            grounded=True, limitations=limitations,
        )

    # -- answer builders ---------------------------------------------------

    @staticmethod
    def _extractive_answer(hits: list[RetrievedChunk], facts: list[tuple[str, int | None]],
                           q_tokens: set[str]) -> str:
        parts: list[str] = []
        if facts:
            seen = set()
            lines = []
            for text, page in facts:
                if text not in seen:
                    seen.add(text)
                    lines.append(f"- {text}" + (f" (page {page})" if page else ""))
            parts.append("Architecture facts:\n" + "\n".join(lines))
        if hits:
            parts.append(
                "Relevant document text:\n"
                + "\n".join(
                    f"- [{h.section or 'n/a'}, page {h.page_number}] {_best_excerpt(h.text, q_tokens)}"
                    for h in hits[:3]
                )
            )
        return "\n\n".join(parts)

    def _llm_answer(self, question: str, hits: list[RetrievedChunk],
                    facts: list[tuple[str, int | None]]) -> str | None:
        settings = get_settings()
        provider = settings.llm_provider.lower()
        if provider not in ("anthropic", "ollama"):
            return None
        if provider == "anthropic" and not settings.anthropic_api_key:
            return None
        context = "\n\n".join(
            f"[C{i + 1}] (section: {h.section}, page {h.page_number})\n{h.text}"
            for i, h in enumerate(hits)
        )
        fact_text = "\n".join(f"- {t} (page {p})" for t, p in facts)
        prompt = (
            "Answer the engineering question using ONLY the evidence below. Cite evidence as "
            "[C1], [C2]. If the evidence does not contain the answer, reply exactly: "
            f"\"{NOT_FOUND}\"\n\nEVIDENCE\n{context}\n\nSTRUCTURED FACTS\n{fact_text or 'none'}\n\n"
            f"QUESTION: {question}"
        )
        try:
            if provider == "ollama":  # locally hosted LLM: no data leaves the machine
                resp = httpx.post(
                    f"{settings.ollama_url.rstrip('/')}/api/generate",
                    json={"model": settings.llm_model or "llama3.2", "prompt": prompt,
                          "stream": False, "options": {"temperature": 0}},
                    timeout=180,
                )
                resp.raise_for_status()
                return resp.json()["response"].strip()
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.llm_model or "claude-haiku-4-5-20251001",
                    "max_tokens": 700,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=40,
            )
            resp.raise_for_status()
            return resp.json()["content"][0]["text"].strip()
        except Exception as exc:  # fall back to the extractive answer
            logger.warning("LLM call failed, using extractive answer: %s", exc)
            return None
