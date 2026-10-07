from app.extraction.structured_model import (
    ComponentDef,
    InterfaceDef,
    PortDef,
    SignalDef,
    StructuredModel,
    _ident,
)
from app.graph.builder import build_graph
from app.rag.retriever import BM25Retriever, tokenize
from app.validation.rules import ValidationEngine


def good_model() -> StructuredModel:
    return StructuredModel(
        components=[ComponentDef("A", "Provider", "", 1), ComponentDef("B", "Consumer", "", 1)],
        interfaces=[InterfaceDef("IX", "A", "B", ["SigStatus"], 1)],
        ports=[PortDef("A", "X_Out", "P-PORT", "IX", 1), PortDef("B", "X_In", "R-PORT", "IX", 1)],
        signals=[SignalDef("SigStatus", "boolean", "A", "B", 1)],
    )


def rules(model):
    return {f.rule_id for f in ValidationEngine(model, [], "d", "v1").run()}


def test_identifier_rejoin():
    assert _ident("DoorStatus Out\n_") == "DoorStatus_Out"
    assert _ident("WindowCommand_In") == "WindowCommand_In"


def test_undeclared_component_flagged():
    m = good_model()
    m.components.pop()
    assert "V001" in rules(m)


def test_undefined_interface_on_port():
    m = good_model()
    m.ports[0].interface = "IMissing"
    assert "V002" in rules(m)


def test_signal_endpoint_mismatch():
    m = good_model()
    m.signals[0].destination = "A"
    assert "V007" in rules(m)


def test_graph_impact_depth():
    g = build_graph(good_model())
    names = [i["name"] for i in g.impact("A", max_depth=1)]
    assert "IX" in names and "B" not in names
    assert "B" in [i["name"] for i in g.impact("A", max_depth=2)]


def test_tokenizer_splits_camel_case():
    assert {"door", "control", "doorcontrol"} <= set(tokenize("DoorControl"))


def test_bm25_prefers_matching_chunk():
    chunks = [
        {"chunk_id": "1", "text": "DoorControl publishes door state", "page_number": 1, "section": "a"},
        {"chunk_id": "2", "text": "Window position is uint8", "page_number": 2, "section": "b"},
    ]
    assert BM25Retriever(chunks).search("door state")[0].chunk_id == "1"
