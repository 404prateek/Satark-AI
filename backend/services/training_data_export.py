"""
Training data export utility — the feedback flywheel.

Why this matters
────────────────
Every other improvement to Satark AI depends on having a growing,
real-world-corrected dataset instead of a frozen one.

The initial model was trained on:
  • UCI SMS Spam Collection (5,574 generic English SMS messages)
  • ~75 hand-crafted Indian phishing samples

That corpus is static.  It will never see a new brand of scam, a novel
urgency phrase, or the specific OCR artefacts that EasyOCR produces from
Indian RCS screenshots — unless we feed real corrections back in.

This module bridges user feedback → retraining input:
  1. Pull all ScanFeedback rows from the DB (synchronous via psycopg2 /
     SQLAlchemy core, so it can be called from a CLI without an event loop).
  2. Derive the correct binary label from the correction type:
       "correct"        → reinforce original_verdict  →  spam if PHISHING/SUSPICIOUS, ham if SAFE
       "false_positive" → model over-triggered         →  ham  (actually safe)
       "false_negative" → model missed a scam          →  spam (actually phishing)
  3. Return a DataFrame with exactly [label, text, source, confidence]
     columns so it can be concat'd directly with the base dataset in
     model_trainer.train(), with no schema changes required.

Intended usage
──────────────
  # CLI / cron job
  from backend.services.training_data_export import export_labeled_corrections
  df = export_labeled_corrections(min_confidence=0.5)
  # → feed into model_trainer.train(include_feedback=True)
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text

from backend.config import get_settings

logger = logging.getLogger(__name__)


def _get_sync_engine():
    """
    Returns a *synchronous* SQLAlchemy engine for use in CLI / script contexts
    where there is no running asyncio event loop.

    Converts the async postgresql+asyncpg URL to the sync postgresql+psycopg2
    dialect so standard pandas / SQLAlchemy queries work without await.
    """
    settings = get_settings()
    sync_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    ).replace(
        "postgresql://", "postgresql+psycopg2://"
    )
    return create_engine(sync_url, pool_pre_ping=True)


def _derive_label(correction: str, original_verdict: str) -> str:
    """
    Maps a (correction, original_verdict) pair to a binary training label.

      correction == "correct"        → trust original_verdict
      correction == "false_positive" → model fired when it shouldn't → ham
      correction == "false_negative" → model missed a real scam       → spam
    """
    if correction == "false_positive":
        return "ham"
    if correction == "false_negative":
        return "spam"
    # "correct" — reinforce what the model said
    return "spam" if original_verdict in ("PHISHING", "SUSPICIOUS") else "ham"


def export_labeled_corrections(
    min_confidence: float = 0.0,
    db_engine=None,
) -> pd.DataFrame:
    """
    Joins scan_feedback with scans and returns a clean DataFrame ready to
    be concatenated with the base training dataset.

    Args:
        min_confidence: Filter out scan rows where the model's NLP confidence
                        was below this threshold (0.0 = include all).
        db_engine:      Optional pre-built SQLAlchemy engine (for testing).
                        If None, a new synchronous engine is created from
                        settings.DATABASE_URL.

    Returns:
        DataFrame with columns:
          label       – "spam" | "ham"
          text        – the raw input text (raw_input or ocr_text)
          source      – always "user_feedback"
          confidence  – a simple corroboration count: how many feedback rows
                        agree on this scan_id's derived label.  Scans with
                        multiple independent corroborations are more reliable
                        training signal.
    """
    engine = db_engine or _get_sync_engine()

    query = text("""
        SELECT
            sf.scan_id,
            sf.user_correction,
            sf.original_verdict,
            sf.corrected_label,
            -- Prefer raw_input (text/URL scans); fall back to ocr_text for images.
            COALESCE(s.raw_input, s.ocr_text) AS input_text,
            s.confidence AS model_confidence
        FROM scan_feedback sf
        JOIN scans s ON s.id = sf.scan_id
        WHERE COALESCE(s.raw_input, s.ocr_text) IS NOT NULL
          AND CHAR_LENGTH(COALESCE(s.raw_input, s.ocr_text)) > 10
          AND s.confidence >= :min_confidence
        ORDER BY sf.created_at ASC
    """)

    try:
        with engine.connect() as conn:
            rows = conn.execute(query, {"min_confidence": min_confidence}).fetchall()
    except Exception as exc:
        logger.error("Failed to query feedback from DB: %s", exc)
        return pd.DataFrame(columns=["label", "text", "source", "confidence"])

    if not rows:
        logger.info("No feedback rows found.")
        return pd.DataFrame(columns=["label", "text", "source", "confidence"])

    records = []
    for row in rows:
        label = _derive_label(row.user_correction, row.original_verdict)
        records.append({
            "scan_id": str(row.scan_id),
            "label":   label,
            "text":    row.input_text,
            "source":  "user_feedback",
        })

    df = pd.DataFrame(records)

    # Corroboration confidence: count feedback rows pointing to the same label
    # for each scan_id.  Multiple independent users agreeing = higher weight.
    corroboration = (
        df.groupby(["scan_id", "label"])
        .size()
        .reset_index(name="confidence")
    )
    df = df.merge(corroboration, on=["scan_id", "label"], how="left")

    result = df[["label", "text", "source", "confidence"]].copy()

    spam_count = (result["label"] == "spam").sum()
    ham_count  = (result["label"] == "ham").sum()
    logger.info(
        "Exported %d feedback rows — spam=%d, ham=%d (min_confidence=%.2f)",
        len(result), spam_count, ham_count, min_confidence,
    )
    return result


if __name__ == "__main__":
    # Quick CLI smoke-test
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    df = export_labeled_corrections()
    print(df.head(20).to_string())
    print(f"\nTotal: {len(df)} rows | spam={sum(df.label=='spam')} | ham={sum(df.label=='ham')}")
