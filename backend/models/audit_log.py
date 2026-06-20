"""
AuditLog ORM model — general application event log.

Distinct from ArmorIQLog (which specifically records AI security events).
AuditLog captures all security-relevant user actions:
  - Login / logout
  - Password change
  - Role changes
  - Scan deletions
  - Admin operations

Stored as immutable append-only records (no UPDATE ever expected on this table).
The table is partitioned by created_at month in production via pg_partman;
for the hackathon, a single partition is fine.
"""

from __future__ import annotations

import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_id_created", "user_id", "created_at"),
        Index("ix_audit_logs_event_type",      "event_type"),
    )

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )

    # ── Actor (nullable: system-generated events have no user) ────────────────
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ── Event ─────────────────────────────────────────────────────────────────
    event_type:  Mapped[str] = mapped_column(String(64),  nullable=False)  # e.g. "LOGIN_SUCCESS"
    description: Mapped[str] = mapped_column(Text,        nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # affected object UUID

    # ── Request context ───────────────────────────────────────────────────────
    ip_address:  Mapped[str | None] = mapped_column(String(64),  nullable=True)
    user_agent:  Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_id:  Mapped[str | None] = mapped_column(String(64),  nullable=True)

    # ── Timestamp ─────────────────────────────────────────────────────────────
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} event={self.event_type!r} user={self.user_id}>"
