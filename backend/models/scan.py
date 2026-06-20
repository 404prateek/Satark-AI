"""
Scan ORM model — stores the full result of one phishing-analysis request.

JSONB is used for shap_features and url_analysis because:
  - Their schema evolves independently of the DB schema.
  - PostgreSQL JSONB is indexable (GIN index) and supports containment queries.
  - Storing a list of {feature, value} dicts avoids a normalised
    many-to-many table that would add JOIN overhead for reads.
"""

from __future__ import annotations

import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    CheckConstraint, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.database import Base


class Verdict(str, PyEnum):
    SAFE       = "SAFE"
    SUSPICIOUS = "SUSPICIOUS"
    PHISHING   = "PHISHING"


class ScanInputType(str, PyEnum):
    message = "message"
    url     = "url"
    image   = "image"


class Scan(Base):
    __tablename__ = "scans"
    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 100", name="chk_risk_score_range"),
        CheckConstraint("confidence >= 0 AND confidence <= 1",   name="chk_confidence_range"),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )

    # ── Ownership ─────────────────────────────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Input ─────────────────────────────────────────────────────────────────
    input_type:    Mapped[ScanInputType] = mapped_column(
        Enum(ScanInputType, name="scan_input_type", create_type=True),
        nullable=False,
    )
    raw_input:     Mapped[str | None]  = mapped_column(Text, nullable=True)  # NULL for image scans
    language:      Mapped[str | None]  = mapped_column(String(20), nullable=True)  # en / hi / hinglish

    # ── ML output ─────────────────────────────────────────────────────────────
    verdict:       Mapped[Verdict] = mapped_column(
        Enum(Verdict, name="verdict", create_type=True),
        nullable=False,
        index=True,
    )
    risk_score:    Mapped[float]   = mapped_column(Float, nullable=False)     # 0–100
    confidence:    Mapped[float]   = mapped_column(Float, nullable=False)     # 0–1
    model_version: Mapped[str]     = mapped_column(String(64), nullable=False, default="v1.0")

    # ── Explainability ────────────────────────────────────────────────────────
    # [ {"feature": "str", "value": float}, … ]
    shap_features: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # ── LLM explanation ───────────────────────────────────────────────────────
    explanation:    Mapped[str | None] = mapped_column(Text, nullable=True)
    groq_model:     Mapped[str | None] = mapped_column(String(128), nullable=True)

    # ── URL analysis sub-results ──────────────────────────────────────────────
    # { final_url, redirect_chain, hop_count, whois_info, is_phishtank_hit, … }
    url_analysis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── OCR metadata (for image scans) ────────────────────────────────────────
    ocr_text:       Mapped[str | None]   = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_word_count: Mapped[int | None]   = mapped_column(Integer, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user           = relationship("User",          back_populates="scans")
    threat_reports = relationship("ThreatReport",  back_populates="scan", lazy="raise")

    def __repr__(self) -> str:
        return f"<Scan id={self.id} verdict={self.verdict} score={self.risk_score}>"
