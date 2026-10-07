from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.config import PROJECT_ROOT, get_settings
from app.core.logging import get_logger
from app.rag.hybrid import FEATURE_NAMES

logger = get_logger(__name__)

DEFAULT_MODEL_DIR = PROJECT_ROOT / "models" / "answerability" / "current"


class AnswerabilityModel:
    """Trained classifier that decides whether a question can be answered from a document.

    It replaces hand-set similarity thresholds with a model fitted on labelled questions from
    several documents (see app/evaluation/train_answerability.py). Metadata (version, training
    documents, metrics, decision threshold) is stored next to the artifact for traceability.
    """

    def __init__(self, estimator, metadata: dict):
        self.estimator = estimator
        self.metadata = metadata
        self.feature_names: list[str] = metadata["feature_names"]
        self.threshold: float = float(metadata["threshold"])
        self.version: str = metadata["version"]

    def predict_proba(self, features: dict[str, float]) -> float:
        row = [[float(features.get(name, 0.0)) for name in self.feature_names]]
        return float(self.estimator.predict_proba(row)[0][1])

    def is_answerable(self, features: dict[str, float]) -> tuple[bool, float]:
        p = self.predict_proba(features)
        return p >= self.threshold, p


@lru_cache
def load_answerability_model() -> AnswerabilityModel | None:
    """Load the versioned model if present; callers fall back to the hand-set gate otherwise."""
    override = get_settings().answerability_model_dir
    directory = Path(override) if override else DEFAULT_MODEL_DIR
    meta_path, model_path = directory / "metadata.json", directory / "model.joblib"
    if not (meta_path.exists() and model_path.exists()):
        return None
    try:
        import joblib

        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        if metadata["feature_names"] != FEATURE_NAMES:
            logger.warning("Answerability model features do not match the code; ignoring it.")
            return None
        return AnswerabilityModel(joblib.load(model_path), metadata)
    except Exception as exc:
        logger.warning("Could not load answerability model: %s", exc)
        return None
