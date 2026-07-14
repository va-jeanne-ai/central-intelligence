"""Unhandled exceptions must return the standard JSON error envelope.

Without this, Starlette's ServerErrorMiddleware answers with a bare text 500
from OUTSIDE the CORS middleware, so browsers report the failure as a CORS
error instead of the real 500 (see EMAXCONNSESSION incident, 2026-07-15).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.middleware.error_envelope import ErrorEnvelopeMiddleware

ORIGIN = "http://localhost:3000"


def _build_app() -> FastAPI:
    """Minimal app mirroring main.py's middleware order: CORS wraps errors."""
    app = FastAPI()

    app.add_middleware(ErrorEnvelopeMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/boom")
    async def boom():
        raise RuntimeError("simulated pool exhaustion")

    return app


def test_unhandled_exception_returns_json_envelope():
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/boom", headers={"Origin": ORIGIN})

    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "requestId" in body["error"]
    # The raw exception text must not leak to clients.
    assert "simulated pool exhaustion" not in resp.text


def test_unhandled_exception_carries_cors_headers():
    client = TestClient(_build_app(), raise_server_exceptions=False)
    resp = client.get("/boom", headers={"Origin": ORIGIN})

    assert resp.headers.get("access-control-allow-origin") == ORIGIN
