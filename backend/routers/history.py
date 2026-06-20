from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, desc, func as sqlfunc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_current_user
from backend.models.database import get_db
from backend.models.scan import Scan
from backend.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["History"])

@router.get(
    "/history",
    summary="Get current user's recent scans",
)
async def get_history(
    page: int = 1,
    limit: int = 20,
    verdict: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    query = select(Scan).where(Scan.user_id == user.id).order_by(desc(Scan.created_at))
    if verdict:
        query = query.where(Scan.verdict == verdict.upper())

    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    scans = result.scalars().all()

    count_query = select(sqlfunc.count()).select_from(Scan).where(Scan.user_id == user.id)
    if verdict:
        count_query = count_query.where(Scan.verdict == verdict.upper())
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return {
        "items": [
            {
                "scan_id":     str(s.id),
                "input_type":  s.input_type.value if s.input_type else None,
                "input_preview": (s.raw_input or s.ocr_text or "")[:120],
                "verdict":     s.verdict.value if s.verdict else None,
                "risk_score":  s.risk_score,
                "language":    s.language,
                "created_at":  s.created_at.isoformat() if s.created_at else None,
            }
            for s in scans
        ],
        "total": total,
        "page":  page,
        "pages": max(1, -(-total // limit)),
    }

@router.get(
    "/report/{scan_id}",
    summary="Get full details of a specific scan",
)
async def get_report(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(Scan).where(Scan.id == scan_id, Scan.user_id == user.id)
    )
    scan = result.scalars().first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found or access denied.",
        )

    # Return full details including shap_features and component scores.
    # We rebuild the component scores from the individual fields for the response.
    return {
        "scan_id": str(scan.id),
        "input_type": scan.input_type.value if scan.input_type else None,
        "raw_input": scan.raw_input,
        "verdict": scan.verdict.value if scan.verdict else None,
        "risk_score": scan.risk_score,
        "confidence": scan.confidence,
        "language": scan.language,
        "component_scores": {
            "nlp": scan.confidence * 100,
            "url": scan.url_analysis.get("score", 0) if scan.url_analysis else 0,
            "behavioral": 0, # Note: behavior score was lost unless persisted somewhere, we fallback to 0 or derive it
            "ocr": scan.ocr_confidence * 100 if scan.ocr_confidence else 0,
        },
        "shap_features": scan.shap_features,
        "explanation": scan.explanation,
        "url_analysis": scan.url_analysis,
        "ocr_text": scan.ocr_text,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
    }
