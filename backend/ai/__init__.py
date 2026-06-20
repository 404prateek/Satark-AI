"""ai package — ML pipeline for Satark AI phishing classifier."""

from backend.ai.model_loader import get_model, reload_model
from backend.ai.shap_explainer import SHAPExplainer
from backend.ai.language_detector import detect_language

__all__ = ["get_model", "reload_model", "SHAPExplainer", "detect_language"]
