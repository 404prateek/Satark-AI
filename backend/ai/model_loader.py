"""
Singleton model loader for Satark AI's phishing classifier.

The Pipeline (TF-IDF + MultinomialNB) is large (~30 MB) and takes a
noticeable time to deserialise from disk.  Loading it once at startup
into a module-level variable means every subsequent request gets the
in-memory object instantly.

Security note: we use `pickle` (via joblib) only for our own model file
whose path is fixed at deployment time. Never unpickle user-supplied bytes.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import joblib
from sklearn.pipeline import Pipeline

logger = logging.getLogger(__name__)

# ── Path resolution ───────────────────────────────────────────────────────────
# By default the model lives at  <repo-root>/data/model.pkl
# Override with the MODEL_PATH environment variable in production.

_DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "data" / "model.pkl"
MODEL_PATH = Path(os.getenv("MODEL_PATH", str(_DEFAULT_MODEL_PATH)))

# ── Singleton state ───────────────────────────────────────────────────────────
_pipeline: Optional[Pipeline] = None


def get_model() -> Pipeline:
    """
    Returns the loaded sklearn Pipeline, loading it from disk on first call.

    Raises:
        FileNotFoundError: If model.pkl does not exist at MODEL_PATH.
        RuntimeError:      If the file exists but cannot be deserialised.
    """
    global _pipeline

    if _pipeline is not None:
        return _pipeline

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model file not found at '{MODEL_PATH}'. "
            "Run `python -m backend.ai.model_trainer` to train and save the model."
        )

    logger.info(f"Loading phishing classifier from: {MODEL_PATH}")
    try:
        import __main__
        import backend.ai.model_trainer
        __main__.preprocess_for_tokens = backend.ai.model_trainer.preprocess_for_tokens
        
        _pipeline = joblib.load(MODEL_PATH)
    except Exception as exc:
        raise RuntimeError(f"Failed to load model from '{MODEL_PATH}': {exc}") from exc

    logger.info("Phishing classifier loaded successfully.")
    return _pipeline


def reload_model() -> Pipeline:
    """Forces a reload from disk — useful after model retraining without restart."""
    global _pipeline
    _pipeline = None
    return get_model()
