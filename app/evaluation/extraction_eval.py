"""Entity-extraction evaluation over the synthetic corpus (micro-averaged precision/recall per type).

python -m app.evaluation.extraction_eval --label after --out data/evaluation/results
"""
import argparse
import json
import os
import tempfile
from collections import defaultdict
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("VECTOR_DIR", tempfile.mkdtemp(prefix="hld_x_"))
os.environ.setdefault("EMBEDDINGS_ENABLED", "false")  # extraction does not need embeddings

from app.core.config import PROJECT_ROOT  # noqa: E402
from app.services.pipeline import HLDService  # noqa: E402

KINDS = ["component", "interface", "port", "signal", "dependency", "functional_flow"]
SYNTH = PROJECT_ROOT / "data" / "synthetic"
DEV_KEYS = ["powertrain", "adas", "infotainment", "battery", "lighting", "thermal"]
TEST_KEYS = ["steering", "keyless", "wiper"]
KEYS = DEV_KEYS + TEST_KEYS


def evaluate(service: HLDService | None = None, keys: list[str] | None = None) -> dict:
    service = service or HLDService()
    totals = {k: [0, 0, 0] for k in KINDS}  # tp, fp, fn
    per_doc, errors = {}, []
    for key in keys or KEYS:
        truth = json.loads((SYNTH / f"{key}.truth.json").read_text(encoding="utf-8"))
        doc_id = service.process(SYNTH / f"{key}.pdf")["document_id"]
        found = defaultdict(set)
        for e in service.entities(doc_id):
            found[e["entity_type"]].add(e["name"])
        doc = {}
        for kind in KINDS:
            exp, got = set(truth[kind]), found[kind]
            tp, fp, fn = len(exp & got), len(got - exp), len(exp - got)
            totals[kind][0] += tp
            totals[kind][1] += fp
            totals[kind][2] += fn
            doc[kind] = {"tp": tp, "fp": fp, "fn": fn}
            for name in sorted(exp - got):
                errors.append({"doc": key, "type": kind, "error": "missed", "name": name})
            for name in sorted(got - exp):
                errors.append({"doc": key, "type": kind, "error": "spurious", "name": name})
        per_doc[key] = doc
    summary = {}
    for kind, (tp, fp, fn) in totals.items():
        summary[kind] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(tp / (tp + fp), 3) if tp + fp else 0.0,
            "recall": round(tp / (tp + fn), 3) if tp + fn else 0.0,
        }
    tp, fp, fn = (sum(v[i] for v in totals.values()) for i in range(3))
    p, r = tp / (tp + fp), tp / (tp + fn)
    summary["overall"] = {"precision": round(p, 3), "recall": round(r, 3),
                          "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0}
    return {"summary": summary, "per_document": per_doc, "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="current")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    service = HLDService()
    result = {"dev": evaluate(service, DEV_KEYS), "test": evaluate(service, TEST_KEYS)}
    for split, res in result.items():
        print("==", split, f"({len(res['errors'])} errors)")
        for kind, v in res["summary"].items():
            print(f"{kind:16s}", {k: v[k] for k in v if k in ("precision", "recall", "f1")})
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"extraction_corpus_{args.label}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
