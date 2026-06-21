"""
models package — imports all ORM models so SQLAlchemy registers them
with Base.metadata before create_all() is called in main.py lifespan.
"""

from backend.models.database import Base, SessionLocal, engine, get_db  # noqa: F401
from backend.models.user import User, UserRole                           # noqa: F401
from backend.models.scan import Scan, Verdict, ScanInputType            # noqa: F401
from backend.models.audit_log import AuditLog                           # noqa: F401
from backend.models.armoriq_log import ArmorIQLog, ArmorIQOutcome       # noqa: F401
from backend.models.threat_report import (                               # noqa: F401
    ThreatReport, ThreatSeverity, ThreatCategory,
)
from backend.models.feedback import ScanFeedback                         # noqa: F401

__all__ = [
    "Base", "SessionLocal", "engine", "get_db",
    "User", "UserRole",
    "Scan", "Verdict", "ScanInputType",
    "AuditLog",
    "ArmorIQLog", "ArmorIQOutcome",
    "ThreatReport", "ThreatSeverity", "ThreatCategory",
    "ScanFeedback",
]
