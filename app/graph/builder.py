from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from app.extraction.structured_model import StructuredModel


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    relation: str
    page: int | None = None


@dataclass
class ArchitectureGraph:
    """Lightweight in-memory property graph (typed nodes, labelled edges)."""

    nodes: dict[str, str] = field(default_factory=dict)  # name -> type
    edges: list[Edge] = field(default_factory=list)

    def add_node(self, name: str, node_type: str) -> None:
        if name:
            self.nodes.setdefault(name, node_type)

    def add_edge(self, source: str, target: str, relation: str, page: int | None = None) -> None:
        if not source or not target:
            return
        edge = Edge(source, target, relation, page)
        if edge not in self.edges:
            self.edges.append(edge)

    def neighbors(self, name: str) -> list[Edge]:
        return [e for e in self.edges if e.source == name or e.target == name]

    def impact(self, name: str, max_depth: int = 3) -> list[dict]:
        """Everything reachable (either direction) from `name` within max_depth hops."""
        if name not in self.nodes:
            return []
        seen = {name: 0}
        via: dict[str, Edge] = {}
        queue = deque([name])
        while queue:
            cur = queue.popleft()
            if seen[cur] >= max_depth:
                continue
            for e in self.neighbors(cur):
                nxt = e.target if e.source == cur else e.source
                if nxt not in seen:
                    seen[nxt] = seen[cur] + 1
                    via[nxt] = e
                    queue.append(nxt)
        return [
            {
                "name": n,
                "type": self.nodes.get(n, "unknown"),
                "distance": d,
                "via": f"{via[n].source} -{via[n].relation}-> {via[n].target}",
            }
            for n, d in sorted(seen.items(), key=lambda kv: (kv[1], kv[0]))
            if n != name
        ]

    def to_dict(self) -> dict:
        return {
            "nodes": [{"id": n, "type": t} for n, t in self.nodes.items()],
            "edges": [
                {"source": e.source, "target": e.target, "relation": e.relation, "page": e.page}
                for e in self.edges
            ],
        }


def build_graph(model: StructuredModel) -> ArchitectureGraph:
    g = ArchitectureGraph()
    for c in model.components:
        g.add_node(c.name, "component")
    for i in model.interfaces:
        g.add_node(i.name, "interface")
        g.add_node(i.provider, "component")
        g.add_node(i.consumer, "component")
        g.add_edge(i.provider, i.name, "PROVIDES_INTERFACE", i.page)
        g.add_edge(i.consumer, i.name, "REQUIRES_INTERFACE", i.page)
        for s in i.signals:
            g.add_node(s, "signal")
            g.add_edge(i.name, s, "CARRIES_SIGNAL", i.page)
    for p in model.ports:
        g.add_node(p.name, "port")
        g.add_edge(p.component, p.name, "HAS_PORT", p.page)
        if p.interface:
            g.add_edge(p.name, p.interface, "TYPED_BY", p.page)
    for s in model.signals:
        g.add_node(s.name, "signal")
        g.add_edge(s.source, s.name, "SENDS_SIGNAL", s.page)
        g.add_edge(s.name, s.destination, "RECEIVED_BY", s.page)
    for d in model.dependencies:
        g.add_edge(d.source, d.target, d.relationship, d.page)
    return g
