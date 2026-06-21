"""
POST /api/v1/feedback/{scan_id}

Accepts a user correction on a completed scan and persists it to
scan_feedback.  Authentication is required — feedback is always tied to
the user who ran the original scan, which lets us weight trusted users'
corrections more heavily in future retraining runs.

Correction types
────────────────
  "correct"          – verdict was right; reinforces training data.
  "false_positive"   – model said PHISHING/SUSPICIOUS, but message was safe.
  "false_negative"   – model said SAFE, but message was actually a scam.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal, Optional

from backend.dependencies import get_current_user
from backend.models.database import get_db
from backend.models.feedback import ScanFeedback
from backend.models.scan import Scan
from backend.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Feedback"])

# ── Correction type → inferred corrected_label ────────────────────────────────
_CORRECTION_TO_LABEL: dict[str, str | None] = {
    "correct":        None,       # no override needed — original was right
    "false_positive": "SAFE",     # model over-fired; actual label is safe
    "false_negative": "PHISHING", # model missed it; actual label is phishing
}


# ── Request / Response schemas ────────────────────────────────────────────────

class FeedbackRequest(BaseModel):
    correction: Literal["correct", "false_positive", "false_negative"] = Field(
        ...,
        description=(
            "'correct' — verdict was right. "
            "'false_positive' — model flagged safe content as a threat. "
            "'false_negative' — model missed a real scam."
        ),
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional free-text from the user (e.g. 'This is my bank's official SMS').",
    )


class FeedbackResponse(BaseModel):
    status: str = "recorded"
    thank_you: bool = True
    feedback_id: str


# ── Route ─────────────────────────────────────────────────────────────────────

@router.post(
    "/feedback/{scan_id}",
    response_model=FeedbackResponse,
    summary="Submit a correction on a completed scan",
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    scan_id: str,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedbackResponse:
    """
    Record user feedback for a specific scan.

    - Verifies the scan exists and belongs to the authenticated user.
    - Derives the corrected label from the correction type.
    - Inserts a ScanFeedback row; idempotent per (scan_id, user_id) pair —
      submitting again overwrites the previous correction to avoid duplicate
      noise in training data.
    """
    # ── Validate scan_id format ───────────────────────────────────────────────
    try:
        scan_uuid = uuid.UUID(scan_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid scan_id — must be a valid UUID.",
        )

    # ── Look up the scan ──────────────────────────────────────────────────────
    result = await db.execute(
        select(Scan).where(Scan.id == scan_uuid, Scan.user_id == user.id)
    )
    scan = result.scalars().first()
    if scan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found or you do not have access to it.",
        )

    # ── Check for existing feedback from this user on this scan ──────────────
    existing_result = await db.execute(
        select(ScanFeedback).where(
            ScanFeedback.scan_id == scan_uuid,
            ScanFeedback.user_id == user.id,
        )
    )
    existing = existing_result.scalars().first()

    corrected_label = _CORRECTION_TO_LABEL.get(body.correction)

    if existing:
        # Update in place — avoid duplicate training rows for the same event.
        existing.user_correction = body.correction
        existing.corrected_label = corrected_label
        existing.notes = body.notes
        feedback_id = str(existing.id)
        logger.info(
            "Updated feedback %s for scan %s: %s → %s",
            feedback_id, scan_id, body.correction, corrected_label,
        )
    else:
        feedback = ScanFeedback(
            scan_id=scan_uuid,
            user_id=user.id,
            original_verdict=scan.verdict.value,
            user_correction=body.correction,
            corrected_label=corrected_label,
            notes=body.notes,
        )
        db.add(feedback)
        await db.flush()  # get the generated id before commit
        feedback_id = str(feedback.id)
        logger.info(
            "Recorded feedback %s for scan %s: %s → %s",
            feedback_id, scan_id, body.correction, corrected_label,
        )

    await db.commit()

    return FeedbackResponse(
        status="recorded",
        thank_you=True,
        feedback_id=feedback_id,
    )
