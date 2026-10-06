from __future__ import annotations

from app.extraction.structured_model import StructuredModel


def _pages(*pages: int | None) -> str:
    unique = sorted({p for p in pages if p})
    return ", ".join(str(p) for p in unique) or "n/a"


def build_component_report(model: StructuredModel, name: str, findings: list[dict],
                           chunks: list[dict], metadata: dict) -> str | None:
    """Cited one-component summary: role, interfaces, ports, signals, dependencies, findings."""
    comp = next((c for c in model.components if c.name == name), None)
    if comp is None:
        return None

    provides = [i for i in model.interfaces if i.provider == name]
    requires = [i for i in model.interfaces if i.consumer == name]
    ports = [p for p in model.ports if p.component == name]
    sends = [s for s in model.signals if s.source == name]
    receives = [s for s in model.signals if s.destination == name]
    deps = [d for d in model.dependencies if d.source == name]
    related = [f for f in findings if name in f["title"] + f["description"]
               or any(name in (e.get("excerpt") or "") for e in f["evidence"])]
    mentions = [c for c in chunks if name in c["text"]]

    out = [
        f"# Component report: {name}",
        "",
        f"Source: {metadata['filename']} ({metadata['version']}), document `{metadata['document_id']}`",
        "",
        "> Generated from the document tables; every statement cites its page. "
        "Requires engineering review before use.",
        "",
        f"**Role:** {comp.role} (page {comp.page})  ",
        f"**Responsibility:** {comp.responsibility}",
        "",
        "## Interfaces",
    ]
    out += [f"- Provides **{i.name}** to {i.consumer} carrying {', '.join(i.signals) or 'no signals'} "
            f"(page {i.page})" for i in provides]
    out += [f"- Requires **{i.name}** from {i.provider} carrying {', '.join(i.signals) or 'no signals'} "
            f"(page {i.page})" for i in requires]
    if not provides and not requires:
        out.append("- None declared.")

    out += ["", "## Ports"]
    out += [f"- {p.name} — {p.direction} on {p.interface} (page {p.page})" for p in ports] or ["- None."]

    out += ["", "## Signals"]
    out += [f"- Sends {s.name} ({s.data_type}) to {s.destination} (page {s.page})" for s in sends]
    out += [f"- Receives {s.name} ({s.data_type}) from {s.source} (page {s.page})" for s in receives]
    if not sends and not receives:
        out.append("- None.")

    out += ["", "## Dependencies"]
    out += [f"- {d.relationship} {d.target}: {d.reason} (page {d.page})" for d in deps] or ["- None."]

    out += ["", "## Validation findings touching this component"]
    out += [f"- [{f['severity'].upper()}] {f['title']} ({f['rule_id']})" for f in related] or [
        "- None detected."]

    all_pages = _pages(comp.page, *(i.page for i in provides + requires), *(p.page for p in ports),
                       *(c["page_number"] for c in mentions))
    out += ["", f"**Cited pages:** {all_pages}", ""]
    return "\n".join(out)
