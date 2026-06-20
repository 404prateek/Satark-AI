"""
ThreatReport ORM model — user-submitted or system-generated threat reports.

A ThreatReport links a Scan to a structured threat assessment that can be:
  - auto-generated for PHISHING scans above a risk threshold, or
  - manually submitted by an analyst after reviewing a scan.

Reports are shared across the platform (other users can view PHISHING reports
for situational awareness) unlike Scans which are private per-user.
"""

from __future__ import annotations

import uuid
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.database import Base


class ThreatSeverity(str, PyEnum):
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


class ThreatCategory(str, PyEnum):
    phishing         = "phishing"
    smishing         = "smishing"          # SMS phishing
    vishing          = "vishing"           # voice phishing
    brand_impersonation = "brand_impersonation"
    malware_url      = "malware_url"
    credential_harvest = "credential_harvest"
    financial_fraud  = "financial_fraud"
    other            = "other"


class ThreatReport(Base):
    __tablename__ = "threat_reports"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )

    # ── Parent scan ───────────────────────────────────────────────────────────
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Reporting user ────────────────────────────────────────────────────────
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Classification ────────────────────────────────────────────────────────
    severity: Mapped[ThreatSeverity] = mapped_column(
        Enum(ThreatSeverity, name="threat_severity", create_type=True),
        nullable=False,
        index=True,
    )
    category: Mapped[ThreatCategory] = mapped_column(
        Enum(ThreatCategory, name="threat_category", create_type=True),
        nullable=False,
    )

    # ── Details ───────────────────────────────────────────────────────────────
    title:           Mapped[str]       = mapped_column(String(255), nullable=False)
    description:     Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_brand:  Mapped[str | None] = mapped_column(String(128), nullable=True)  # e.g. "SBI"
    malicious_url:   Mapped[str | None] = mapped_column(String(2048), nullable=True)
    confidence:      Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── Status flags ─────────────────────────────────────────────────────────
    is_verified:    Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_public:      Mapped[bool] = mapped_column(Boolean, default=True,  nullable=False)
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    scan = relationship("Scan", back_populates="threat_reports")
    user = relationship("User", back_populates="threat_reports")

    def __repr__(self) -> str:
        return f"<ThreatReport id={self.id} severity={self.severity} category={self.category}>"
