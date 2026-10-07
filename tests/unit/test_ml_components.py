import json
from pathlib import Path

import pytest

from app.extraction.functional_flows import FunctionalFlowExtractor
from app.extraction.interfaces import InterfaceExtractor
from app.rag.answerability import load_answerability_model
from app.rag.hybrid import FEATURE_NAMES
from app.rag.retriever import tokenize

SYNTH = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def test_stopwords_do_not_count_as_content():
    assert tokenize("What ports does DoorControl have?") == ["ports", "doorcontrol", "door", "control"]


def test_interface_pattern_ignores_all_caps_words():
    pattern = InterfaceExtractor.INTERFACE_PATTERN
    assert pattern.findall("IVI INFOTAINMENT IDoorStatus IWindowCommand") == ["IDoorStatus", "IWindowCommand"]


@pytest.mark.parametrize("content,title", [
    ("Door State Monitoring DoorControl reads the state.", "Door State Monitoring"),
    ("Steering Angle Command Distribution LaneKeepControl publishes it.", "Steering Angle Command Distribution"),
    ("Key Challenge Distribution KeyFobControl publishes KeyChallenge.", "Key Challenge Distribution"),
])
def test_flow_title_split(content, title):
    assert FunctionalFlowExtractor._split_flow_name(content)[0] == title


def test_answerability_model_artifact_is_consistent():
    model = load_answerability_model()
    assert model is not None, "run python -m app.evaluation.train_answerability"
    assert model.feature_names == FEATURE_NAMES
    assert 0.0 < model.threshold < 1.0
    refused, p_low = model.is_answerable({"sem_top1": 0.45, "coverage": 0.0, "uncovered": 4, "n_tokens": 4})
    answered, p_high = model.is_answerable({
        "sem_top1": 0.75, "sem_top2": 0.7, "sem_mean5": 0.68, "bm25_top1": 6.0, "bm25_per_token": 1.2,
        "coverage": 1.0, "uncovered": 0, "n_tokens": 5, "agree": 1, "top_chunk_cov": 0.9, "entity_match": 1})
    assert not refused and answered and p_high > p_low


def test_training_metadata_records_provenance():
    meta = json.loads((Path(__file__).resolve().parents[2] / "models/answerability/current/metadata.json").read_text())
    assert not set(meta["training_documents"]) & set(meta["test_documents"])  # no document leakage
    assert meta["metrics_test"]["f1"] > meta["metrics_rule_baseline_test"]["f1"]
    assert meta["dataset_sha256_16"] and meta["git_sha"]


def test_synthetic_truth_files_exist():
    keys = {p.name.split(".")[0] for p in SYNTH.glob("*.truth.json")}
    assert {"powertrain", "steering", "keyless", "wiper"} <= keys
