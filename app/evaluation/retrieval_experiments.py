"""Retrieval method comparison and embedding PCA experiment.

python -m app.evaluation.retrieval_experiments [--out data/evaluation/results]

Gold labels: each generated answerable question knows which HLD sections hold its answer.
Metrics: Recall@1/3/5 (a gold section appears in the top-k chunks) and MRR, per split.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import warnings
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("VECTOR_DIR", tempfile.mkdtemp(prefix="hld_ret_"))
warnings.filterwarnings("ignore")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from fastembed import TextEmbedding  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402

from app.core.config import PROJECT_ROOT  # noqa: E402
from app.evaluation.qa_dataset import DEV_DOCS, TEST_DOCS, build_items  # noqa: E402
from app.evaluation.tracking import log_run  # noqa: E402
from app.rag.embeddings import BGE_QUERY_PREFIX  # noqa: E402
from app.rag.hybrid import RRF_K  # noqa: E402
from app.rag.retriever import BM25Retriever  # noqa: E402
from app.services.pipeline import HLDService  # noqa: E402

BGE, MINILM = "BAAI/bge-small-en-v1.5", "sentence-transformers/all-MiniLM-L6-v2"


def plain_tokenize(text: str) -> list[str]:
    """Baseline tokenizer without CamelCase/underscore splitting."""
    return [t.lower() for t in re.findall(r"[A-Za-z0-9]+", text) if len(t) > 1]


def rrf(*rankings: list[int], k: int = RRF_K, weights: tuple[float, ...] | None = None) -> list[int]:
    score: dict[int, float] = defaultdict(float)
    for w, r in zip(weights or (1.0,) * len(rankings), rankings):
        for pos, idx in enumerate(r):
            score[idx] += w / (k + pos + 1)
    return sorted(score, key=lambda i: -score[i])


def metrics(rank_lists: list[list[int]], gold: list[set[int]]) -> dict:
    hits = {1: 0, 3: 0, 5: 0}
    rr = 0.0
    for ranking, g in zip(rank_lists, gold):
        first = next((p for p, idx in enumerate(ranking) if idx in g), None)
        for k in hits:
            hits[k] += first is not None and first < k
        rr += 1.0 / (first + 1) if first is not None else 0.0
    n = len(gold)
    return {"recall@1": round(hits[1] / n, 3), "recall@3": round(hits[3] / n, 3),
            "recall@5": round(hits[5] / n, 3), "mrr": round(rr / n, 3), "n": n}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(PROJECT_ROOT / "data" / "evaluation" / "results"))
    args = parser.parse_args()
    out = Path(args.out)
    fig_dir = out.parent / "figures"
    out.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    service = HLDService()
    bge, mini = TextEmbedding(BGE), TextEmbedding(MINILM)

    docs = []  # per document: chunks, gold sets, query list, embeddings
    for split, registry in (("dev", DEV_DOCS), ("test", TEST_DOCS)):
        for n, (name, path) in enumerate(registry.items()):
            doc_id = service.process(path)["document_id"]
            chunks = service.chunks(doc_id)
            items = [i for i in build_items(service, doc_id, 7 + n + (100 if split == "test" else 0))
                     if i["answerable"]]
            gold = [{ci for ci, c in enumerate(chunks) if c["section"] in set(i["gold_sections"])} for i in items]
            keep = [k for k, g in enumerate(gold) if g]
            texts = [c["text"] for c in chunks]
            queries = [items[k]["question"] for k in keep]
            docs.append({
                "split": split, "name": name, "chunks": chunks, "texts": texts, "queries": queries,
                "gold": [gold[k] for k in keep],
                "bge_doc": np.array([v for v in bge.embed(texts)]),
                "bge_q": np.array([v for v in bge.embed([BGE_QUERY_PREFIX + q for q in queries])]),
                "mini_doc": np.array([v for v in mini.embed(texts)]),
                "mini_q": np.array([v for v in mini.embed(queries)]),
            })

    def dense(dq, dd):  # cosine similarity on normalised vectors
        dd_n = dd / np.linalg.norm(dd, axis=1, keepdims=True)
        dq_n = dq / np.linalg.norm(dq, axis=1, keepdims=True)
        return [list(np.argsort(-row)) for row in dq_n @ dd_n.T]

    approaches = {
        "BM25 (plain tokens)": lambda d: [[
            next(i for i, c in enumerate(d["chunks"]) if c["chunk_id"] == h.chunk_id)
            for h in BM25Retriever(d["chunks"], tokenizer=plain_tokenize).search(q, top_k=50)]
            for q in d["queries"]],
        "BM25 (CamelCase-aware, used)": lambda d: [[
            next(i for i, c in enumerate(d["chunks"]) if c["chunk_id"] == h.chunk_id)
            for h in BM25Retriever(d["chunks"]).search(q, top_k=50)] for q in d["queries"]],
    }

    def tfidf(d):
        vec = TfidfVectorizer(tokenizer=plain_tokenize, lowercase=False, token_pattern=None)
        mat = vec.fit_transform(d["texts"])
        qs = vec.transform(d["queries"])
        return [list(np.argsort(-row)) for row in (qs @ mat.T).toarray()]

    approaches["TF-IDF cosine"] = tfidf
    approaches["Dense: MiniLM-L6"] = lambda d: dense(d["mini_q"], d["mini_doc"])
    approaches["Dense: BGE-small (used)"] = lambda d: dense(d["bge_q"], d["bge_doc"])

    def hybrid(d):
        lex = approaches["BM25 (CamelCase-aware, used)"](d)
        den = dense(d["bge_q"], d["bge_doc"])
        return [rrf(a, b) for a, b in zip(lex, den)]

    approaches["Hybrid BM25 + BGE, equal weights"] = hybrid

    # Tune the dense weight on dev documents only, then report both splits.
    def weighted(w):
        def run(d):
            lex = approaches["BM25 (CamelCase-aware, used)"](d)
            den = dense(d["bge_q"], d["bge_doc"])
            return [rrf(a, b, weights=(1.0, w)) for a, b in zip(lex, den)]
        return run

    def dev_mrr(w):
        ranks, golds = [], []
        for d in docs:
            if d["split"] == "dev":
                ranks += weighted(w)(d)
                golds += d["gold"]
        return metrics(ranks, golds)["mrr"]

    weight_grid = {w: dev_mrr(w) for w in (1.0, 1.5, 2.0, 3.0, 5.0, 10.0)}
    best_w = max(weight_grid, key=lambda w: (weight_grid[w], -w))
    print("dense-weight grid (dev MRR):", weight_grid, "-> best", best_w)
    approaches[f"Hybrid BM25 + BGE, RRF dense weight {best_w} (tuned on dev)"] = weighted(best_w)

    results = {}
    for name, fn in approaches.items():
        for split in ("dev", "test"):
            ranks, golds = [], []
            for d in docs:
                if d["split"] != split:
                    continue
                ranks += fn(d)
                golds += d["gold"]
            results.setdefault(name, {})[split] = metrics(ranks, golds)
        print(f"{name:34s} dev R@1={results[name]['dev']['recall@1']} MRR={results[name]['dev']['mrr']} | "
              f"test R@1={results[name]['test']['recall@1']} MRR={results[name]['test']['mrr']}")

    # ---- PCA on BGE chunk embeddings: fit on dev chunks, evaluate on test ----
    dev_matrix = np.vstack([d["bge_doc"] for d in docs if d["split"] == "dev"])
    pca_rows = {}
    for k in (4, 8, 16, 32, 64, 384):
        if k == 384:
            tf = lambda x: x  # noqa: E731
            var = 1.0
        else:
            pca = PCA(n_components=k, random_state=0).fit(dev_matrix)
            tf = pca.transform
            var = float(pca.explained_variance_ratio_.sum())
        ranks, golds = [], []
        for d in docs:
            if d["split"] == "test":
                ranks += dense(tf(d["bge_q"]), tf(d["bge_doc"]))
                golds += d["gold"]
        pca_rows[k] = {**metrics(ranks, golds), "explained_variance": round(var, 3)}
        print(f"PCA {k:3d} dims: var={var:.2f} test R@1={pca_rows[k]['recall@1']} MRR={pca_rows[k]['mrr']}")

    # ---- figures ----
    names = list(results)
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(x - 0.2, [results[n]["dev"]["mrr"] for n in names], 0.4, label="dev documents")
    ax.bar(x + 0.2, [results[n]["test"]["mrr"] for n in names], 0.4, label="held-out documents")
    ax.set_xticks(x)
    ax.set_xticklabels([n.replace(" (", "\n(") for n in names], fontsize=7)
    ax.set_ylabel("MRR"); ax.set_ylim(0, 1.05); ax.legend(); ax.set_title("Retrieval method comparison")
    plt.tight_layout(); plt.savefig(fig_dir / "retrieval_comparison.png", dpi=130); plt.close()

    all_doc = np.vstack([d["bge_doc"] for d in docs])
    sections = [c["section"] for d in docs for c in d["chunks"]]
    p2 = PCA(n_components=2, random_state=0).fit_transform(all_doc)
    plt.figure(figsize=(6.2, 4.6))
    for sec in sorted(set(sections)):
        idx = [i for i, s in enumerate(sections) if s == sec]
        plt.scatter(p2[idx, 0], p2[idx, 1], s=14, label=sec[:24])
    plt.legend(fontsize=6, ncol=2); plt.title("PCA of chunk embeddings (BGE-small), coloured by section")
    plt.xlabel("PC1"); plt.ylabel("PC2"); plt.tight_layout()
    plt.savefig(fig_dir / "embedding_pca.png", dpi=130); plt.close()

    plt.figure(figsize=(5.5, 4))
    ks = list(pca_rows)
    plt.plot(ks, [pca_rows[k]["mrr"] for k in ks], "o-", label="test MRR")
    plt.plot(ks, [pca_rows[k]["explained_variance"] for k in ks], "s--", label="explained variance")
    plt.xscale("log", base=2); plt.xlabel("PCA dimensions (of 384)"); plt.legend()
    plt.title("Retrieval vs embedding dimensionality"); plt.tight_layout()
    plt.savefig(fig_dir / "pca_retrieval.png", dpi=130); plt.close()

    report = {"dense_weight_grid_dev_mrr": {str(k): v for k, v in weight_grid.items()}, "best_dense_weight": best_w, "approaches": results, "pca_dense_test": pca_rows,
              "n_documents": {"dev": sum(d["split"] == "dev" for d in docs), "test": sum(d["split"] == "test" for d in docs)}}
    (out / "retrieval_experiments.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    log_run("retrieval_experiments", {"models": [BGE, MINILM]},
            {n: results[n]["test"]["mrr"] for n in names}, [str(out / "retrieval_experiments.json")])


if __name__ == "__main__":
    main()
