from __future__ import annotations

import re

from app.core.logging import get_logger
from app.core.schemas import Citation, QueryResponse
from app.graph.builder import ArchitectureGraph
from app.rag.answerability import load_answerability_model
from app.rag.llm import NOT_FOUND, generate_answer, llm_status
from app.rag.retriever import RetrievedChunk, tokenize

logger = get_logger(__name__)


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
    3. A local LLM (Ollama) phrases the answer from that evidence only (see app/rag/llm.py). If the
       LLM is unavailable or its answer fails the faithfulness guard, the extractive answer is used.
    """

    def __init__(self, retriever, graph: ArchitectureGraph, document_id: str, version: str):
        self.retriever = retriever
        self.graph = graph
        self.document_id = document_id
        self.version = version

    def answer(self, question: str, top_k: int = 8) -> QueryResponse:
        model = load_answerability_model()
        features = None
        if model is not None and hasattr(self.retriever, "retrieve_with_features"):
            hits, features = self.retriever.retrieve_with_features(question, top_k=top_k)
        else:
            hits = self.retriever.search(question, top_k=top_k)
        entities = find_entities(question, self.graph)
        facts: list[tuple[str, int | None]] = []
        for ent in entities:
            facts.extend(graph_facts(ent, self.graph))

        probability = None
        if model is not None and features is not None:
            # A trained classifier decides whether the document can answer this question.
            features["entity_match"] = float(len(entities))
            answerable, probability = model.is_answerable(features)
            if not answerable:
                return QueryResponse(
                    answer=NOT_FOUND, confidence=round(probability, 2), grounded=False,
                    limitations=[
                        f"Answerability model v{model.version}: estimated probability that the document "
                        f"answers this question is {probability:.2f} (threshold {model.threshold:.2f})."
                    ],
                )

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

        status = llm_status()
        llm = generate_answer(question, hits[:5], facts)
        generated_by = llm.label if llm else None
        answer_text = llm.text if llm else self._extractive_answer(hits, facts, q_tokens)

        if probability is not None:
            confidence = min(0.99, probability)  # calibrated probability from the trained model
        else:
            top = hits[0].score if hits else 0.0
            confidence = min(0.95, 0.35 + min(top, 12.0) / 24.0 + (0.15 if entities else 0.0))
        limitations = ["AI-assisted answer; verify against the cited pages before engineering use."]
        if generated_by:
            limitations.append(
                f"Wording generated by {generated_by}, instructed to use only the cited evidence; "
                "check it against the citations."
            )
        if status.enabled and not generated_by:
            limitations.append(
                f"LLM wording not used ({status.detail if not status.reachable or not status.model_installed else 'answer failed the faithfulness check'}); "
                "showing the extracted evidence instead."
            )
        if not entities:
            limitations.append("No specific architecture entity was recognised in the question.")
        return QueryResponse(
            answer=answer_text, citations=citations, confidence=round(confidence, 2),
            grounded=True, limitations=limitations, generated_by=generated_by,
            facts=list(dict.fromkeys(f"{t} (page {p})" if p else t for t, p in facts)),
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


__all__ = ["GroundedAnswerer", "NOT_FOUND", "find_entities", "graph_facts"]
