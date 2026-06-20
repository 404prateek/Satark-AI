"""
SHAP explainability for the TF-IDF + MultinomialNB phishing classifier.

Why LinearExplainer with a sparse-compatible approach?
  - MultinomialNB is a linear model in log-probability space.
  - SHAP's LinearExplainer supports the sparse CSR matrices that
    TfidfVectorizer produces, making it the correct (and fast) choice.
  - KernelExplainer works but is O(N²) in features and therefore too
    slow for 10 000 TF-IDF features at inference time.

Interpretation of SHAP values:
  - Positive value → feature pushes the prediction toward PHISHING (class 1).
  - Negative value → feature pushes the prediction toward SAFE (class 0).
"""

import logging
from typing import Dict, Optional

import numpy as np
import shap
from sklearn.pipeline import Pipeline

import re

logger = logging.getLogger(__name__)

FEATURE_LABEL_MAP = {
    "DOT_xyz": "Suspicious .xyz domain",
    "dot_xyz": "Suspicious .xyz domain",
    "DOT_tk": "Suspicious .tk domain",
    "dot_tk": "Suspicious .tk domain",
    "DOT_ml": "Suspicious .ml domain",
    "dot_ml": "Suspicious .ml domain",
    "DOT_ga": "Suspicious .ga domain",
    "dot_ga": "Suspicious .ga domain",
    "url_token": "Contains a link",
    "phone_token": "Contains a phone number",
    "RUPEE_": "Mentions money/currency",
    "AMOUNT_LARGE": "Large cash amount mentioned",
    "AMOUNT_MEDIUM": "Cash amount mentioned",
    "PHONE_NUMBER": "Phone number included",
    "NUMBER_TOKEN": "Unusual number sequence",
}


class SHAPExplainer:
    """
    Wraps a scikit-learn Pipeline (TfidfVectorizer → MultinomialNB) with
    a SHAP LinearExplainer to produce human-readable feature attributions.
    """

    def __init__(self, pipeline: Pipeline):
        """
        Initialises the explainer.  Background data is not needed for
        LinearExplainer — it computes exact Shapley values analytically.

        Args:
            pipeline: A fitted sklearn Pipeline whose first step is a
                      TfidfVectorizer and second step is a MultinomialNB.
        """
        self._pipeline = pipeline
        self._vectorizer = pipeline.named_steps.get("tfidf") or pipeline.steps[0][1]
        self._classifier = pipeline.named_steps.get("nb") or pipeline.steps[-1][1]
        self._feature_names: list[str] = self._vectorizer.get_feature_names_out().tolist()

        # LinearExplainer expects the underlying linear model.
        # For MultinomialNB the decision boundary is linear in log-prob space.
        delta_log_prob = self._classifier.feature_log_prob_[1] - self._classifier.feature_log_prob_[0]
        intercept = self._classifier.class_log_prior_[1] - self._classifier.class_log_prior_[0]

        self._explainer = shap.LinearExplainer(
            (delta_log_prob, intercept),
            masker=shap.maskers.Independent(
                # Use a tiny zero-background: LinearExplainer with sparse data
                # works best with a single all-zero reference point.
                np.zeros((1, len(self._feature_names)))
            ),
        )
        logger.info(
            f"SHAPExplainer ready. Vocabulary size: {len(self._feature_names)}"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def explain(self, text: str, top_n: int = 10) -> Dict[str, float]:
        """
        Computes SHAP feature attributions for a single text input.

        Args:
            text:  Raw message/URL string.
            top_n: Number of top features to return (by absolute SHAP value).

        Returns:
            Dict mapping feature name → SHAP value, sorted by absolute impact
            (descending).  Positive values increase phishing probability;
            negative values decrease it.

        Edge cases handled:
          - Empty text → returns {}.
          - All-zero SHAP values (no discriminative features) → returns {}.
          - top_n > number of non-zero features → returns all non-zero ones.
        """
        if not text or not text.strip():
            logger.debug("explain() called with empty text — returning {}")
            return {}

        # 1. Transform text into sparse TF-IDF vector (shape: 1 × vocab_size)
        x_sparse = self._vectorizer.transform([text])  # scipy CSR matrix

        # 2. Convert to dense for LinearExplainer (1 × vocab_size ndarray)
        x_dense = x_sparse.toarray()

        # 3. Compute SHAP values
        # shap_values shape for binary classifier: (1, vocab_size) for class 1
        shap_values = self._explainer.shap_values(x_dense)

        # For binary classifiers shap returns a list [class0_vals, class1_vals]
        # or a single 2D array; normalise to always get class-1 (phishing) values.
        if isinstance(shap_values, list):
            values_1d: np.ndarray = shap_values[1][0]   # shape: (vocab_size,)
        else:
            # Some SHAP versions return shape (1, vocab_size, 2) or (1, vocab_size)
            if shap_values.ndim == 3:
                values_1d = shap_values[0, :, 1]
            else:
                values_1d = shap_values[0]

        # 4. Guard: all-zero SHAP → no informative features
        if not np.any(values_1d):
            logger.debug("All SHAP values are zero — no discriminative features found")
            return {}

        # 5. Restrict to features actually present in this text (non-zero TF-IDF)
        nonzero_indices = x_sparse.nonzero()[1]
        if len(nonzero_indices) == 0:
            return {}

        stopword_pairs = {"you", "have", "been", "are", "is", "the", "a", "an", "to", "of", "in", "on", "for", "and", "or"}

        # Build (feature_name, shap_value) pairs for present features only
        present: list[tuple[str, float]] = []
        for i in nonzero_indices:
            feat_name = self._feature_names[i]
            val = float(values_1d[i])
            
            # Filter out purely punctuation/symbols or single characters
            if len(feat_name) < 2:
                continue
            if re.match(r'^[^a-zA-Z0-9\u0900-\u097F]+$', feat_name):
                continue
                
            # Low-signal bigram filter
            words = feat_name.lower().split()
            if len(words) == 2 and words[0] in stopword_pairs and words[1] in stopword_pairs:
                continue

            # Map feature name to readable label
            mapped_label = FEATURE_LABEL_MAP.get(feat_name, feat_name.capitalize())
            present.append((mapped_label, val))

        # 6. Sort by absolute SHAP value, descending, then take top_n
        present.sort(key=lambda x: abs(x[1]), reverse=True)
        top_features = present[:top_n]

        return dict(top_features)

    # ── Convenience ──────────────────────────────────────────────────────────

    def verdict_shap(self, text: str) -> Optional[str]:
        """
        Returns the single highest-weight feature driving the prediction —
        useful for a one-line human-readable reason.
        """
        features = self.explain(text, top_n=1)
        if not features:
            return None
        name, val = next(iter(features.items()))
        direction = "phishing" if val > 0 else "safe"
        return f"'{name}' ({direction} signal, SHAP={val:+.4f})"
