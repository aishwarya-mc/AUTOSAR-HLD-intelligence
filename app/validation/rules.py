from __future__ import annotations

import hashlib
import re

from app.core.schemas import FindingSeverity, SourceEvidence, ValidationFinding
from app.extraction.structured_model import StructuredModel

VALID_RELATIONSHIPS = {"PROVIDES_INTERFACE", "REQUIRES_INTERFACE"}
SIGNAL_NAME = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:Status|Speed|Position|Command)\b")
INTERFACE_NAME = re.compile(r"\bI[A-Z][A-Za-z0-9]+\b")
PORT_NAME = re.compile(r"\b[A-Za-z][A-Za-z0-9]*_(?:In|Out)\b")


class ValidationEngine:
    """
    Deterministic architecture consistency rules over the structured HLD model.

    Every finding carries a rule id, severity and page-level evidence so a reviewer can
    accept/reject it. Rules never auto-fix anything.
    """

    def __init__(self, model: StructuredModel, chunks: list[dict],
                 document_id: str, version: str):
        self.m = model
        self.chunks = chunks
        self.document_id = document_id
        self.version = version
        self.findings: list[ValidationFinding] = []

    # -- helpers -----------------------------------------------------------

    def _evidence(self, page: int | None, section: str, excerpt: str) -> list[SourceEvidence]:
        return [SourceEvidence(
            document_id=self.document_id, document_version=self.version,
            page_number=page, section=section, excerpt=excerpt,
        )]

    def _add(self, rule_id: str, title: str, description: str, severity: FindingSeverity,
             subject: str, page: int | None, section: str, excerpt: str,
             confidence: float = 0.95) -> None:
        digest = hashlib.sha256(f"{rule_id}|{subject}|{self.document_id}".encode()).hexdigest()[:12]
        self.findings.append(ValidationFinding(
            finding_id=f"F-{rule_id}-{digest}", rule_id=rule_id, title=title,
            description=description, severity=severity, confidence=confidence,
            evidence=self._evidence(page, section, excerpt),
        ))

    # -- rules -------------------------------------------------------------

    def run(self) -> list[ValidationFinding]:
        self.findings = []
        for rule in (
            self._undeclared_endpoints, self._port_interfaces, self._port_direction,
            self._missing_ports, self._dependency_consistency, self._signal_consistency,
            self._signal_definitions, self._port_naming, self._unused_components,
            self._flow_references,
        ):
            rule()
        order = {FindingSeverity.critical: 0, FindingSeverity.warning: 1, FindingSeverity.info: 2}
        self.findings.sort(key=lambda f: (order[f.severity], f.rule_id, f.finding_id))
        return self.findings

    def _components(self) -> set[str]:
        return {c.name for c in self.m.components}

    def _interfaces(self) -> dict[str, object]:
        return {i.name: i for i in self.m.interfaces}

    def _undeclared_endpoints(self) -> None:  # V001
        comps = self._components()
        for i in self.m.interfaces:
            for role, comp in (("provider", i.provider), ("consumer", i.consumer)):
                if comp not in comps:
                    self._add("V001", f"Undeclared {role} component '{comp}'",
                              f"Interface {i.name} lists {comp} as {role}, but {comp} is not in the "
                              "Software Components table.", FindingSeverity.critical,
                              f"{i.name}|{comp}", i.page, "4. Interfaces",
                              f"{i.name} | {i.provider} | {i.consumer}")
        for p in self.m.ports:
            if p.component not in comps:
                self._add("V001", f"Port '{p.name}' belongs to undeclared component '{p.component}'",
                          f"{p.component} is not in the Software Components table.",
                          FindingSeverity.critical, f"port|{p.name}|{p.component}", p.page,
                          "5. Ports", f"{p.component} | {p.name} | {p.direction} | {p.interface}")

    def _port_interfaces(self) -> None:  # V002
        ifaces = self._interfaces()
        for p in self.m.ports:
            if p.interface and p.interface not in ifaces:
                self._add("V002", f"Port '{p.name}' references undefined interface '{p.interface}'",
                          "Provider and consumer ports shall reference interfaces defined in the "
                          "Interfaces table.", FindingSeverity.critical,
                          f"{p.name}|{p.interface}", p.page, "5. Ports",
                          f"{p.component} | {p.name} | {p.direction} | {p.interface}")

    def _port_direction(self) -> None:  # V003
        ifaces = self._interfaces()
        for p in self.m.ports:
            i = ifaces.get(p.interface)
            if not i:
                continue
            if p.component == i.provider and p.direction != "P-PORT":
                self._add("V003", f"Provider '{p.component}' uses {p.direction} for {i.name}",
                          f"{p.component} provides {i.name} so port {p.name} must be a P-PORT.",
                          FindingSeverity.critical, f"{p.name}|dir", p.page, "5. Ports",
                          f"{p.component} | {p.name} | {p.direction} | {p.interface}")
            elif p.component == i.consumer and p.direction != "R-PORT":
                self._add("V003", f"Consumer '{p.component}' uses {p.direction} for {i.name}",
                          f"{p.component} consumes {i.name} so port {p.name} must be an R-PORT.",
                          FindingSeverity.critical, f"{p.name}|dir", p.page, "5. Ports",
                          f"{p.component} | {p.name} | {p.direction} | {p.interface}")

    def _missing_ports(self) -> None:  # V004
        for i in self.m.interfaces:
            if not any(p.component == i.provider and p.interface == i.name and p.direction == "P-PORT"
                       for p in self.m.ports):
                self._add("V004", f"No P-PORT for {i.name} on provider {i.provider}",
                          f"{i.provider} is the provider of {i.name} but declares no P-PORT for it.",
                          FindingSeverity.warning, f"{i.name}|prov-port", i.page, "5. Ports",
                          f"{i.name} provider {i.provider}")
            if not any(p.component == i.consumer and p.interface == i.name and p.direction == "R-PORT"
                       for p in self.m.ports):
                self._add("V004", f"No R-PORT for {i.name} on consumer {i.consumer}",
                          f"{i.consumer} consumes {i.name} but declares no R-PORT for it.",
                          FindingSeverity.warning, f"{i.name}|cons-port", i.page, "5. Ports",
                          f"{i.name} consumer {i.consumer}")

    def _dependency_consistency(self) -> None:  # V005 / V006
        ifaces = self._interfaces()
        declared = {(d.source, d.relationship, d.target) for d in self.m.dependencies}
        for d in self.m.dependencies:
            if d.relationship not in VALID_RELATIONSHIPS:
                self._add("V006", f"Unknown relationship '{d.relationship}'",
                          "Dependencies must be PROVIDES_INTERFACE or REQUIRES_INTERFACE.",
                          FindingSeverity.warning, f"{d.source}|{d.relationship}|{d.target}",
                          d.page, "7. Dependencies",
                          f"{d.source} | {d.relationship} | {d.target} | {d.reason}")
            if d.target not in ifaces and d.relationship in VALID_RELATIONSHIPS:
                self._add("V006", f"Dependency targets undefined interface '{d.target}'",
                          f"{d.source} {d.relationship} {d.target}, but {d.target} is not defined.",
                          FindingSeverity.critical, f"dep|{d.source}|{d.target}", d.page,
                          "7. Dependencies",
                          f"{d.source} | {d.relationship} | {d.target} | {d.reason}")
        for i in self.m.interfaces:
            for rel, comp in (("PROVIDES_INTERFACE", i.provider), ("REQUIRES_INTERFACE", i.consumer)):
                if (comp, rel, i.name) not in declared:
                    self._add("V005", f"Missing dependency: {comp} {rel} {i.name}",
                              "The Interfaces table implies this dependency but section 7 does "
                              "not trace it (violates 'dependencies must be traceable').",
                              FindingSeverity.warning, f"{comp}|{rel}|{i.name}", i.page,
                              "7. Dependencies", f"{i.name} | {i.provider} | {i.consumer}")
        for d in self.m.dependencies:
            i = ifaces.get(d.target)
            if not i:
                continue
            expected = i.provider if d.relationship == "PROVIDES_INTERFACE" else i.consumer
            if d.relationship in VALID_RELATIONSHIPS and d.source != expected:
                self._add("V005", f"Dependency contradicts interface table for {i.name}",
                          f"{d.source} {d.relationship} {i.name}, but the Interfaces table lists "
                          f"{expected}.", FindingSeverity.critical, f"contra|{d.source}|{d.target}",
                          d.page, "7. Dependencies",
                          f"{d.source} | {d.relationship} | {d.target}")

    def _signal_consistency(self) -> None:  # V007
        sigs = {s.name: s for s in self.m.signals}
        for i in self.m.interfaces:
            for name in i.signals:
                s = sigs.get(name)
                if s and (s.source != i.provider or s.destination != i.consumer):
                    self._add("V007", f"Signal '{name}' endpoints differ from interface {i.name}",
                              f"Signals table: {s.source} -> {s.destination}; Interfaces table: "
                              f"{i.provider} -> {i.consumer}.", FindingSeverity.critical,
                              f"{name}|endpoints", s.page, "6. Signals",
                              f"{s.name} | {s.data_type} | {s.source} | {s.destination}")

    def _signal_definitions(self) -> None:  # V008
        defined = {s.name for s in self.m.signals}
        used = {n for i in self.m.interfaces for n in i.signals}
        for name in sorted(used - defined):
            self._add("V008", f"Signal '{name}' used by an interface but not defined",
                      "Every interface signal needs an entry (data type, source, destination) in "
                      "the Signals table.", FindingSeverity.warning, f"undef|{name}", None,
                      "6. Signals", name)
        for s in self.m.signals:
            if s.name not in used:
                self._add("V008", f"Signal '{s.name}' is not carried by any interface",
                          "The signal is defined but no interface carries it.",
                          FindingSeverity.warning, f"orphan|{s.name}", s.page, "6. Signals",
                          f"{s.name} | {s.data_type} | {s.source} | {s.destination}")
            if not s.data_type:
                self._add("V008", f"Signal '{s.name}' has no data type", "Data type is empty.",
                          FindingSeverity.warning, f"notype|{s.name}", s.page, "6. Signals", s.name)

    def _port_naming(self) -> None:  # V009
        for p in self.m.ports:
            expected = "_Out" if p.direction == "P-PORT" else "_In" if p.direction == "R-PORT" else None
            if expected and not p.name.endswith(expected):
                self._add("V009", f"Port '{p.name}' name does not match direction {p.direction}",
                          f"By convention a {p.direction} name ends with {expected}.",
                          FindingSeverity.info, f"naming|{p.name}", p.page, "5. Ports",
                          f"{p.component} | {p.name} | {p.direction}", confidence=0.8)

    def _unused_components(self) -> None:  # V010
        used = {i.provider for i in self.m.interfaces} | {i.consumer for i in self.m.interfaces}
        for c in self.m.components:
            if c.name not in used:
                self._add("V010", f"Component '{c.name}' participates in no interface",
                          "The component is declared but neither provides nor consumes any interface.",
                          FindingSeverity.info, f"unused|{c.name}", c.page, "3. Software Components",
                          f"{c.name} | {c.role}", confidence=0.85)

    def _flow_references(self) -> None:  # V011
        flow_chunks = [c for c in self.chunks if c.get("section", "").startswith("8.")]
        text = " ".join(c["text"] for c in flow_chunks)
        if not text:
            return
        page = flow_chunks[0]["page_number"]
        sigs = {s.name for s in self.m.signals}
        ifaces = set(self._interfaces())
        ports = {p.name for p in self.m.ports}
        for pattern, known, kind in ((SIGNAL_NAME, sigs | ifaces, "signal"),
                                     (INTERFACE_NAME, ifaces, "interface"),
                                     (PORT_NAME, ports, "port")):
            for name in sorted(set(pattern.findall(text)) - known):
                if kind == "signal" and INTERFACE_NAME.fullmatch(name):
                    continue
                self._add("V011", f"Functional flow references undefined {kind} '{name}'",
                          f"'{name}' appears in section 8 but is not defined in the {kind} tables "
                          "(signal/interface names must stay consistent with the flows).",
                          FindingSeverity.warning, f"flow|{kind}|{name}", page, "8. Functional Flows",
                          name, confidence=0.85)
