"""Catch unhandled exceptions and answer with the standard JSON error envelope.

Starlette's built-in ServerErrorMiddleware sits OUTSIDE every user middleware,
so its bare text 500 never passes through CORSMiddleware — browsers then report
the failure as a CORS violation and the real error is invisible to the client.
This middleware sits INSIDE CORS (added before it in main.py), so its response
gets Access-Control-Allow-* headers like any other.
"""

import logging
import uuid
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class ErrorEnvelopeMiddleware(BaseHTTPMiddleware):
    """Convert any unhandled exception into a JSON 500 with the error envelope."""

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            return await call_next(request)
        except Exception:  # noqa: BLE001 — last-resort handler, log and envelope
            request_id = str(uuid.uuid4())
            logger.exception(
                "Unhandled exception (requestId=%s) %s %s",
                request_id,
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Internal server error",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "requestId": request_id,
                    }
                },
            )
