"""Train and evaluate the answerability classifier.

python -m app.evaluation.train_answerability [--out data/evaluation/results] [--no-save]

Protocol (no leakage):
  * Training pool  = 6 `dev` synthetic documents. Model selection uses *nested* leave-one-document-out
    cross-validation (outer folds estimate generalisation to an unseen document, inner folds tune
    hyper-parameters), so no document is ever in both train and validation.
  * The 5 `test` documents (3 unseen synthetic domains + the sample HLD and its revision) are used
    only once, after the model and decision threshold are fixed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("VECTOR_DIR", tempfile.mkdtemp(prefix="hld_train_vec_"))
warnings.filterwarnings("ignore")

import joblib  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import sklearn  # noqa: E402
from sklearn.calibration import CalibratedClassifierCV, calibration_curve  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    ConfusionMatrixDisplay,
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import GridSearchCV, GroupKFold, LeaveOneGroupOut, learning_curve  # noqa: E402
from sklearn.neighbors import KNeighborsClassifier  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.svm import SVC  # noqa: E402
from sklearn.tree import DecisionTreeClassifier  # noqa: E402

from app.core.config import PROJECT_ROOT  # noqa: E402
from app.evaluation.qa_dataset import build_dataset  # noqa: E402
from app.evaluation.tracking import git_sha, log_run  # noqa: E402
from app.rag.hybrid import FEATURE_NAMES  # noqa: E402

SEED = 42
MODEL_VERSION = "1.0.0"
RULE_GATE = 0.60  # the hand-set threshold used before this model existed

SEARCH_SPACES = {
    "logistic_regression": (
        Pipeline([("sc", StandardScaler()), ("m", LogisticRegression(max_iter=2000))]),
        {"m__C": [0.01, 0.1, 1, 10, 100]}),
    "svm_rbf": (
        Pipeline([("sc", StandardScaler()), ("m", SVC(probability=True, random_state=SEED))]),
        {"m__C": [0.5, 1, 5, 20], "m__gamma": ["scale", 0.05, 0.2]}),
    "knn": (
        Pipeline([("sc", StandardScaler()), ("m", KNeighborsClassifier())]),
        {"m__n_neighbors": [3, 7, 15, 31]}),
    "decision_tree": (
        DecisionTreeClassifier(random_state=SEED), {"max_depth": [2, 3, 4, 6, None]}),
    "random_forest": (
        RandomForestClassifier(n_estimators=200, random_state=SEED),
        {"max_depth": [3, 5, None], "min_samples_leaf": [1, 3, 5]}),
    "gradient_boosting": (
        GradientBoostingClassifier(random_state=SEED),
        {"n_estimators": [50, 150], "max_depth": [2, 3], "learning_rate": [0.05, 0.1]}),
}


def metrics_at(y, p, threshold) -> dict:
    pred = (p >= threshold).astype(int)
    pr, rc, f1, _ = precision_recall_fscore_support(y, pred, average="binary", zero_division=0)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {"accuracy": round(accuracy_score(y, pred), 4), "precision": round(pr, 4),
            "recall": round(rc, 4), "f1": round(f1, 4),
            "roc_auc": round(roc_auc_score(y, p), 4), "brier": round(brier_score_loss(y, p), 4),
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}


def best_threshold(y, p) -> float:
    grid = np.linspace(0.05, 0.95, 91)
    scores = [f1_score(y, (p >= t).astype(int)) for t in grid]
    best = max(scores)
    # choose the middle of the plateau of near-optimal thresholds for stability
    good = [t for t, s in zip(grid, scores) if s >= best - 1e-9]
    return float(good[len(good) // 2])


def nested_cv(X, y, groups, name, estimator, space):
    """Outer leave-one-document-out; inner grouped CV tunes hyper-parameters."""
    outer = LeaveOneGroupOut()
    oof = np.zeros(len(y))
    fold_auc, chosen, train_auc = [], [], []
    for tr, va in outer.split(X, y, groups):
        inner = GridSearchCV(estimator, space, scoring="roc_auc",
                             cv=GroupKFold(n_splits=min(5, len(set(groups[tr])))), n_jobs=-1)
        inner.fit(X[tr], y[tr], groups=groups[tr])
        oof[va] = inner.predict_proba(X[va])[:, 1]
        fold_auc.append(roc_auc_score(y[va], oof[va]))
        train_auc.append(roc_auc_score(y[tr], inner.predict_proba(X[tr])[:, 1]))
        chosen.append(inner.best_params_)
    return {"oof": oof, "fold_auc": fold_auc, "train_auc": float(np.mean(train_auc)), "chosen": chosen}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(PROJECT_ROOT / "data" / "evaluation" / "results"))
    parser.add_argument("--no-save", action="store_true", help="do not write the model artifact")
    args = parser.parse_args()
    out = Path(args.out)
    fig_dir = out.parent / "figures"
    out.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    print("building dataset ...")
    df = build_dataset()
    csv = out.parent / "answerability_dataset.csv"
    df.drop(columns=["terms", "gold_sections", "top_sections"]).to_csv(csv, index=False)
    data_hash = hashlib.sha256(csv.read_bytes()).hexdigest()[:16]

    dev, test = df[df.split == "dev"], df[df.split == "test"]
    Xd, yd, gd = dev[FEATURE_NAMES].to_numpy(), dev.answerable.to_numpy(), dev.doc.to_numpy()
    Xt, yt = test[FEATURE_NAMES].to_numpy(), test.answerable.to_numpy()
    print(f"dev {len(dev)} rows / {dev.doc.nunique()} docs, test {len(test)} rows / {test.doc.nunique()} docs")

    # ---- model comparison (nested CV on dev documents only) ----
    results, oofs = {}, {}
    rule_scores = dev.sem_top1.to_numpy()
    results["rule: sem_top1 >= 0.60 (previous)"] = {
        "cv_auc_mean": round(roc_auc_score(yd, rule_scores), 4), "cv_auc_std": 0.0,
        **{k: v for k, v in metrics_at(yd, rule_scores, RULE_GATE).items() if k in ("f1", "precision", "recall")}}
    oofs["rule"] = rule_scores
    results["majority class"] = {"cv_auc_mean": 0.5, "cv_auc_std": 0.0, "f1": 0.667, "precision": 0.5, "recall": 1.0}
    for name, (est, space) in SEARCH_SPACES.items():
        print("  nested CV:", name)
        r = nested_cv(Xd, yd, gd, name, est, space)
        oofs[name] = r["oof"]
        th = best_threshold(yd, r["oof"])
        m = metrics_at(yd, r["oof"], th)
        results[name] = {
            "cv_auc_mean": round(float(np.mean(r["fold_auc"])), 4),
            "cv_auc_std": round(float(np.std(r["fold_auc"])), 4),
            "train_auc_mean": round(r["train_auc"], 4),
            "overfit_gap": round(r["train_auc"] - float(np.mean(r["fold_auc"])), 4),
            "f1": m["f1"], "precision": m["precision"], "recall": m["recall"], "brier": m["brier"],
            "threshold": round(th, 3), "chosen_params": r["chosen"][0],
        }
    ranked = sorted((n for n in results if n in SEARCH_SPACES), key=lambda n: -results[n]["cv_auc_mean"])
    best = ranked[0]
    # prefer a simpler model when it is within one standard error of the best
    for cand in ["logistic_regression", "decision_tree"]:
        if cand in results and results[cand]["cv_auc_mean"] >= results[best]["cv_auc_mean"] - results[best]["cv_auc_std"] / 2:
            best = cand
            break
    print("selected:", best)

    # ---- final fit on all dev data ----
    est, space = SEARCH_SPACES[best]
    search = GridSearchCV(est, space, scoring="roc_auc", cv=GroupKFold(n_splits=6), n_jobs=-1)
    search.fit(Xd, yd, groups=gd)
    final = search.best_estimator_
    if best not in ("logistic_regression",):  # make probabilities trustworthy as a confidence score
        final = CalibratedClassifierCV(search.best_estimator_, method="sigmoid", cv=5).fit(Xd, yd)
    threshold = best_threshold(yd, oofs[best])

    # ---- final evaluation on unseen documents ----
    p_test = final.predict_proba(Xt)[:, 1]
    test_metrics = metrics_at(yt, p_test, threshold)
    rule_test = metrics_at(yt, test.sem_top1.to_numpy(), RULE_GATE)
    per_doc = {d: metrics_at(g.answerable.to_numpy(), final.predict_proba(g[FEATURE_NAMES].to_numpy())[:, 1], threshold)
               for d, g in test.groupby("doc")}
    pred = (p_test >= threshold).astype(int)
    rule_pred = (test.sem_top1.to_numpy() >= RULE_GATE).astype(int)
    by_cat = {}
    for cat, g in test.assign(pred=pred, rule_pred=rule_pred).groupby("category"):
        by_cat[cat] = {"n": len(g), "model_correct": round(float((g.pred == g.answerable).mean()), 3),
                       "rule_correct": round(float((g.rule_pred == g.answerable).mean()), 3)}

    # ---- feature importance, ablation and PCA ----
    perm = permutation_importance(final, Xt, yt, scoring="roc_auc", n_repeats=20, random_state=SEED)
    importance = {f: round(float(v), 4) for f, v in sorted(zip(FEATURE_NAMES, perm.importances_mean), key=lambda kv: -kv[1])}
    ablation = {}
    for f in FEATURE_NAMES:
        keep = [i for i, n in enumerate(FEATURE_NAMES) if n != f]
        m = Pipeline([("sc", StandardScaler()), ("m", LogisticRegression(max_iter=2000, C=1.0))]).fit(Xd[:, keep], yd)
        ablation[f] = round(roc_auc_score(yt, m.predict_proba(Xt[:, keep])[:, 1]), 4)
    base_lr = Pipeline([("sc", StandardScaler()), ("m", LogisticRegression(max_iter=2000, C=1.0))]).fit(Xd, yd)
    ablation["(all features)"] = round(roc_auc_score(yt, base_lr.predict_proba(Xt)[:, 1]), 4)
    scaler = StandardScaler().fit(Xd)
    pca_full = PCA().fit(scaler.transform(Xd))
    pca_curve = {}
    for k in range(1, len(FEATURE_NAMES) + 1):
        pca = PCA(n_components=k).fit(scaler.transform(Xd))
        m = LogisticRegression(max_iter=2000).fit(pca.transform(scaler.transform(Xd)), yd)
        pca_curve[k] = {"explained_variance": round(float(pca.explained_variance_ratio_.sum()), 4),
                        "test_auc": round(roc_auc_score(yt, m.predict_proba(pca.transform(scaler.transform(Xt)))[:, 1]), 4)}

    # ---- figures ----
    plt.figure(figsize=(6, 5))
    for name in ["rule", *SEARCH_SPACES]:
        fpr, tpr, _ = roc_curve(yd, oofs[name])
        plt.plot(fpr, tpr, label=f"{'rule sem>=0.60' if name == 'rule' else name} ({roc_auc_score(yd, oofs[name]):.3f})")
    plt.plot([0, 1], [0, 1], "k--", lw=0.7)
    plt.xlabel("False positive rate"); plt.ylabel("True positive rate")
    plt.title("Nested CV ROC (leave-one-document-out)"); plt.legend(fontsize=7); plt.tight_layout()
    plt.savefig(fig_dir / "roc_cv.png", dpi=130); plt.close()

    fig, ax = plt.subplots(figsize=(4.2, 4))
    ConfusionMatrixDisplay(confusion_matrix(yt, pred, labels=[0, 1]), display_labels=["unanswerable", "answerable"]).plot(ax=ax, colorbar=False)
    ax.set_title(f"Held-out test documents ({best})"); plt.tight_layout()
    plt.savefig(fig_dir / "confusion_test.png", dpi=130); plt.close()

    sizes, tr_s, va_s = learning_curve(est.set_params(**search.best_params_), Xd, yd, groups=gd,
                                       cv=GroupKFold(n_splits=6), scoring="roc_auc",
                                       train_sizes=np.linspace(0.2, 1.0, 6), n_jobs=-1)
    plt.figure(figsize=(5.5, 4))
    plt.plot(sizes, tr_s.mean(1), "o-", label="train"); plt.plot(sizes, va_s.mean(1), "o-", label="validation (unseen doc)")
    plt.fill_between(sizes, va_s.mean(1) - va_s.std(1), va_s.mean(1) + va_s.std(1), alpha=0.15)
    plt.xlabel("training examples"); plt.ylabel("ROC-AUC"); plt.title(f"Learning curve ({best})")
    plt.legend(); plt.tight_layout(); plt.savefig(fig_dir / "learning_curve.png", dpi=130); plt.close()

    frac, mean_pred = calibration_curve(yt, p_test, n_bins=8, strategy="quantile")
    plt.figure(figsize=(4.5, 4)); plt.plot(mean_pred, frac, "o-"); plt.plot([0, 1], [0, 1], "k--", lw=0.7)
    plt.xlabel("predicted probability"); plt.ylabel("observed fraction answerable")
    plt.title("Reliability on test documents"); plt.tight_layout(); plt.savefig(fig_dir / "calibration.png", dpi=130); plt.close()

    plt.figure(figsize=(6, 3.8))
    names, vals = zip(*importance.items())
    plt.barh(names[::-1], vals[::-1]); plt.xlabel("drop in ROC-AUC when permuted")
    plt.title("Permutation importance (test)"); plt.tight_layout(); plt.savefig(fig_dir / "feature_importance.png", dpi=130); plt.close()

    fig, ax = plt.subplots(1, 2, figsize=(9, 3.6))
    ax[0].plot(range(1, len(FEATURE_NAMES) + 1), np.cumsum(pca_full.explained_variance_ratio_), "o-")
    ax[0].set_xlabel("principal components"); ax[0].set_ylabel("cumulative explained variance"); ax[0].set_title("PCA of the 12 features")
    ax[1].plot(list(pca_curve), [v["test_auc"] for v in pca_curve.values()], "o-")
    ax[1].set_xlabel("components kept"); ax[1].set_ylabel("test ROC-AUC"); ax[1].set_title("Logistic regression on PCA features")
    plt.tight_layout(); plt.savefig(fig_dir / "pca_features.png", dpi=130); plt.close()

    # ---- save ----
    metadata = {
        "name": "answerability", "version": MODEL_VERSION, "algorithm": best,
        "created_at": datetime.now(timezone.utc).isoformat(), "git_sha": git_sha(),
        "sklearn_version": sklearn.__version__, "feature_names": FEATURE_NAMES,
        "threshold": round(threshold, 4), "best_params": {k: (v if v is not None else "None") for k, v in search.best_params_.items()},
        "training_documents": sorted(dev.doc.unique()), "test_documents": sorted(test.doc.unique()),
        "n_train": int(len(dev)), "n_test": int(len(test)), "dataset_sha256_16": data_hash,
        "metrics_test": test_metrics, "metrics_rule_baseline_test": rule_test,
        "cv_auc_mean": results[best]["cv_auc_mean"], "seed": SEED,
    }
    report = {"metadata": metadata, "model_comparison": results, "selected": best,
              "test_metrics": test_metrics, "rule_baseline_test": rule_test, "per_test_document": per_doc,
              "by_category_test": by_cat, "permutation_importance": importance, "feature_ablation_auc": ablation,
              "pca": {"explained_variance_ratio": [round(float(v), 4) for v in pca_full.explained_variance_ratio_], "curve": pca_curve},
              "learning_curve": {"train_sizes": sizes.tolist(), "train_auc": tr_s.mean(1).round(4).tolist(), "val_auc": va_s.mean(1).round(4).tolist()}}
    (out / "answerability_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    if not args.no_save:
        for target in (PROJECT_ROOT / "models" / "answerability" / f"v{MODEL_VERSION}",
                       PROJECT_ROOT / "models" / "answerability" / "current"):
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True)
            joblib.dump(final, target / "model.joblib")
            (target / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    log_run("train_answerability", {"selected": best, "params": metadata["best_params"], "threshold": metadata["threshold"],
                                    "n_train": metadata["n_train"], "dataset": data_hash},
            {"cv_auc": results[best]["cv_auc_mean"], **{f"test_{k}": v for k, v in test_metrics.items()},
             "rule_test_f1": rule_test["f1"]}, artifacts=[str(out / "answerability_report.json")])

    print("\n=== model comparison (nested CV AUC mean+-std | F1 at tuned threshold) ===")
    for n, r in results.items():
        print(f"{n:38s} {r['cv_auc_mean']:.3f} +- {r['cv_auc_std']:.3f} | F1 {r.get('f1')}")
    print(f"\nselected: {best}, threshold {threshold:.3f}")
    print("TEST (unseen docs):", test_metrics)
    print("RULE baseline TEST:", rule_test)
    print("by category:", json.dumps(by_cat))
    return 0


if __name__ == "__main__":
    sys.exit(main())
