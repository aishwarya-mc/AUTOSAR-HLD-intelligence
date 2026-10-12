"""Local LLM (Ollama) that phrases the final answer from retrieved evidence.

The LLM never decides *whether* to answer (the trained answerability model does that) and never
supplies facts: it only rewrites the retrieved evidence. Three safeguards keep it grounded:

1. the prompt allows only the supplied evidence and asks for [C#] citations;
2. a faithfulness guard rejects answers that mention an identifier (component, interface, port,
   signal) that appears neither in the evidence nor in the question;
3. any failure (Ollama not running, model missing, timeout, empty or 'not found' reply, unfaithful
   reply) falls back to the extractive answer, so the system always answers.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

NOT_FOUND = "The requested information was not found in the document."

SYSTEM_PROMPT = (
    "You are an assistant for reviewing AUTOSAR High-Level Design documents. Answer the question "
    "using ONLY the EVIDENCE and STRUCTURED FACTS provided. Rules: (1) Be concise: at most four "
    "sentences. (2) Cite the evidence you used as [C1], [C2] right after the statement. (3) Copy "
    "component, interface, port and signal names exactly as written. (4) Do not add any name, number "
    "or fact that is not in the evidence. (5) Do not confuse the kinds of element: interface names start "
    "with I (for example IDoorStatus), port names end in _In or _Out (for example DoorStatus_Out), "
    "components end in Manager, Control or Component, and signals are the data values. (6) Keep the "
    "relationship verbs exactly as in the STRUCTURED FACTS: a component that 'provides' an interface "
    "does not 'require' it, and the reverse. Name only the components the question asks about. (7) If "
    f"the evidence does not answer the question, reply exactly: {NOT_FOUND}"
)

FACT = re.compile(r"(\w+) (provides|requires) interface (\w+)")
ASKS_REQUIRES = re.compile(r"\b(requires?|consum\w*|uses?|needs?)\b", re.I)
ASKS_PROVIDES = re.compile(r"\b(provides?|supplies|supplying|publish\w*|offers?)\b", re.I)

IDENTIFIER = re.compile(r"\b[A-Za-z]+(?:[A-Z][a-z0-9]+)+\b|\b[A-Za-z0-9]+_(?:In|Out)\b")


@dataclass
class LLMAnswer:
    text: str
    label: str  # e.g. "ollama:llama3.2"
    seconds: float


@dataclass
class LLMStatus:
    provider: str
    model: str
    enabled: bool
    reachable: bool
    model_installed: bool
    detail: str


_cache: dict = {"at": 0.0, "status": None}


def llm_status(force: bool = False) -> LLMStatus:
    """Is the configured LLM usable right now? Cached for 15 s so a missing server costs ~nothing."""
    s = get_settings()
    provider, model = s.llm_provider.lower(), s.llm_model or "llama3.2"
    if provider == "anthropic":
        ok = bool(s.anthropic_api_key)
        return LLMStatus(provider, model or "claude-haiku-4-5-20251001", True, ok, ok,
                         "external API" if ok else "ANTHROPIC_API_KEY missing")
    if provider != "ollama":
        return LLMStatus(provider, "", False, False, False, "LLM disabled (extractive answers)")
    now = time.time()
    if not force and _cache["status"] is not None and now - _cache["at"] < 15:
        return _cache["status"]
    try:
        r = httpx.get(f"{s.ollama_url.rstrip('/')}/api/tags", timeout=1.5)
        r.raise_for_status()
        names = [m.get("name", "") for m in r.json().get("models", [])]
        wanted = model if ":" in model else f"{model}:latest"
        installed = wanted in names or model in names
        status = LLMStatus(provider, model, True, True, installed,
                           "ready" if installed else f"model '{model}' not installed (ollama pull {model})")
    except Exception as exc:
        status = LLMStatus(provider, model, True, False, False, f"Ollama not reachable ({type(exc).__name__})")
    _cache.update(at=now, status=status)
    return status


def identifiers(text: str) -> set[str]:
    return {m.group(0).lower() for m in IDENTIFIER.finditer(text)}


def is_faithful(answer: str, evidence: str, question: str) -> bool:
    """Every identifier in the answer must occur in the evidence or the question."""
    allowed = identifiers(evidence) | identifiers(question)
    return identifiers(answer) <= allowed


def relation_conflict(question: str, answer: str, facts) -> bool:
    """True if the answer names a component for the wrong role (e.g. a provider as a requirer).

    Only applies to questions that ask about exactly one of provides/requires; the roles come from the
    structured facts extracted from the document tables, not from the LLM.
    """
    wants_req, wants_prov = bool(ASKS_REQUIRES.search(question)), bool(ASKS_PROVIDES.search(question))
    if wants_req == wants_prov:
        return False
    asked, other = ("requires", "provides") if wants_req else ("provides", "requires")
    roles: dict[str, set[str]] = {}
    for text, _page in facts:
        m = FACT.search(text)
        if m:
            roles.setdefault(m.group(1), set()).add(m.group(2))
    mentioned = identifiers(answer)
    for comp, rels in roles.items():
        if comp.lower() in mentioned and other in rels and asked not in rels:
            return True
    return False


def build_messages(question: str, hits, facts) -> list[dict]:
    context = "\n\n".join(
        f"[C{i + 1}] (section: {h.section}, page {h.page_number})\n{h.text}" for i, h in enumerate(hits)
    )
    fact_text = "\n".join(f"- {t} (page {p})" for t, p in facts) or "none"
    user = f"EVIDENCE\n{context}\n\nSTRUCTURED FACTS\n{fact_text}\n\nQUESTION: {question}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def generate_answer(question: str, hits, facts) -> LLMAnswer | None:
    """Return the LLM's wording, or None when the extractive answer should be used."""
    s = get_settings()
    provider = s.llm_provider.lower()
    status = llm_status()
    if not (status.enabled and status.reachable and status.model_installed):
        return None
    messages = build_messages(question, hits, facts)
    evidence = " ".join(m["content"] for m in messages if m["role"] == "user")
    started = time.time()
    try:
        if provider == "ollama":  # locally hosted: no data leaves the machine
            resp = httpx.post(
                f"{s.ollama_url.rstrip('/')}/api/chat",
                json={"model": status.model, "messages": messages, "stream": False, "keep_alive": "30m",
                      "options": {"temperature": 0, "num_predict": 300}},
                timeout=s.llm_timeout_seconds,
            )
            resp.raise_for_status()
            text = resp.json()["message"]["content"].strip()
            label = f"ollama:{status.model}"
        else:  # anthropic
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": s.anthropic_api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": status.model, "max_tokens": 400, "system": SYSTEM_PROMPT,
                      "messages": [messages[1]]},
                timeout=s.llm_timeout_seconds,
            )
            resp.raise_for_status()
            text = resp.json()["content"][0]["text"].strip()
            label = f"anthropic:{status.model}"
    except Exception as exc:
        logger.warning("LLM call failed, using extractive answer: %s", exc)
        _cache["at"] = 0.0  # re-check availability next time
        return None
    if not text or NOT_FOUND.lower() in text.lower():
        return None
    if not is_faithful(text, evidence, question):
        logger.warning("LLM answer rejected by the faithfulness guard (unknown identifier): %s", text[:120])
        return None
    if relation_conflict(question, text, facts):
        logger.warning("LLM answer rejected by the relation guard (provides/requires mixed up): %s", text[:120])
        return None
    return LLMAnswer(text=text, label=label, seconds=time.time() - started)


def warm_up() -> None:
    """Load the model into memory in the background so the first real question is fast."""
    def run():
        status = llm_status(force=True)
        if status.reachable and status.model_installed and status.provider == "ollama":
            try:
                s = get_settings()
                httpx.post(f"{s.ollama_url.rstrip('/')}/api/chat",
                           json={"model": status.model, "messages": [{"role": "user", "content": "ok"}],
                                 "stream": False, "keep_alive": "30m", "options": {"num_predict": 1}},
                           timeout=s.llm_timeout_seconds)
                logger.info("LLM warmed up: %s", status.model)
            except Exception as exc:
                logger.warning("LLM warm-up failed: %s", exc)
        else:
            logger.info("LLM not ready: %s", status.detail)

    threading.Thread(target=run, daemon=True).start()
