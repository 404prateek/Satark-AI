"""
ArmorIQ Security Middleware

A Starlette BaseHTTPMiddleware that intercepts every request to
``/analyze/*`` routes and enforces the four-layer ArmorIQ security model:

  Layer 0 — Request routing
    Only /analyze/* routes are inspected.  Health, auth, and static routes
    pass through without overhead.

  Layer 1 — Intent verification (request body)
    The raw request body is read, the primary text field extracted, and the
    IntentVerifier is run.  Malicious input is rejected with HTTP 422 before
    any downstream processing begins.

  Layer 2 — Prompt sanitisation
    The text is sanitised via PromptGuard and written back into the request
    state so that route handlers can retrieve it with ``request.state.sanitised_text``
    instead of re-reading the raw body.  The original body is also preserved
    so FastAPI can still parse it with Pydantic.

  Layer 3 — Audit logging (pre-call)
    A BLOCKED or ALLOWED record is written to PostgreSQL before the route
    handler runs so the log is tamper-evident even if the server crashes
    during handling.

  Layer 4 — Output guardrails (response body)
    After the route handler returns, the response body is intercepted.
    If it contains an LLM explanation field, the guardrails validator runs.
    Failing responses are replaced with a safe error payload and logged as
    FLAGGED.

Middleware ordering note:
  Add ArmorIQMiddleware AFTER CORSMiddleware in main.py so that preflight
  OPTIONS requests are handled by CORS before reaching ArmorIQ.

  app.add_middleware(ArmorIQMiddleware)   # ← add after CORS
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.armoriq.intent_verifier import IntentVerifier
from backend.armoriq.prompt_guard import sanitize
from backend.armoriq.guardrails import validate_llm_output, validate_analysis_json
from backend.armoriq.audit_logger import ArmorIQOutcome, log_request

logger = logging.getLogger(__name__)

# Routes that ArmorIQ inspects (prefix match)
_PROTECTED_PREFIXES = ("/api/v1/analyze",)

# JSON body field that contains the user message to analyse
_USER_TEXT_FIELDS = ("message", "text", "url", "content")


def _get_client_ip(request: Request) -> str:
    """Extract real client IP respecting common reverse-proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _extract_text_from_body(body: dict) -> str:
    """Returns the first recognised text field value from the parsed body."""
    for field in _USER_TEXT_FIELDS:
        if field in body and isinstance(body[field], str):
            return body[field]
    return ""


class ArmorIQMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that enforces the ArmorIQ 4-layer security model
    on all /analyze/* routes.
    """

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._verifier = IntentVerifier.get_instance()
        logger.info("ArmorIQ Security Middleware initialised.")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # ── 0. Route filter ───────────────────────────────────────────────────
        path = request.url.path
        if not any(path.startswith(prefix) for prefix in _PROTECTED_PREFIXES):
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        ip_address = _get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")[:256]
        route = path

        # ── 1. Read & parse request body ──────────────────────────────────────
        raw_body = await request.body()
        
        # Re-inject the body into request._receive so downstream handlers can read it
        async def receive():
            return {"type": "http.request", "body": raw_body}
        request._receive = receive

        body_dict: dict = {}
        user_text = ""

        if raw_body:
            try:
                body_dict = json.loads(raw_body)
                user_text = _extract_text_from_body(body_dict)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Body is not JSON (e.g. multipart image upload) — skip text checks
                pass

        # ── 2. Intent verification ────────────────────────────────────────────
        if user_text:
            verification = self._verifier.verify(user_text)
            if not verification.is_safe:
                reason_str = " | ".join(verification.reasons)
                logger.warning(
                    "ArmorIQ BLOCKED request_id=%s ip=%s reason=%s",
                    request_id, ip_address, reason_str,
                )
                await log_request(
                    request_id=request_id,
                    route=route,
                    outcome=ArmorIQOutcome.BLOCKED,
                    sanitised_input=user_text[:4_000],
                    block_reason=reason_str[:2_000],
                    user_agent=user_agent,
                    ip_address=ip_address,
                )
                return JSONResponse(
                    status_code=422,
                    content={
                        "detail": "Request blocked by ArmorIQ security layer.",
                        "reasons": verification.reasons,
                    },
                    headers={"X-ArmorIQ-Blocked": "true"},
                )

        # ── 3. Prompt sanitisation ────────────────────────────────────────────
        sanitised_text = sanitize(user_text) if user_text else ""

        # Store sanitised text for route handlers; rebuild body bytes so Pydantic
        # can re-parse the request normally (replace original field with sanitised value).
        if user_text and sanitised_text != user_text and body_dict:
            for field in _USER_TEXT_FIELDS:
                if field in body_dict:
                    body_dict[field] = sanitised_text
                    break

        # Attach to request state for downstream access
        request.state.armoriq_request_id = request_id
        request.state.sanitised_text = sanitised_text

        # Monkey-patch _body so FastAPI re-reads the sanitised version
        # (Starlette caches the body; we overwrite the cache)
        if user_text and sanitised_text != user_text:
            request._body = json.dumps(body_dict).encode("utf-8")  # type: ignore[attr-defined]

        # ── 4. Pre-call audit log (ALLOWED) ───────────────────────────────────
        await log_request(
            request_id=request_id,
            route=route,
            outcome=ArmorIQOutcome.ALLOWED,
            sanitised_input=sanitised_text or user_text,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        # ── 5. Call downstream route handler ──────────────────────────────────
        response = await call_next(request)

        # ── 6. Output guardrails ──────────────────────────────────────────────
        # Read response body (StreamingResponse needs to be consumed)
        response_body = b""
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            response_body += chunk if isinstance(chunk, bytes) else chunk.encode()

        # Only inspect JSON success responses
        if (
            response.status_code == 200
            and "application/json" in response.headers.get("content-type", "")
        ):
            try:
                resp_data = json.loads(response_body)

                # Validate structured JSON fields (verdict, risk_score, explanation)
                json_check = validate_analysis_json(resp_data)
                if not json_check.is_valid:
                    logger.warning(
                        "ArmorIQ FLAGGED (JSON guardrail) request_id=%s reasons=%s",
                        request_id, json_check.reasons,
                    )
                    await log_request(
                        request_id=request_id,
                        route=route,
                        outcome=ArmorIQOutcome.FLAGGED,
                        sanitised_input=sanitised_text or user_text,
                        llm_output=response_body.decode("utf-8", errors="replace")[:8_000],
                        block_reason=" | ".join(json_check.reasons),
                        user_agent=user_agent,
                        ip_address=ip_address,
                    )
                    return JSONResponse(
                        status_code=502,
                        content={
                            "detail": "LLM response failed ArmorIQ output guardrails.",
                            "reasons": json_check.reasons,
                        },
                        headers={"X-ArmorIQ-Flagged": "true"},
                    )

                # Also validate the free-text explanation for persona-breaks
                explanation = resp_data.get("explanation", "")
                if explanation:
                    text_check = validate_llm_output(explanation)
                    if not text_check.is_valid:
                        logger.warning(
                            "ArmorIQ FLAGGED (text guardrail) request_id=%s reasons=%s",
                            request_id, text_check.reasons,
                        )
                        await log_request(
                            request_id=request_id,
                            route=route,
                            outcome=ArmorIQOutcome.FLAGGED,
                            sanitised_input=sanitised_text or user_text,
                            llm_output=explanation[:8_000],
                            block_reason=" | ".join(text_check.reasons),
                            user_agent=user_agent,
                            ip_address=ip_address,
                        )
                        return JSONResponse(
                            status_code=502,
                            content={
                                "detail": "LLM explanation failed ArmorIQ content guardrails.",
                                "reasons": text_check.reasons,
                            },
                            headers={"X-ArmorIQ-Flagged": "true"},
                        )

            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # Non-JSON body (e.g. streaming) — skip guardrail

        # Return the original (or rebuilt) response
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
