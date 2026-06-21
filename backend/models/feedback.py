"""
ScanFeedback ORM model.

Stores user corrections on individual scans.  Every row in this table is a
signal that the model got something right or wrong on real-world input.
Over time, aggregating these corrections into retraining runs is the primary
mechanism by which Satark AI can improve after its initial training freeze.

Correction semantics
─────────────────────
  "correct"          – user agrees with the model's verdict; reinforce.
  "false_positive"   – model said PHISHING/SUSPICIOUS, but message was safe.
                       Correct label: "ham" (safe).
  "false_negative"   – model said SAFE, but message was actually a scam.
                       Correct label: "spam" (phishing).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.database import Base


class ScanFeedback(Base):
    __tablename__ = "scan_feedback"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )

    # ── Foreign keys ──────────────────────────────────────────────────────────
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable — anonymous feedback is allowed (scan_id is enough to trace context).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Verdict snapshot ──────────────────────────────────────────────────────
    # Denormalised here so the training-data export doesn't need to re-join
    # back to scans for every row when rebuilding the label.
    original_verdict: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )  # SAFE | SUSPICIOUS | PHISHING

    # ── User correction ───────────────────────────────────────────────────────
    user_correction: Mapped[str] = mapped_column(
        String(20), nullable=False,
    )  # "correct" | "false_positive" | "false_negative"

    corrected_label: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
    )  # "SAFE" | "PHISHING" — what it actually should be

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamp ─────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    scan = relationship("Scan", lazy="raise")
    user = relationship("User", lazy="raise")

    def __repr__(self) -> str:
        return (
            f"<ScanFeedback scan={self.scan_id} "
            f"correction={self.user_correction} label={self.corrected_label}>"
        )
