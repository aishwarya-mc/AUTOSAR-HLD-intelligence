from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ingestion.pdf_parser import ParsedDocument


@dataclass
class InterfaceDef:
    name: str
    provider: str
    consumer: str
    signals: list[str]
    page: int


@dataclass
class PortDef:
    component: str
    name: str
    direction: str
    interface: str
    page: int


@dataclass
class SignalDef:
    name: str
    data_type: str
    source: str
    destination: str
    page: int


@dataclass
class DependencyDef:
    source: str
    relationship: str
    target: str
    reason: str
    page: int


@dataclass
class ComponentDef:
    name: str
    role: str
    responsibility: str
    page: int


@dataclass
class StructuredModel:
    """Typed view of the HLD's tables, used by graph, validation and diff."""

    components: list[ComponentDef] = field(default_factory=list)
    interfaces: list[InterfaceDef] = field(default_factory=list)
    ports: list[PortDef] = field(default_factory=list)
    signals: list[SignalDef] = field(default_factory=list)
    dependencies: list[DependencyDef] = field(default_factory=list)


def _clean(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    # PyMuPDF renders "_" wrapped onto its own line for long identifiers.
    return re.sub(r"\s+_+$", "", value).strip()


def _ident(value: str) -> str:
    """Rejoin identifiers split by table cell wrapping: 'DoorStatus Out _'."""
    value = _clean(value)
    return re.sub(r"\s*_\s*", "_", re.sub(r"(\w) (In|Out)$", r"\1_\2", value))


def _headers(row: list[str]) -> list[str]:
    return [re.sub(r"[^a-z]", "", str(h).lower()) for h in row]


def build_structured_model(document: ParsedDocument) -> StructuredModel:
    model = StructuredModel()

    for page in document.pages:
        for table in page.tables:
            if len(table) < 2:
                continue
            headers = _headers(table[0])
            idx = {h: i for i, h in enumerate(headers)}
            rows = [r for r in table[1:] if len(r) >= len(headers)]

            if {"component", "role"} <= set(headers):
                for r in rows:
                    model.components.append(ComponentDef(
                        _clean(r[idx["component"]]), _clean(r[idx["role"]]),
                        _clean(r[idx.get("primaryresponsibility", idx["role"])]), page.page_number))
            elif {"interface", "provider", "consumer"} <= set(headers):
                for r in rows:
                    sigs = [s.strip() for s in re.split(r"[,;]", _clean(r[idx["signals"]])) if s.strip()] if "signals" in idx else []
                    model.interfaces.append(InterfaceDef(
                        _clean(r[idx["interface"]]), _clean(r[idx["provider"]]),
                        _clean(r[idx["consumer"]]), sigs, page.page_number))
            elif {"component", "port", "direction"} <= set(headers):
                for r in rows:
                    model.ports.append(PortDef(
                        _clean(r[idx["component"]]), _ident(r[idx["port"]]),
                        _clean(r[idx["direction"]]).upper(),
                        _clean(r[idx["interface"]]) if "interface" in idx else "", page.page_number))
            elif {"signal", "datatype", "source", "destination"} <= set(headers):
                for r in rows:
                    model.signals.append(SignalDef(
                        _clean(r[idx["signal"]]), _clean(r[idx["datatype"]]),
                        _clean(r[idx["source"]]), _clean(r[idx["destination"]]), page.page_number))
            elif {"source", "relationship", "target"} <= set(headers):
                for r in rows:
                    rel = re.sub(r"\s+", "_", _clean(r[idx["relationship"]]).replace("_", " ")).upper()
                    model.dependencies.append(DependencyDef(
                        _clean(r[idx["source"]]), rel, _clean(r[idx["target"]]),
                        _clean(r[idx["reason"]]) if "reason" in idx else "", page.page_number))
    return model


def model_from_dict(data: dict) -> StructuredModel:
    return StructuredModel(
        components=[ComponentDef(**x) for x in data.get("components", [])],
        interfaces=[InterfaceDef(**x) for x in data.get("interfaces", [])],
        ports=[PortDef(**x) for x in data.get("ports", [])],
        signals=[SignalDef(**x) for x in data.get("signals", [])],
        dependencies=[DependencyDef(**x) for x in data.get("dependencies", [])],
    )
