"""
ArmorIQLog ORM model — tamper-evident AI security audit log.

Every LLM request processed by the ArmorIQ middleware produces one record.
Outcome can be:
  ALLOWED  — request passed all checks and reached the LLM.
  BLOCKED  — request was rejected before the LLM was called.
  FLAGGED  — LLM response failed output guardrails.

The input_hash and output_hash columns store SHA-256 digests of the
sanitised input and LLM output respectively.  Auditors can verify
integrity by recomputing the hash from the stored (or separately logged)
plaintext.

NOTE: This model is also used directly by backend/armoriq/audit_logger.py.
      The model defined here is the canonical ORM representation; the one
      previously sketched in audit_logger.py is superseded by this file.
"""

from __future__ import annotations

import uuid
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.database import Base


class ArmorIQOutcome(str, PyEnum):
    ALLOWED  = "ALLOWED"
    BLOCKED  = "BLOCKED"
    FLAGGED  = "FLAGGED"


class ArmorIQLog(Base):
    __tablename__ = "armoriq_logs"
    __table_args__ = (
        Index("ix_armoriq_logs_request_id", "request_id"),
        Index("ix_armoriq_logs_outcome",    "outcome"),
        Index("ix_armoriq_logs_created",    "created_at"),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )

    # ── Request identity ──────────────────────────────────────────────────────
    request_id:  Mapped[str] = mapped_column(String(64),  nullable=False)
    route:       Mapped[str] = mapped_column(String(256), nullable=False)

    # ── Outcome ───────────────────────────────────────────────────────────────
    outcome: Mapped[ArmorIQOutcome] = mapped_column(
        Enum(ArmorIQOutcome, name="armoriq_outcome", create_type=True),
        nullable=False,
    )

    # ── Tamper-evident hashes ─────────────────────────────────────────────────
    input_hash:  Mapped[str]        = mapped_column(String(64), nullable=False)   # SHA-256 hex
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)    # NULL if BLOCKED

    # ── Block / flag detail ───────────────────────────────────────────────────
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── HTTP context ──────────────────────────────────────────────────────────
    ip_address: Mapped[str | None] = mapped_column(String(64),  nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # ── Timestamp ─────────────────────────────────────────────────────────────
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ArmorIQLog id={self.id} outcome={self.outcome} route={self.route!r}>"
