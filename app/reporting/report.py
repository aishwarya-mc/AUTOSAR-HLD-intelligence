from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_None._\n"
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def build_report(metadata: dict, model: dict, findings: list[dict],
                 comparison: dict | None = None, other: dict | None = None) -> str:
    """Evidence-backed Markdown engineering report for one HLD revision."""
    sev = Counter(f["severity"] for f in findings)
    out = [
        f"# HLD Analysis Report: {metadata['filename']}",
        "",
        f"- Document ID: `{metadata['document_id']}`",
        f"- Version: {metadata['version']}",
        f"- Pages: {metadata.get('page_count', '?')}",
        f"- Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "> AI-generated findings are advisory and require human engineering review.",
        "",
        "## 1. Architecture Summary",
        "",
        _md_table(
            ["Element", "Count"],
            [[k.title(), str(len(model[k]))] for k in
             ("components", "interfaces", "ports", "signals", "dependencies")],
        ),
        "### Components",
        _md_table(["Component", "Role", "Page"],
                  [[c["name"], c["role"], str(c["page"])] for c in model["components"]]),
        "### Interfaces",
        _md_table(["Interface", "Provider", "Consumer", "Signals", "Page"],
                  [[i["name"], i["provider"], i["consumer"], ", ".join(i["signals"]), str(i["page"])]
                   for i in model["interfaces"]]),
        "### Dependencies",
        _md_table(["Source", "Relationship", "Target", "Page"],
                  [[d["source"], d["relationship"], d["target"], str(d["page"])]
                   for d in model["dependencies"]]),
        "## 2. Validation Findings",
        "",
        f"Critical: {sev.get('critical', 0)} · Warning: {sev.get('warning', 0)} · "
        f"Info: {sev.get('info', 0)}",
        "",
    ]
    if findings:
        for f in findings:
            ev = f["evidence"][0] if f["evidence"] else {}
            review = (f.get("review") or {}).get("status", "pending")
            out += [
                f"### [{f['severity'].upper()}] {f['title']}",
                f"- Rule: {f['rule_id']} · Confidence: {f['confidence']:.2f} · Review: {review}",
                f"- {f['description']}",
                f"- Evidence: section {ev.get('section', 'n/a')}, page {ev.get('page_number', 'n/a')}"
                f" — `{ev.get('excerpt', '')}`",
                "",
            ]
    else:
        out += ["No inconsistencies detected by the rule set.", ""]

    if comparison:
        s = comparison["summary"]
        out += [
            "## 3. Revision Comparison",
            "",
            f"Compared against `{other['filename']}` ({other['version']}): "
            f"{s['total_changes']} change(s).",
            "",
            _md_table(
                ["Category", "Added", "Removed", "Modified"],
                [[c, str(s[c]["added"]), str(s[c]["removed"]), str(s[c]["modified"])]
                 for c in comparison["categories"]],
            ),
            "### Change impact",
            _md_table(["Element", "Type", "Affected because of"],
                      [[i["name"], i["type"], ", ".join(i["because_of"])] for i in comparison["impact"]]),
        ]
    return "\n".join(out)
