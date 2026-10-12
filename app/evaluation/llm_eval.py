"""Measure LLM-phrased answers against the extractive baseline.

python -m app.evaluation.llm_eval [--out data/evaluation/results]

For every answerable question of the two hand-written sets (sample HLD and held-out domains) the same
retrieval + answerability decision is used; only the wording step differs:
  extractive  = facts and quoted passages (LLM_PROVIDER=local)
  llm         = local Ollama model phrasing the same evidence (guarded by the faithfulness check)
Metrics: expected-term accuracy, [C#] citation markers, LLM usage rate (vs guard/fallback), latency.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("VECTOR_DIR", tempfile.mkdtemp(prefix="hld_llm_"))

import time  # noqa: E402

from app.core.config import PROJECT_ROOT, get_settings  # noqa: E402
from app.rag import llm  # noqa: E402
from app.rag.answerability import load_answerability_model  # noqa: E402
from app.services.pipeline import HLDService  # noqa: E402

CITATION = re.compile(r"\[C\d+\]")


def load_cases() -> list[dict]:
    s = get_settings()
    ev = s.evaluation_data_dir
    cases = []
    for c in json.loads((ev / "qa_set.json").read_text(encoding="utf-8")):
        if c.get("answerable", True):
            cases.append({**c, "doc": "bcs_sample"})
    for c in json.loads((ev / "qa_set_independent.json").read_text(encoding="utf-8")):
        if c.get("answerable", True):
            cases.append(c)
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(PROJECT_ROOT / "data" / "evaluation" / "results"))
    args = parser.parse_args()

    settings = get_settings()
    settings.llm_provider = settings.llm_provider if settings.llm_provider != "local" else "ollama"
    status = llm.llm_status(force=True)
    print("LLM status:", status)
    if not (status.reachable and status.model_installed):
        print("The LLM is not ready:", status.detail)
        return 2

    service = HLDService()
    docs = {"bcs_sample": PROJECT_ROOT / "data" / "sample" / "sample_hld.pdf"}
    for key in ("steering", "keyless", "wiper"):
        docs[key] = PROJECT_ROOT / "data" / "synthetic" / f"{key}.pdf"
    ids = {k: service.process(p)["document_id"] for k, p in docs.items()}

    cases = load_cases()
    rows = []
    for c in cases:
        answerer = service.answerer(ids[c["doc"]])
        settings.llm_provider = "local"
        base = answerer.answer(c["question"])
        settings.llm_provider = "ollama"
        llm._cache.update(at=0.0, status=None)
        t0 = time.time()
        out = answerer.answer(c["question"])
        seconds = time.time() - t0
        terms = [t.lower() for t in c["must_contain"]]
        rows.append({
            "id": c["id"], "question": c["question"], "grounded": out.grounded,
            "baseline_correct": base.grounded and all(t in base.answer.lower() for t in terms),
            "llm_used": out.generated_by is not None,
            "llm_correct": out.grounded and all(t in out.answer.lower() for t in terms),
            "citation_marker": bool(CITATION.search(out.answer)) if out.generated_by else None,
            "seconds": round(seconds, 2), "answer": out.answer,
            "fallback_reason": next((x for x in out.limitations if x.startswith("LLM wording not used")), None),
        })
        print(f"{c['id']:4s} llm={rows[-1]['llm_used']!s:5s} correct={rows[-1]['llm_correct']!s:5s} {seconds:5.1f}s")

    used = [r for r in rows if r["llm_used"]]
    summary = {
        "model": status.model, "questions": len(rows),
        "baseline_accuracy": round(sum(r["baseline_correct"] for r in rows) / len(rows), 3),
        "llm_accuracy_overall": round(sum(r["llm_correct"] for r in rows) / len(rows), 3),
        "llm_used_rate": round(len(used) / len(rows), 3),
        "llm_accuracy_when_used": round(sum(r["llm_correct"] for r in used) / len(used), 3) if used else None,
        "citation_marker_rate_when_used": round(sum(bool(r["citation_marker"]) for r in used) / len(used), 3) if used else None,
        "median_seconds_when_used": round(statistics.median(r["seconds"] for r in used), 2) if used else None,
        "fallbacks": len(rows) - len(used),
    }
    print(json.dumps(summary, indent=2))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "llm_eval.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), encoding="utf-8")
    load_answerability_model.cache_clear()
    return 0


if __name__ == "__main__":
    sys.exit(main())
