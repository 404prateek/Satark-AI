"""
ArmorIQ Audit Logger

Writes a tamper-evident log record for every AI request that passes through
the ArmorIQ security layer.  Records are stored in the ``armoriq_logs``
PostgreSQL table.

Tamper-evidence design:
  We store SHA-256 hashes of both the (sanitised) input and the LLM output.
  An auditor can recompute the hash from stored text and verify it matches —
  any modification to the stored text will produce a different hash.
  This is not a cryptographic signature (we don't have a private key), but
  it provides integrity checking against accidental or low-sophistication
  tampering.  For stronger guarantees, the hash column can be signed with an
  HSM key or written to an append-only ledger.

Why async?
  Audit logging must not slow down the analysis response.  We use an async
  SQLAlchemy session and fire-and-forget (the router awaits it but does not
  gate the user response on it).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, DateTime, Enum, Integer, String, Text, text
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.database import Base, SessionLocal

logger = logging.getLogger(__name__)


from backend.models.armoriq_log import ArmorIQOutcome, ArmorIQLog


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sha256(text: str) -> str:
    """Returns the hex-encoded SHA-256 digest of the input string (UTF-8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── Public API ────────────────────────────────────────────────────────────────

async def log_request(
    *,
    request_id:   str,
    route:        str,
    outcome:      ArmorIQOutcome,
    sanitised_input: str,
    llm_output:   str | None = None,
    block_reason: str | None = None,
    user_agent:   str | None = None,
    ip_address:   str | None = None,
) -> None:
    """
    Persists a tamper-evident audit record for an ArmorIQ-protected request.

    This function is designed to be awaited but *not* to propagate database
    errors back to the caller — a logging failure must never break the main
    analysis response.

    Args:
        request_id:      UUID identifying the HTTP request.
        route:           FastAPI path (e.g. "/api/v1/analyze/message").
        outcome:         ALLOWED | BLOCKED | FLAGGED.
        sanitised_input: The user text *after* prompt-guard sanitisation.
                         We store its hash, not the plaintext.
        llm_output:      Raw LLM response (hashed before storage).  None if
                         the request was blocked before an LLM call.
        block_reason:    Rejection reason(s) joined into a single string.
        user_agent:      HTTP User-Agent header value.
        ip_address:      Client IP.
    """
    record = ArmorIQLog(
        request_id=request_id,
        route=route,
        outcome=outcome,
        input_hash=_sha256(sanitised_input),
        output_hash=_sha256(llm_output) if llm_output is not None else None,
        block_reason=block_reason,
        user_agent=(user_agent or "")[:256],
        ip_address=(ip_address or "")[:64],
    )

    try:
        async with SessionLocal() as session:
            session.add(record)
            await session.commit()
            logger.debug(
                "ArmorIQ audit log written: request_id=%s outcome=%s",
                request_id, outcome.value,
            )
    except Exception as exc:
        # Log the failure but do NOT re-raise — audit errors must not
        # surface to users or abort the analysis pipeline.
        logger.error("ArmorIQ audit log write FAILED: %s", exc, exc_info=True)
