from __future__ import annotations

from dataclasses import asdict

from app.extraction.structured_model import StructuredModel
from app.graph.builder import build_graph

# category -> (attribute on StructuredModel, key function, compared fields)
_CATEGORIES = {
    "components": ("components", lambda x: x.name, ("role", "responsibility")),
    "interfaces": ("interfaces", lambda x: x.name, ("provider", "consumer", "signals")),
    "ports": ("ports", lambda x: x.name, ("component", "direction", "interface")),
    "signals": ("signals", lambda x: x.name, ("data_type", "source", "destination")),
    "dependencies": (
        "dependencies",
        lambda x: f"{x.source} {x.relationship} {x.target}",
        ("reason",),
    ),
}


def compare_models(old: StructuredModel, new: StructuredModel) -> dict:
    """Structured revision diff plus a change-impact set from the combined graphs."""
    result: dict = {"categories": {}, "summary": {}}
    changed_names: set[str] = set()
    removed_names: set[str] = set()

    for cat, (attr, key, fields) in _CATEGORIES.items():
        o = {key(x): x for x in getattr(old, attr)}
        n = {key(x): x for x in getattr(new, attr)}
        added = sorted(set(n) - set(o))
        removed = sorted(set(o) - set(n))
        modified = []
        for name in sorted(set(o) & set(n)):
            diffs = {
                f: {"old": getattr(o[name], f), "new": getattr(n[name], f)}
                for f in fields
                if getattr(o[name], f) != getattr(n[name], f)
            }
            if diffs:
                modified.append({"name": name, "changes": diffs})
        result["categories"][cat] = {
            "added": [asdict(n[a]) for a in added],
            "removed": [asdict(o[r]) for r in removed],
            "modified": modified,
        }
        result["summary"][cat] = {
            "added": len(added), "removed": len(removed), "modified": len(modified),
        }
        if cat != "dependencies":
            changed_names.update(added)
            changed_names.update(m["name"] for m in modified)
            removed_names.update(removed)
        else:
            for dep in [*added, *removed]:
                src, _, tgt = dep.split(" ")
                changed_names.update({src, tgt})

    result["impact"] = _impact(old, new, changed_names, removed_names)
    result["summary"]["total_changes"] = sum(
        v["added"] + v["removed"] + v["modified"]
        for k, v in result["summary"].items()
        if k != "total_changes"
    )
    return result


def _impact(old: StructuredModel, new: StructuredModel,
            changed: set[str], removed: set[str]) -> list[dict]:
    """Elements connected (within 2 hops, in either revision) to something that changed."""
    g_old, g_new = build_graph(old), build_graph(new)
    impacted: dict[str, dict] = {}
    for name in sorted(changed | removed):
        for graph, label in ((g_new, "new"), (g_old, "old")):
            for hit in graph.impact(name, max_depth=2):
                if hit["name"] in changed or hit["name"] in removed:
                    continue
                impacted.setdefault(
                    hit["name"],
                    {"name": hit["name"], "type": hit["type"], "because_of": set(), "revision": label},
                )["because_of"].add(name)
    return [
        {**v, "because_of": sorted(v["because_of"])}
        for v in sorted(impacted.values(), key=lambda v: v["name"])
    ]
