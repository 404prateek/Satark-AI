"""
Analyze router — POST /analyze/message  |  /analyze/image  |  /analyze/url

This is the central orchestration layer.  For every request it:
  1. Detects language (English / Hindi / Hinglish)
  2. Runs the TF-IDF + MultinomialNB classifier (+ SHAP attributions)
  3. Runs the behavioral rule engine
  4. (optional) Follows redirects + runs URL analysis if a URL is present
  5. (optional) Runs EasyOCR if input is a screenshot
  6. Aggregates all signals into a 0-100 risk score via risk_engine.py
  7. Calls Groq LLM to generate a human-readable explanation
  8. Persists the scan to PostgreSQL
  9. Returns the full ScanResponse JSON

ArmorIQ middleware already sanitised the input text before this router is
reached.  Use `request.state.sanitised_text` when available.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.language_detector import detect_language
from backend.ai.model_loader import get_model
from backend.ai.shap_explainer import SHAPExplainer
from backend.dependencies import get_current_user
from backend.models.database import get_db
from backend.models.scan import Scan, Verdict, ScanInputType
from backend.models.user import User
from backend.ocr.image_validator import validate_image
from backend.services.behavioral_service import score_behavior
from backend.services.groq_service import get_explanation
from backend.services.risk_engine import calculate_risk
from backend.url_analysis.url_analyzer import URLAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Singletons ────────────────────────────────────────────────────────────────
_url_analyzer = URLAnalyzer()
_shap_explainer: Optional[SHAPExplainer] = None

_URL_RE = re.compile(
    r'(https?://\S+|bit\.ly/\S+|t\.co/\S+|tinyurl\.com/\S+|www\.\S+)',
    re.IGNORECASE,
)


def _get_shap() -> SHAPExplainer:
    global _shap_explainer
    if _shap_explainer is None:
        _shap_explainer = SHAPExplainer(get_model())
    return _shap_explainer


# ── Schemas ───────────────────────────────────────────────────────────────────

class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000, description="SMS / email / message body to analyse")


class URLRequest(BaseModel):
    url: str = Field(..., min_length=5, max_length=2000)


class ScanResponse(BaseModel):
    scan_id:           str
    verdict:           str        # SAFE | SUSPICIOUS | PHISHING
    risk_score:        int        # 0–100
    confidence:        float      # 0.0–1.0 (NLP confidence of the predicted class)
    language:          str
    component_scores:  dict
    shap_features:     list[dict] # [{feature, value}, …]
    behavioral_triggers: list[str]
    explanation:       str
    url_found:         Optional[str]
    url_analysis:      Optional[dict]
    extracted_text:    Optional[str]   # OCR only
    ocr_confidence:    Optional[float] # OCR only
    model_version:     str
    analyzed_at:       str
    processing_ms:     int
    actions:           list[dict]


# ── Shared analysis core ──────────────────────────────────────────────────────

async def _run_core(
    text: str,
    db: AsyncSession,
    user: User,
    input_type: ScanInputType,
    extracted_text: Optional[str] = None,
    ocr_confidence: Optional[float] = None,
) -> ScanResponse:
    """Single analysis pipeline shared by all three route handlers."""
    t0 = time.perf_counter()

    # 1. Language
    language = await asyncio.to_thread(detect_language, text)

    # 2. NLP + SHAP (offloaded to thread — sklearn is sync)
    model = get_model()
    proba_arr = await asyncio.to_thread(model.predict_proba, [text])
    nlp_score = float(proba_arr[0][1])          # P(phishing)
    nlp_confidence = float(max(proba_arr[0]))    # confidence of the prediction
    shap_dict = await asyncio.to_thread(_get_shap().explain, text)

    # 3. Behavioral rules (fast, sync is fine)
    beh = score_behavior(text)
    behavioral_score: float = beh["behavioral_score"]
    triggers: list[str] = beh["triggers"]

    # 4. URL analysis (async-wrapped sync)
    url_match = _URL_RE.search(text)
    url_found: Optional[str] = url_match.group(0) if url_match else None
    url_score = 0.0
    url_analysis_dict: Optional[dict] = None

    if url_found:
        try:
            result = await asyncio.to_thread(_url_analyzer.analyze, url_found)
            url_score = result.score
            url_analysis_dict = result.to_dict()
        except Exception as exc:
            logger.warning("URL analysis failed for '%s': %s", url_found, exc)

    # 5. Risk aggregation
    risk = calculate_risk(
        nlp_score=nlp_score,
        behavioral_score=behavioral_score,
        url_score=url_score,
        ocr_score=(nlp_score * (ocr_confidence or 0.8)) if extracted_text else 0.0,
        has_url=url_found is not None,
        has_image=extracted_text is not None,
    )

    # 6. Groq LLM explanation
    explanation = await get_explanation(
        text=text,
        risk_score=risk["risk_score"],
        verdict=risk["verdict"],
        shap_features=shap_dict,
        triggers=triggers,
        language=language,
    )

    processing_ms = int((time.perf_counter() - t0) * 1000)

    # 7. Persist scan
    scan_id = str(uuid.uuid4())
    shap_list = [{"feature": k, "value": round(v, 4)} for k, v in shap_dict.items()]
    try:
        scan = Scan(
            id=uuid.UUID(scan_id),
            user_id=user.id,
            input_type=ScanInputType(input_type.value),
            raw_input=text[:4000],
            language=language,
            verdict=Verdict(risk["verdict"]),
            risk_score=float(risk["risk_score"]),
            confidence=nlp_confidence,
            model_version="v1.0",
            shap_features=shap_list,
            explanation=explanation,
            url_analysis=url_analysis_dict,
            ocr_text=extracted_text,
            ocr_confidence=ocr_confidence,
            ocr_word_count=len(extracted_text.split()) if extracted_text else None,
        )
        db.add(scan)
        await db.commit()
        await db.refresh(scan)
    except Exception as exc:
        logger.error("Failed to persist scan: %s", exc)
        await db.rollback()
        # Don't fail the user request over a DB error — continue with response

    # 8. Actions
    actions: list[dict] = [
        {"label": "Report to Cybercrime", "url": "https://cybercrime.gov.in", "type": "link"},
    ]
    if risk["verdict"] in ("PHISHING", "SUSPICIOUS"):
        actions.append({"label": "Report to CERT-In", "url": "https://www.cert-in.org.in", "type": "link"})
    if risk["verdict"] == "PHISHING":
        actions.append({"label": "Block Sender", "type": "action"})

    from datetime import datetime, timezone
    return ScanResponse(
        scan_id=scan_id,
        verdict=risk["verdict"],
        risk_score=risk["risk_score"],
        confidence=nlp_confidence,
        language=language,
        component_scores=risk["component_scores"],
        shap_features=shap_list,
        behavioral_triggers=triggers,
        explanation=explanation,
        url_found=url_found,
        url_analysis=url_analysis_dict,
        extracted_text=extracted_text,
        ocr_confidence=ocr_confidence,
        model_version="v1.0",
        analyzed_at=datetime.now(timezone.utc).isoformat(),
        processing_ms=processing_ms,
        actions=actions,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/message",
    response_model=ScanResponse,
    summary="Analyse a text message (SMS / email / WhatsApp)",
)
async def analyze_message(
    body: MessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScanResponse:
    # Prefer ArmorIQ-sanitised text if middleware already ran
    text = getattr(request.state, "sanitised_text", None) or body.message
    return await _run_core(text=text, db=db, user=user, input_type=ScanInputType.message)


@router.post(
    "/url",
    response_model=ScanResponse,
    summary="Analyse a URL for phishing indicators",
)
async def analyze_url(
    body: URLRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScanResponse:
    text = f"Analyse this link: {body.url}"
    return await _run_core(text=text, db=db, user=user, input_type=ScanInputType.url)


@router.post(
    "/image",
    response_model=ScanResponse,
    summary="Analyse a screenshot via OCR",
)
async def analyze_image(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ScanResponse:
    image_bytes = await file.read()

    # Validate image type, size, dimensions
    validation = validate_image(image_bytes, file.filename or "upload")
    if not validation.get("valid", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation.get("error", "Invalid image"),
        )

    # Lazy-import OCR service to avoid EasyOCR loading on non-image requests
    from backend.services.ocr_service import extract_from_image  # type: ignore
    ocr_result = await extract_from_image(image_bytes)

    extracted_text: str = ocr_result.get("text", "").strip()
    ocr_confidence: float = float(ocr_result.get("confidence", 0.0))

    if not extracted_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text could be extracted from this image. Try a higher-resolution screenshot.",
        )

    return await _run_core(
        text=extracted_text,
        db=db,
        user=user,
        input_type=ScanInputType.image,
        extracted_text=extracted_text,
        ocr_confidence=ocr_confidence,
    )



