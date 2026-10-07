"""Evaluate the validation rules on seeded defects.

python -m app.evaluation.validation_eval [--out data/evaluation/results]

Each synthetic HLD exists as a clean version and a defective version with four seeded defects
(wrong port direction, dropped dependency, undefined interface on a port, signal endpoint mismatch).
Recall   = seeded defects detected (expected rule fires on the defect's subject)
FP rate  = findings on clean documents; also findings on defective documents not explained by a defect
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("VECTOR_DIR", tempfile.mkdtemp(prefix="hld_val_"))
os.environ.setdefault("EMBEDDINGS_ENABLED", "false")

from app.core.config import PROJECT_ROOT  # noqa: E402
from app.evaluation.extraction_eval import KEYS  # noqa: E402
from app.services.pipeline import HLDService  # noqa: E402

SYNTH = PROJECT_ROOT / "data" / "synthetic"
# rules that a given defect can legitimately trigger as side effects
EXPLAINED = {
    "wrong_direction": {"V003", "V004", "V009"},
    "missing_dependency": {"V005"},
    "undefined_interface_on_port": {"V002", "V004"},
    "signal_endpoint_mismatch": {"V007"},
}


def evaluate(service: HLDService | None = None) -> dict:
    service = service or HLDService()
    detected = total = clean_findings = unexplained = defect_doc_findings = 0
    per_kind: dict[str, list[int]] = {k: [0, 0] for k in EXPLAINED}
    misses, fps = [], []
    for key in KEYS:
        truth = json.loads((SYNTH / f"{key}.truth.json").read_text(encoding="utf-8"))
        clean = service.findings(service.process(SYNTH / f"{key}.pdf")["document_id"])
        clean_findings += len(clean)
        fps += [{"doc": key, "rule": f["rule_id"], "title": f["title"]} for f in clean]

        findings = service.findings(service.process(SYNTH / f"{key}_defect.pdf")["document_id"])
        defect_doc_findings += len(findings)
        allowed = set()
        for d in truth["seeded_defects"]:
            total += 1
            per_kind[d["kind"]][1] += 1
            allowed |= EXPLAINED[d["kind"]]
            hit = any(f["rule_id"] in d["expected_rules"] and d["subject"] in (f["title"] + f["description"])
                      for f in findings)
            detected += hit
            per_kind[d["kind"]][0] += hit
            if not hit:
                misses.append({"doc": key, **d})
        for f in findings:
            if f["rule_id"] not in allowed:
                unexplained += 1
                fps.append({"doc": key, "rule": f["rule_id"], "title": f["title"], "in": "defect version"})
    return {
        "documents": len(KEYS), "seeded_defects": total, "detected": detected,
        "defect_recall": round(detected / total, 3),
        "recall_by_kind": {k: f"{a}/{b}" for k, (a, b) in per_kind.items()},
        "findings_on_clean_documents": clean_findings,
        "findings_on_defect_documents": defect_doc_findings,
        "unexplained_findings_on_defect_documents": unexplained,
        "false_positive_findings": fps, "missed_defects": misses,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    res = evaluate()
    print({k: v for k, v in res.items() if k not in ("false_positive_findings", "missed_defects")})
    for m in res["missed_defects"]:
        print("MISSED", m)
    for f in res["false_positive_findings"]:
        print("FP", f)
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "validation_eval.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
