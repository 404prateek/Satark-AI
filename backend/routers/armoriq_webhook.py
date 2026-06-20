from fastapi import APIRouter, Request, Depends
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_db
from backend.models.armoriq_log import ArmorIQLog, ArmorIQOutcome
import hashlib
import uuid

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/webhook", summary="Receive ArmorClaw events")
async def receive_armoriq_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = await request.json()
        logger.info("Received ArmorIQ Webhook payload: %s", payload)

        # Map OpenClaw webhook payload to ArmorIQLog
        outcome_str = payload.get("outcome", "ALLOWED").upper()
        outcome = ArmorIQOutcome.ALLOWED
        if outcome_str == "BLOCKED" or payload.get("block"):
            outcome = ArmorIQOutcome.BLOCKED
        elif outcome_str == "FLAGGED":
            outcome = ArmorIQOutcome.FLAGGED

        # Generate hashes
        raw_input = str(payload.get("input", payload.get("message", "")))
        input_hash = hashlib.sha256(raw_input.encode()).hexdigest()
        
        output_hash = None
        if "output" in payload and payload["output"] is not None:
            output_hash = hashlib.sha256(str(payload["output"]).encode()).hexdigest()

        # Create record
        log_record = ArmorIQLog(
            request_id=payload.get("request_id", payload.get("runId", str(uuid.uuid4()))),
            route=payload.get("route", payload.get("toolName", "webhook")),
            outcome=outcome,
            input_hash=input_hash,
            output_hash=output_hash,
            block_reason=payload.get("blockReason", payload.get("reason", None)),
            user_agent=request.headers.get("user-agent", "OpenClaw"),
            ip_address=request.client.host if request.client else None,
        )

        db.add(log_record)
        await db.commit()
        
        return {"status": "ok"}
    except Exception as exc:
        logger.error("Failed to parse ArmorIQ webhook: %s", exc)
        return {"status": "error", "detail": str(exc)}
