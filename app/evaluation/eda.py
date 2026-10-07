"""Exploratory data analysis of the document corpus and the question dataset.

python -m app.evaluation.eda [--out data/evaluation/results]
Writes eda_summary.json and figures to data/evaluation/figures/.
Run app.evaluation.train_answerability first (it writes answerability_dataset.csv).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import warnings
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("VECTOR_DIR", tempfile.mkdtemp(prefix="hld_eda_"))
os.environ.setdefault("EMBEDDINGS_ENABLED", "false")
warnings.filterwarnings("ignore")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app.chunking.section_chunker import SectionAwareChunker  # noqa: E402
from app.core.config import PROJECT_ROOT  # noqa: E402
from app.evaluation.qa_dataset import DEV_DOCS, TEST_DOCS  # noqa: E402
from app.ingestion.pdf_parser import PDFParser  # noqa: E402
from app.rag.hybrid import FEATURE_NAMES  # noqa: E402
from app.rag.retriever import tokenize  # noqa: E402
from app.services.pipeline import HLDService  # noqa: E402

WRAPPED_ARTIFACT = re.compile(r"\w\s*\n\s*_\s*$")  # "DoorStatus Out\n_" produced by PDF table wrapping


def corpus_stats(service: HLDService) -> pd.DataFrame:
    rows = []
    parser, chunker = PDFParser(), SectionAwareChunker()
    for split, registry in (("dev", DEV_DOCS), ("test", TEST_DOCS)):
        for name, path in registry.items():
            doc = parser.parse(path)
            chunks = chunker.chunk_document(doc, name, "v1")
            cells = [c for p in doc.pages for t in p.tables for r in t for c in r]
            words = [len(c.text.split()) for c in chunks]
            all_text = " ".join(p.text for p in doc.pages)
            rows.append({
                "doc": name, "split": split, "pages": doc.page_count,
                "words": doc.total_word_count,
                "words_per_page": round(doc.total_word_count / doc.page_count, 1),
                "tables": sum(len(p.tables) for p in doc.pages),
                "table_cells": len(cells),
                "empty_cells": sum(1 for c in cells if not str(c).strip()),
                "wrapped_underscore_cells": sum(1 for c in cells if WRAPPED_ARTIFACT.search(str(c))),
                "headings": sum(len(p.headings) for p in doc.pages),
                "low_text_pages": len(doc.low_text_pages), "scanned_pages": len(doc.scanned_pages),
                "chunks": len(chunks), "chunk_words_mean": round(float(np.mean(words)), 1),
                "chunk_words_max": max(words), "duplicate_chunks": len(chunks) - len({c.text for c in chunks}),
                "vocab": len(set(tokenize(all_text))),
                "identifiers": len(set(re.findall(r"\b[A-Za-z]+(?:[A-Z][a-z0-9]+)+\b|\b\w+_(?:In|Out)\b", all_text))),
                "_chunk_words": words,
            })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(PROJECT_ROOT / "data" / "evaluation" / "results"))
    args = parser.parse_args()
    out = Path(args.out)
    fig_dir = out.parent / "figures"
    out.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    service = HLDService()
    docs = corpus_stats(service)
    chunk_words = [w for ws in docs["_chunk_words"] for w in ws]
    docs = docs.drop(columns=["_chunk_words"])

    csv = out.parent / "answerability_dataset.csv"
    qa = pd.read_csv(csv)
    qa["q_len_words"] = qa.question.str.split().str.len()

    # ---- leakage and balance checks ----
    dev_docs, test_docs = set(qa[qa.split == "dev"].doc), set(qa[qa.split == "test"].doc)
    q_dev, q_test = set(qa[qa.split == "dev"].question), set(qa[qa.split == "test"].question)
    checks = {
        "documents_shared_between_dev_and_test": sorted(dev_docs & test_docs),
        "identical_questions_in_dev_and_test": len(q_dev & q_test),
        "identical_question_share_of_test": round(len(q_dev & q_test) / max(len(q_test), 1), 3),
        "note": "Question templates are shared across splits by design (the task is the same); documents are disjoint, "
                "so a model cannot memorise a document's content. Overlapping identical questions are off-topic "
                "sentences, which are unanswerable in every document.",
        "missing_values": int(qa[FEATURE_NAMES].isna().sum().sum()),
        "duplicate_rows": int(qa.duplicated(subset=["doc", "question"]).sum()),
        "class_balance": qa.groupby(["split", "answerable"]).size().unstack().to_dict(),
        "category_counts": qa.category.value_counts().to_dict(),
    }

    corr = qa[FEATURE_NAMES].corr().round(2)
    high_corr = [(a, b, float(corr.loc[a, b])) for i, a in enumerate(FEATURE_NAMES) for b in FEATURE_NAMES[i + 1:]
                 if abs(corr.loc[a, b]) >= 0.85]
    by_class = qa.groupby("answerable")[FEATURE_NAMES].mean().round(3).to_dict(orient="index")

    summary = {
        "documents": docs.to_dict(orient="records"),
        "totals": {"documents": len(docs), "pages": int(docs.pages.sum()), "words": int(docs.words.sum()),
                   "tables": int(docs.tables.sum()), "chunks": int(docs.chunks.sum()),
                   "wrapped_underscore_cells": int(docs.wrapped_underscore_cells.sum()),
                   "scanned_pages": int(docs.scanned_pages.sum())},
        "chunk_words": {"mean": round(float(np.mean(chunk_words)), 1), "median": float(np.median(chunk_words)),
                        "max": int(max(chunk_words)), "p90": float(np.percentile(chunk_words, 90))},
        "quality_checks": checks, "high_feature_correlations": high_corr,
        "feature_means_by_class": by_class,
        "question_length_words": {"answerable": round(float(qa[qa.answerable == 1].q_len_words.mean()), 1),
                                  "unanswerable": round(float(qa[qa.answerable == 0].q_len_words.mean()), 1)},
    }
    (out / "eda_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # ---- figures ----
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.4))
    order = docs.sort_values(["split", "doc"])
    colors = ["#2E75B6" if s == "dev" else "#ED7D31" for s in order.split]
    ax[0].barh(order.doc, order.words, color=colors); ax[0].set_title("Words per document")
    ax[1].barh(order.doc, order.tables, color=colors); ax[1].set_title("Tables per document")
    ax[2].hist(chunk_words, bins=15, color="#2E75B6"); ax[2].set_title("Chunk length (words)")
    ax[2].axvline(250, color="r", ls="--", lw=0.8)
    ax[2].text(250, ax[2].get_ylim()[1] * 0.9, " chunk size 250", color="r", fontsize=7)
    fig.suptitle("Corpus overview (blue = development, orange = held-out)", fontsize=9)
    plt.tight_layout(); plt.savefig(fig_dir / "eda_corpus.png", dpi=130); plt.close()

    fig, ax = plt.subplots(1, 3, figsize=(11, 3.4))
    cats = qa.category.value_counts()
    ax[0].barh(cats.index[::-1], cats.values[::-1], color="#2E75B6"); ax[0].set_title("Questions per category", fontsize=9)
    ax[0].tick_params(axis="y", labelsize=6)
    for name, a in (("sem_top1", ax[1]), ("coverage", ax[2])):
        a.hist(qa[qa.answerable == 1][name], bins=20, alpha=0.6, label="answerable")
        a.hist(qa[qa.answerable == 0][name], bins=20, alpha=0.6, label="unanswerable")
        a.set_title(f"Feature: {name}", fontsize=9); a.legend(fontsize=7)
    plt.tight_layout(); plt.savefig(fig_dir / "eda_questions.png", dpi=130); plt.close()

    plt.figure(figsize=(6.2, 5))
    plt.imshow(corr.to_numpy(), cmap="coolwarm", vmin=-1, vmax=1)
    plt.xticks(range(len(FEATURE_NAMES)), FEATURE_NAMES, rotation=70, fontsize=7)
    plt.yticks(range(len(FEATURE_NAMES)), FEATURE_NAMES, fontsize=7)
    plt.colorbar(shrink=0.8); plt.title("Feature correlation matrix"); plt.tight_layout()
    plt.savefig(fig_dir / "eda_correlation.png", dpi=130); plt.close()

    print("totals:", summary["totals"])
    print("chunk words:", summary["chunk_words"])
    print("checks:", {k: v for k, v in checks.items() if k not in ("note", "category_counts")})
    print("high correlations:", high_corr)


if __name__ == "__main__":
    main()
