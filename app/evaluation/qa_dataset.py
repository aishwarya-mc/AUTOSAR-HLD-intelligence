"""Labelled question dataset for the answerability classifier and retrieval experiments.

Questions are generated from each document's own tables, so gold answers and gold sections are
known without manual labelling. Three kinds of unanswerable questions are generated:

  offtopic         unrelated to engineering documents
  absent_attribute names a real entity but asks for a fact the HLD never states (hard cases)
  fake_entity      names a plausible entity that does not exist in the document

Split: `dev` documents are used for training and cross-validation; `test` documents are never
touched until the final evaluation. The hand-written question set for the sample HLD
(data/evaluation/qa_set.json) is kept as a separate, independent test set.
"""
from __future__ import annotations

import random
import re

import pandas as pd

from app.core.config import PROJECT_ROOT
from app.rag.answerer import find_entities
from app.services.pipeline import HLDService

SYNTH = PROJECT_ROOT / "data" / "synthetic"
SAMPLE = PROJECT_ROOT / "data" / "sample"

DEV_DOCS = {k: SYNTH / f"{k}.pdf" for k in
            ["powertrain", "adas", "infotainment", "battery", "lighting", "thermal"]}
TEST_DOCS = {
    "steering": SYNTH / "steering.pdf", "keyless": SYNTH / "keyless.pdf", "wiper": SYNTH / "wiper.pdf",
    "bcs_sample": SAMPLE / "sample_hld.pdf", "bcs_sample_v2": SAMPLE / "sample_hld_v2.pdf",
}

OFFTOPIC = [
    "What is the weather today?", "How do I bake sourdough bread?", "Who won the football match last night?",
    "What is the capital of Australia?", "Recommend a good science fiction novel.",
    "How many calories are in an apple?", "What time does the pharmacy open?",
    "Explain how photosynthesis works.", "What is the best way to learn guitar?",
    "How do I change a bicycle tire?", "Translate good morning into French.",
    "What is the population of Canada?", "Tell me a joke about cats.", "How far away is the moon?",
    "What is the stock price of a technology company?", "How do I reset my email password?",
    "Which movie won the best picture award?", "What is the boiling point of water?",
    "Give me a recipe for vegetable soup.", "How many players are on a basketball team?",
    "What is the tallest mountain in the world?", "Who painted the Mona Lisa?",
    "How do vaccines work?", "What is the speed of light?", "Suggest a name for my puppy.",
    "How long does it take to fly to Tokyo?", "What is machine learning?", "Explain the rules of chess.",
    "What is the exchange rate for euros?", "How do I plant tomatoes?",
]
ABSENT_ATTRIBUTE = [
    "What is the CAN baud rate of {comp}?", "What is the memory footprint of {comp}?",
    "Who approved the design of {comp}?", "What is the ASIL rating of {iface}?",
    "What is the maximum latency of {sig}?", "What is the cycle time of {comp}?",
    "Which supplier developed {comp}?", "What is the test coverage of {comp}?",
    "What is the operating voltage of {comp}?", "What is the safety goal for {sig}?",
    "What is the end-of-line calibration value of {sig}?", "How many lines of code does {comp} contain?",
]
FAKE_NAMES = ["HeatedSeat", "SunroofPosition", "TirePressure", "ParkingBrake", "WindshieldHeater",
              "NavigationRoute", "SeatMemory", "FuelLevel", "MirrorFold", "TrunkRelease", "CruiseSetpoint",
              "OdometerCount", "HornActuation", "ChildLock", "WheelSlip", "SuspensionHeight"]
FAKE_TEMPLATES = [
    "Which component provides I{fake}?", "What signal does I{fake} carry?",
    "Which component requires I{fake}?", "What ports does {fake}Control have?",
    "What is the data type of {fake}?", "Describe the {fake_words} flow.",
    "What is the role of {fake}Manager?", "Which interface does the {fake}_Out port use?",
]


def spaced(camel: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", camel)


def _answerable(model, flows, rng, n: int) -> list[dict]:
    items = []
    for i in model.interfaces:
        base = i.name[1:]
        sig = i.signals[0] if i.signals else base
        items += [
            ("provider_of", f"Which component provides {i.name}?", [i.provider], {"4. Interfaces", "7. Dependencies"}),
            ("consumer_of", f"Which component requires {i.name}?", [i.consumer], {"4. Interfaces", "7. Dependencies"}),
            ("consumer_para", f"Who consumes {i.name}?", [i.consumer], {"4. Interfaces", "7. Dependencies"}),
            ("provider_para", f"Which element supplies {spaced(sig).lower()} information?",
             [i.provider], {"4. Interfaces", "7. Dependencies", "6. Signals", "8. Functional Flows"}),
            ("iface_signal", f"What signal does {i.name} carry?", [sig], {"4. Interfaces", "6. Signals"}),
            ("port_iface", f"Which interface does the {base}_In port use?", [i.name], {"5. Ports"}),
        ]
    for s in model.signals:
        items += [
            ("signal_type", f"What is the data type of {s.name}?", [s.data_type], {"6. Signals"}),
            ("signal_src", f"Where does {s.name} originate?", [s.source], {"6. Signals", "4. Interfaces"}),
            ("signal_dst", f"Which component receives {s.name}?", [s.destination], {"6. Signals", "4. Interfaces"}),
        ]
    for c in model.components:
        ports = [p.name for p in model.ports if p.component == c.name]
        items += [
            ("ports_of", f"What ports does {c.name} have?", ports[:2], {"5. Ports"}),
            ("comp_role", f"What is the role of {c.name}?", [c.role], {"3. Software Components"}),
            ("comp_does", f"What does {spaced(c.name).lower()} do?", [],
             {"3. Software Components", "2. Software Architecture"}),
        ]
    for _fid, title in flows:
        items.append(("flow", f"Describe the {title} flow.", [], {"8. Functional Flows"}))
    rng.shuffle(items)
    return [{"category": c, "question": q, "terms": t, "gold_sections": sorted(g), "answerable": 1}
            for c, q, t, g in items[:n]]


def _unanswerable(model, doc_text: str, rng, n_off: int, n_abs: int, n_fake: int) -> list[dict]:
    out = [{"category": "offtopic", "question": q, "terms": [], "gold_sections": [], "answerable": 0}
           for q in rng.sample(OFFTOPIC, n_off)]
    comps, ifaces, sigs = ([c.name for c in model.components], [i.name for i in model.interfaces],
                           [s.name for s in model.signals])
    for t in rng.sample(ABSENT_ATTRIBUTE, n_abs):
        out.append({"category": "absent_attribute",
                    "question": t.format(comp=rng.choice(comps), iface=rng.choice(ifaces), sig=rng.choice(sigs)),
                    "terms": [], "gold_sections": [], "answerable": 0})
    pool = [f for f in FAKE_NAMES if f.lower() not in doc_text.lower()]
    for _ in range(n_fake):
        fake = rng.choice(pool)
        out.append({"category": "fake_entity",
                    "question": rng.choice(FAKE_TEMPLATES).format(fake=fake, fake_words=spaced(fake).lower()),
                    "terms": [], "gold_sections": [], "answerable": 0})
    return out


def build_items(service: HLDService, doc_id: str, seed: int, n_ans=24, n_off=10, n_abs=7, n_fake=7) -> list[dict]:
    rng = random.Random(seed)
    model = service.model(doc_id)
    flows = [(e["attributes"].get("flow_id", ""), e["attributes"].get("flow_name", ""))
             for e in service.entities(doc_id, "functional_flow")]
    doc_text = " ".join(c["text"] for c in service.chunks(doc_id))
    return _answerable(model, flows, rng, n_ans) + _unanswerable(model, doc_text, rng, n_off, n_abs, n_fake)


def build_dataset(service: HLDService | None = None, seed: int = 7) -> pd.DataFrame:
    """Process every document, generate its questions and compute retrieval features."""
    service = service or HLDService()
    rows = []
    for split, docs in (("dev", DEV_DOCS), ("test", TEST_DOCS)):
        for n, (name, path) in enumerate(docs.items()):
            doc_id = service.process(path)["document_id"]
            answerer = service.answerer(doc_id)
            retriever = answerer.retriever
            for item in build_items(service, doc_id, seed + n + (100 if split == "test" else 0)):
                chunks, feats = retriever.retrieve_with_features(item["question"])
                if feats is None:
                    raise RuntimeError("Embeddings are required to build the dataset (EMBEDDINGS_ENABLED=true).")
                feats["entity_match"] = float(len(find_entities(item["question"], answerer.graph)))
                rows.append({"doc": name, "split": split, **item, **feats,
                             "top_sections": [c.section for c in chunks]})
    df = pd.DataFrame(rows)
    return df


def to_records(df: pd.DataFrame) -> list[dict]:
    return [asdict_row for asdict_row in df.to_dict(orient="records")]
