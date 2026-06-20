"""
User ORM model — identity, access control, and Google OAuth support.
"""

from __future__ import annotations

import uuid
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.database import Base


class UserRole(str, PyEnum):
    admin   = "admin"
    analyst = "analyst"
    viewer  = "viewer"


class User(Base):
    __tablename__ = "users"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True,
    )
    username: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True,
    )
    # NULL when the user authenticates exclusively via Google OAuth
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Google OAuth ──────────────────────────────────────────────────────────
    google_id:      Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    google_picture: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # ── Access control ────────────────────────────────────────────────────────
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", create_type=True),
        default=UserRole.viewer,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )
    last_login_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    scans          = relationship("Scan",          back_populates="user", lazy="raise")
    audit_logs     = relationship("AuditLog",      back_populates="user", lazy="raise")
    threat_reports = relationship("ThreatReport",  back_populates="user", lazy="raise")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
