"""
FastAPI application factory for the Central Intelligence API.

Usage
-----
Start with uvicorn:

    uvicorn app.main:app --reload --port 8000

The ``app`` object at module level is the ASGI entry point.  Use
``create_app()`` in tests to build isolated instances.

Router prefix strategy
----------------------
- health_router  is mounted under /api/v1  (prefix added here).
- central_intelligence_router carries its own full paths (/api/v1/... and /ws/v1/...)
  so it is mounted at the root with no prefix.  This avoids registering
  duplicate routes while keeping the WebSocket and HTTP paths on different
  URL segments.
- auth_router carries its own full prefix (/api/v1/auth/...) and is
  mounted at the root with no additional prefix.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware import AuthMiddleware

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Logging — configure once at import time so all modules share the same
# format.  Production deployments should override via LOG_LEVEL env var or
# an external logging config file.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)


def create_app() -> FastAPI:
    """Construct and configure the FastAPI application.

    Importing routers inside this function avoids circular imports and keeps
    the startup path explicit.
    """
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Central Intelligence API — "
            "AI-powered workforce management and agent orchestration."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # -----------------------------------------------------------------------
    # Middleware — Starlette uses LIFO order: the LAST add_middleware call
    # becomes the OUTERMOST layer.  We need CORS to wrap Auth so that even
    # 401 responses carry Access-Control-Allow-* headers.
    #
    # Execution order:  Request → CORS → Auth → Route
    # -----------------------------------------------------------------------
    app.add_middleware(AuthMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -----------------------------------------------------------------------
    # Routers
    # -----------------------------------------------------------------------
    from app.routes.auth import router as auth_router
    from app.routes.ci import router as ci_router
    from app.routes.dashboard import router as dashboard_router
    from app.routes.health import router as health_router
    from app.routes.icp import router as icp_router
    from app.routes.leads import router as leads_router
    from app.routes.marketing import router as marketing_router
    from app.routes.sales import router as sales_router
    from app.routes.fulfillment import router as fulfillment_router
    from app.routes.members import router as members_router
    from app.routes.appointments import router as appointments_router
    from app.routes.goals import router as goals_router
    from app.routes.tech_sos import router as tech_sos_router
    from app.routes.central_intelligence import router as central_intelligence_router
    from app.routes.directors import router as directors_router
    from app.routes.transcribe import router as transcribe_router
    from app.routes.social import router as social_router
    from app.routes.email import router as email_router
    from app.routes.funnels import router as funnels_router
    from app.routes.ads import router as ads_router
    from app.routes.dm import router as dm_router
    from app.routes.offers import router as offers_router, generate_router as offer_generate_router
    from app.routes.promo_calendar import router as promo_calendar_router
    from app.routes.integrations import router as integrations_router
    from app.routes.oauth import router as oauth_router
    from app.routes.meta_oauth import router as meta_oauth_router
    from app.routes.webhooks import router as webhooks_router
    from app.routes.chat_sessions import router as chat_sessions_router
    from app.routes.calendar import router as calendar_router

    # Health check under /api/v1 (prefix applied here).
    app.include_router(health_router, prefix="/api/v1")

    # Dashboard stats under /api/v1 (prefix applied here).
    # Resolves to GET /api/v1/dashboard/stats
    app.include_router(dashboard_router, prefix="/api/v1")

    # Leads endpoints under /api/v1 (prefix applied here).
    # Resolves to:  GET /api/v1/leads
    #               GET /api/v1/leads/stats
    app.include_router(leads_router, prefix="/api/v1")

    # Marketing endpoints under /api/v1 (prefix applied here).
    # Resolves to:  GET /api/v1/marketing/summary
    app.include_router(marketing_router, prefix="/api/v1")

    # Sales endpoints under /api/v1 (prefix applied here).
    # Resolves to:  GET /api/v1/sales/summary
    app.include_router(sales_router, prefix="/api/v1")

    # Fulfillment endpoints under /api/v1 (prefix applied here).
    # Resolves to:  GET /api/v1/fulfillment/summary  and  /api/v1/members/*
    app.include_router(fulfillment_router, prefix="/api/v1")
    app.include_router(members_router, prefix="/api/v1")

    # Appointments endpoints under /api/v1.
    # Resolves to:  GET /api/v1/appointments  and  /api/v1/appointments/*
    app.include_router(appointments_router, prefix="/api/v1")

    # Goals (accountability) endpoints under /api/v1.
    # Resolves to:  GET /api/v1/goals  and  /api/v1/goals/*
    app.include_router(goals_router, prefix="/api/v1")

    # Tech SOS (support tickets) endpoints under /api/v1.
    # Resolves to:  /api/v1/tech-sos  and  /api/v1/tech-sos/*  (incl. public /submit)
    app.include_router(tech_sos_router, prefix="/api/v1")

    # Transcription endpoint under /api/v1 (prefix applied here).
    # Resolves to:  POST /api/v1/transcribe
    app.include_router(transcribe_router, prefix="/api/v1")

    # Social media endpoints under /api/v1 (prefix applied here).
    # Resolves to:  POST /api/v1/social
    #               GET  /api/v1/social
    app.include_router(social_router, prefix="/api/v1")

    # Email marketing endpoints under /api/v1 (prefix applied here).
    # Resolves to:  POST /api/v1/email
    #               GET  /api/v1/email
    app.include_router(email_router, prefix="/api/v1")

    # Funnels endpoints under /api/v1 (prefix applied here).
    # Resolves to:  POST /api/v1/funnels
    app.include_router(funnels_router, prefix="/api/v1")

    # Ads endpoints under /api/v1.
    # Resolves to:  POST /api/v1/ads
    #               GET  /api/v1/ads
    app.include_router(ads_router, prefix="/api/v1")

    # DM outreach endpoints under /api/v1.
    # Resolves to:  POST /api/v1/dm
    #               GET  /api/v1/dm
    app.include_router(dm_router, prefix="/api/v1")

    # Offers endpoints under /api/v1.
    # Resolves to:  GET  /api/v1/offers
    #               POST /api/v1/offers
    app.include_router(offers_router, prefix="/api/v1")

    # Offer Generator trigger endpoint.
    # Resolves to:  POST /api/v1/offer-generate
    app.include_router(offer_generate_router, prefix="/api/v1")

    # Promo calendar endpoints under /api/v1.
    # Resolves to:  GET    /api/v1/promo-calendar
    #               POST   /api/v1/promo-calendar
    #               PUT    /api/v1/promo-calendar/{promotion_id}
    #               DELETE /api/v1/promo-calendar/{promotion_id}
    app.include_router(promo_calendar_router, prefix="/api/v1", tags=["promo-calendar"])

    # Integrations CRUD — UI-driven third-party connector activation.
    # Resolves to:  GET    /api/v1/integrations
    #               GET    /api/v1/integrations/{slug}
    #               POST   /api/v1/integrations/{slug}
    #               POST   /api/v1/integrations/{slug}/test
    #               DELETE /api/v1/integrations/{slug}
    app.include_router(integrations_router, prefix="/api/v1")

    # Google OAuth flow — per-user. /start is auth'd (frontend calls it
    # with the user's JWT); /callback is exempt (Google hits it
    # directly, state token encodes the user_id). See app/routes/oauth.py.
    # Resolves to:
    #   GET    /api/v1/integrations/google_workspace/oauth/start
    #   GET    /api/v1/integrations/google_workspace/oauth/callback
    #   GET    /api/v1/integrations/google_workspace/oauth/connected-users
    #   DELETE /api/v1/integrations/google_workspace/oauth/disconnect
    app.include_router(oauth_router, prefix="/api/v1")

    # Meta (Facebook/Instagram) OAuth — single shared business account.
    # The /callback is auth-exempt (Facebook redirects there directly); the
    # state token carries a CSRF nonce. See app/routes/meta_oauth.py.
    #   GET    /api/v1/integrations/instagram/oauth/start
    #   GET    /api/v1/integrations/instagram/oauth/callback
    #   DELETE /api/v1/integrations/instagram/oauth/disconnect
    app.include_router(meta_oauth_router, prefix="/api/v1")

    # Inbound webhook receivers — UNAUTHENTICATED (path is exempted in
    # AuthMiddleware via _EXEMPT_PREFIXES). Per-integration tokens in the
    # URL path are the auth mechanism. See app/routes/webhooks.py.
    # Resolves to:  POST /api/v1/webhooks/ghl/{webhook_token}/leads
    app.include_router(webhooks_router, prefix="/api/v1")

    # ICP endpoints under /api/v1 (prefix applied here).
    # Resolves to:  POST /api/v1/icp/generate
    #               GET  /api/v1/icp
    #               GET  /api/v1/icp/primary
    #               PUT  /api/v1/icp/:id
    app.include_router(icp_router, prefix="/api/v1")

    # Central Intelligence endpoints under /api/v1 (prefix applied here).
    # Resolves to:  GET  /api/v1/ci/calls
    #               GET  /api/v1/ci/insights
    #               GET  /api/v1/ci/content-ideas
    #               GET  /api/v1/ci/market-signals
    #               GET  /api/v1/ci/tags
    #               GET  /api/v1/ci/offers
    #               etc. (13 endpoints + 2 sync bridges)
    app.include_router(ci_router, prefix="/api/v1")

    # Central Intelligence router owns its own full paths:
    #   POST /api/v1/central-intelligence/chat
    #   WS   /ws/v1/central-intelligence/{session_id}
    # Mount at root so the decorator paths are used verbatim.
    app.include_router(central_intelligence_router)

    # Chat session CRUD owns its own full paths:
    #   GET    /api/v1/chat/sessions
    #   GET    /api/v1/chat/sessions/{id}
    #   PATCH  /api/v1/chat/sessions/{id}
    #   DELETE /api/v1/chat/sessions/{id}
    app.include_router(chat_sessions_router)

    # Calendar surface owns its own full paths:
    #   GET  /api/v1/calendar/events
    #   POST /api/v1/calendar/sync
    app.include_router(calendar_router)

    # Director routers own their own WebSocket paths:
    #   WS /ws/v1/{director_slug}/{session_id}
    # Mount at root so the decorator paths are used verbatim.
    app.include_router(directors_router)

    # Auth router owns its own full paths (/api/v1/auth/...).
    # Mount at root so the prefix defined in the router is used verbatim.
    app.include_router(auth_router)

    logger.info(
        "Central Intelligence API ready — debug=%s cors_origins=%s",
        settings.debug,
        settings.cors_origins,
    )

    return app


app = create_app()
