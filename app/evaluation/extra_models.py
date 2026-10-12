"""Supplementary taught techniques: naive Bayes, a neural network (MLP) and k-means clustering.

python -m app.evaluation.extra_models

Uses the same dataset, features and nested leave-one-document-out protocol as train_answerability.py, but does
NOT change the production model: it adds comparison evidence for further standard ML techniques.
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import (
    adjusted_rand_score,
    f1_score,
    normalized_mutual_info_score,
    roc_auc_score,
    silhouette_score,
)
from sklearn.model_selection import GridSearchCV, GroupKFold, LeaveOneGroupOut
from sklearn.naive_bayes import GaussianNB
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.core.config import PROJECT_ROOT
from app.evaluation.tracking import log_run
from app.rag.hybrid import FEATURE_NAMES

warnings.filterwarnings("ignore")
SEED = 42

MODELS = {
    "naive_bayes (Gaussian)": (
        Pipeline([("sc", StandardScaler()), ("m", GaussianNB())]),
        {"m__var_smoothing": [1e-9, 1e-6, 1e-3, 1e-1]}),
    "neural_network (MLP)": (
        Pipeline([("sc", StandardScaler()), ("m", MLPClassifier(max_iter=2000, random_state=SEED, early_stopping=True))]),
        {"m__hidden_layer_sizes": [(8,), (16,), (32, 16)], "m__alpha": [1e-4, 1e-2, 1e-1]}),
}


def nested(X, y, groups, est, space):
    oof = np.zeros(len(y))
    aucs = []
    for tr, va in LeaveOneGroupOut().split(X, y, groups):
        inner = GridSearchCV(est, space, scoring="roc_auc", cv=GroupKFold(n_splits=5), n_jobs=-1)
        inner.fit(X[tr], y[tr], groups=groups[tr])
        oof[va] = inner.predict_proba(X[va])[:, 1]
        aucs.append(roc_auc_score(y[va], oof[va]))
    best_f1 = max(f1_score(y, (oof >= t).astype(int)) for t in np.linspace(0.05, 0.95, 91))
    return {"cv_auc_mean": round(float(np.mean(aucs)), 4), "cv_auc_std": round(float(np.std(aucs)), 4),
            "f1_at_best_threshold": round(float(best_f1), 4)}


def main() -> None:
    root = PROJECT_ROOT / "data" / "evaluation"
    df = pd.read_csv(root / "answerability_dataset.csv")
    dev, test = df[df.split == "dev"], df[df.split == "test"]
    X, y, g = dev[FEATURE_NAMES].to_numpy(), dev.answerable.to_numpy(), dev.doc.to_numpy()

    results = {}
    for name, (est, space) in MODELS.items():
        print("nested CV:", name)
        results[name] = nested(X, y, g, est, space)
        print("  ", results[name])

    # ---- unsupervised: do questions form natural clusters that match answerable / unanswerable? ----
    Z = StandardScaler().fit(X).transform(X)
    Zt = StandardScaler().fit(X).transform(test[FEATURE_NAMES].to_numpy())
    clustering = {}
    for k in (2, 3, 4):
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(Z)
        labels = km.labels_
        majority = {c: int(round(y[labels == c].mean())) for c in range(k)}
        purity = float(np.mean([majority[c] == v for c, v in zip(labels, y)]))
        test_labels = km.predict(Zt)
        test_purity = float(np.mean([majority[c] == v for c, v in zip(test_labels, test.answerable.to_numpy())]))
        clustering[f"k={k}"] = {
            "silhouette": round(float(silhouette_score(Z, labels)), 3),
            "adjusted_rand_vs_label": round(float(adjusted_rand_score(y, labels)), 3),
            "nmi_vs_label": round(float(normalized_mutual_info_score(y, labels)), 3),
            "purity_dev": round(purity, 3), "purity_test_documents": round(test_purity, 3),
            "cluster_answerable_share": {str(c): round(float(y[labels == c].mean()), 2) for c in range(k)},
        }
        print("k-means", k, clustering[f"k={k}"])

    rf = json.loads((root / "results" / "answerability_report.json").read_text(encoding="utf-8"))["model_comparison"]["random_forest"]
    report = {"supplementary_models_nested_cv": results,
              "reference_random_forest": {k: rf[k] for k in ("cv_auc_mean", "cv_auc_std", "f1")},
              "kmeans_clustering": clustering,
              "note": "Production model unchanged (random forest). Differences among the top models are within one standard deviation."}
    out = root / "results" / "extra_models.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log_run("extra_models", {"models": list(MODELS)}, {n: r["cv_auc_mean"] for n, r in results.items()}, [str(out)])
    print("saved", Path(out))


if __name__ == "__main__":
    main()
