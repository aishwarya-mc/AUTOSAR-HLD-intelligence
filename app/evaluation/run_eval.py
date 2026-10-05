"""Offline evaluation of the Q&A pipeline: python -m app.evaluation.run_eval"""
import json
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.core.config import get_settings  # noqa: E402
from app.services.pipeline import HLDService  # noqa: E402


def main() -> int:
    settings = get_settings()
    service = HLDService()
    doc = service.process(settings.sample_data_dir / "sample_hld.pdf")
    answerer = service.answerer(doc["document_id"])
    cases = json.loads((settings.evaluation_data_dir / "qa_set.json").read_text(encoding="utf-8"))

    passed = 0
    for case in cases:
        r = answerer.answer(case["question"])
        if case.get("answerable", True):
            ok = (
                r.grounded
                and all(t in r.answer for t in case["must_contain"])
                and any(c.page_number == case["page"] for c in r.citations)
            )
        else:
            ok = not r.grounded
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {case['question']}")
    print(f"\n{passed}/{len(cases)} passed")
    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
