"""Offline evaluation: python -m app.evaluation.run_eval [--out data/evaluation/results]

Reports (1) extraction precision/recall against a hand-built ground truth and
(2) Q&A answer accuracy, citation validity (groundedness), retrieval hit rate and refusal accuracy.
"""
import argparse
import json
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("VECTOR_DIR", tempfile.mkdtemp(prefix="hld_eval_vectors_"))

from app.core.config import get_settings  # noqa: E402
from app.services.pipeline import HLDService  # noqa: E402


def extraction_metrics(service: HLDService, document_id: str, truth: dict) -> dict:
    found: dict[str, set] = defaultdict(set)
    for e in service.entities(document_id):
        found[e["entity_type"]].add(e["name"])
    rows, tp_all, fp_all, fn_all = {}, 0, 0, 0
    for kind, expected in truth.items():
        if kind == "document":
            continue
        exp, got = set(expected), found.get(kind, set())
        tp, fp, fn = len(exp & got), len(got - exp), len(exp - got)
        tp_all, fp_all, fn_all = tp_all + tp, fp_all + fp, fn_all + fn
        rows[kind] = {
            "expected": len(exp), "extracted": len(got), "true_positive": tp,
            "precision": round(tp / (tp + fp), 3) if tp + fp else 0.0,
            "recall": round(tp / (tp + fn), 3) if tp + fn else 0.0,
            "missing": sorted(exp - got), "unexpected": sorted(got - exp),
        }
    rows["overall"] = {
        "precision": round(tp_all / (tp_all + fp_all), 3) if tp_all + fp_all else 0.0,
        "recall": round(tp_all / (tp_all + fn_all), 3) if tp_all + fn_all else 0.0,
    }
    return rows


def qa_metrics(service: HLDService, document_id: str, cases: list[dict]) -> dict:
    answerer = service.answerer(document_id)
    results, by_cat = [], defaultdict(lambda: [0, 0])
    for case in cases:
        r = answerer.answer(case["question"])
        answerable = case.get("answerable", True)
        if answerable:
            text_ok = r.grounded and all(t.lower() in r.answer.lower() for t in case["must_contain"])
            cite_ok = any(c.page_number == case["page"] for c in r.citations)
            retrieval_ok = cite_ok
            ok = text_ok and cite_ok
        else:
            text_ok = cite_ok = retrieval_ok = None
            ok = not r.grounded
        by_cat[case["category"]][0] += ok
        by_cat[case["category"]][1] += 1
        results.append({
            "id": case["id"], "category": case["category"], "question": case["question"],
            "passed": bool(ok), "answerable": answerable, "grounded": r.grounded,
            "confidence": r.confidence, "answer_contains_expected": text_ok,
            "citation_on_expected_page": cite_ok, "retrieval_hit": retrieval_ok,
            "citations": [{"id": c.citation_id, "page": c.page_number, "section": c.section}
                          for c in r.citations],
            "answer": r.answer,
        })
    answerable = [x for x in results if x["answerable"]]
    unanswerable = [x for x in results if not x["answerable"]]
    answered = [x for x in results if x["grounded"]]
    return {
        "total_questions": len(results),
        "accuracy_overall": round(sum(x["passed"] for x in results) / len(results), 3),
        "answer_accuracy_answerable": round(sum(x["passed"] for x in answerable) / len(answerable), 3),
        "citation_page_hit_rate": round(
            sum(bool(x["citation_on_expected_page"]) for x in answerable) / len(answerable), 3),
        "groundedness_valid_citations": round(
            sum(bool(x["citations"]) for x in answered) / len(answered), 3) if answered else 0.0,
        "refusal_accuracy_unanswerable": round(
            sum(x["passed"] for x in unanswerable) / len(unanswerable), 3) if unanswerable else None,
        "by_category": {k: f"{p}/{n}" for k, (p, n) in by_cat.items()},
        "results": results,
    }


def independent_eval(service: HLDService) -> dict:
    """Hand-written questions on held-out documents, trained model vs the previous hand-set gate."""
    from app.rag.answerability import load_answerability_model

    settings = get_settings()
    cases = json.loads((settings.evaluation_data_dir / "qa_set_independent.json").read_text(encoding="utf-8"))
    doc_ids = {}
    for key in {c["doc"] for c in cases}:
        doc_ids[key] = service.process(settings.project_root_data / "synthetic" / f"{key}.pdf")["document_id"]

    def run(label: str, model_dir: str) -> dict:
        settings.answerability_model_dir = model_dir
        load_answerability_model.cache_clear()
        rows = []
        for c in cases:
            r = service.answerer(doc_ids[c["doc"]]).answer(c["question"])
            answerable = c.get("answerable", True)
            ok = (r.grounded and all(t.lower() in r.answer.lower() for t in c["must_contain"])) if answerable                 else not r.grounded
            rows.append({"id": c["id"], "doc": c["doc"], "answerable": answerable, "passed": bool(ok),
                         "grounded": r.grounded, "confidence": r.confidence, "question": c["question"],
                         "answer": r.answer[:200]})
        ans = [x for x in rows if x["answerable"]]
        un = [x for x in rows if not x["answerable"]]
        return {"label": label, "accuracy": round(sum(x["passed"] for x in rows) / len(rows), 3),
                "answerable_accuracy": round(sum(x["passed"] for x in ans) / len(ans), 3),
                "refusal_accuracy": round(sum(x["passed"] for x in un) / len(un), 3),
                "n": len(rows), "failures": [x for x in rows if not x["passed"]]}

    trained = run("trained answerability model", "")
    legacy = run("previous hand-set relevance gate", "/nonexistent")
    settings.answerability_model_dir = ""
    load_answerability_model.cache_clear()
    return {"trained": trained, "legacy_gate": legacy}


def to_markdown(config: dict, ext: dict, qa: dict) -> str:
    lines = ["# Evaluation results", "", "## Configuration", ""]
    lines += [f"- {k}: `{v}`" for k, v in config.items()]
    lines += ["", "## Entity extraction (vs. ground truth)", "",
              "| Entity type | Expected | Extracted | Precision | Recall |", "|---|---|---|---|---|"]
    for kind, r in ext.items():
        if kind == "overall":
            continue
        lines.append(f"| {kind} | {r['expected']} | {r['extracted']} | {r['precision']} | {r['recall']} |")
    lines.append(f"| **overall** | | | **{ext['overall']['precision']}** | **{ext['overall']['recall']}** |")
    lines += ["", "## Question answering", "",
              f"- Questions: {qa['total_questions']}",
              f"- Overall accuracy: {qa['accuracy_overall']}",
              f"- Accuracy on answerable questions: {qa['answer_accuracy_answerable']}",
              f"- Citation on expected page: {qa['citation_page_hit_rate']}",
              f"- Groundedness (answers with valid citations): {qa['groundedness_valid_citations']}",
              f"- Refusal accuracy on unanswerable questions: {qa['refusal_accuracy_unanswerable']}",
              f"- By category: {qa['by_category']}", "", "### Failures", ""]
    fails = [x for x in qa["results"] if not x["passed"]]
    lines += [f"- {x['id']} {x['question']} -> {x['answer'][:120]!r}" for x in fails] or ["None."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None, help="directory for results.json / results.md")
    args = parser.parse_args()

    settings = get_settings()
    service = HLDService()
    doc = service.process(settings.sample_data_dir / "sample_hld.pdf")
    did = doc["document_id"]
    eval_dir = settings.evaluation_data_dir
    truth = json.loads((eval_dir / "ground_truth_entities.json").read_text(encoding="utf-8"))
    cases = json.loads((eval_dir / "qa_set.json").read_text(encoding="utf-8"))

    ext = extraction_metrics(service, did, truth)
    qa = qa_metrics(service, did, cases)
    config = {
        "embedding_model": settings.embedding_model if settings.embeddings_enabled else "disabled (BM25 only)",
        "retrieval": "hybrid BM25 + vector (RRF)" if service.vector_store() and settings.embeddings_enabled else "BM25",
        "vector_store": "ChromaDB (persistent, per-document collection)",
        "llm_provider": settings.llm_provider,
        "indexed_chunks": doc.get("indexed_chunks", 0),
    }

    indep = independent_eval(service)
    print(to_markdown(config, ext, qa))
    print("INDEPENDENT", json.dumps({k: {m: v[m] for m in ("accuracy", "answerable_accuracy", "refusal_accuracy")} for k, v in indep.items()}))
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "results.json").write_text(
            json.dumps({"config": config, "extraction": ext, "qa": qa, "independent": indep}, indent=2), encoding="utf-8")
        (out / "results.md").write_text(to_markdown(config, ext, qa), encoding="utf-8")
    failed = ext["overall"]["recall"] < 1.0 or any(not x["passed"] for x in qa["results"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
