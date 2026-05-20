"""
Shared Operator registry.

Operators are Level-1 single-purpose, deterministic tasks that can be
invoked by any department (marketing, sales, fulfillment).  Each entry in
``OPERATOR_REGISTRY`` maps an operator ID to its metadata and Celery task.

Sprint 2 / CI-CORE-01 / T01-6
"""

from __future__ import annotations

from typing import Any

from app.tasks.ads_stats import update_ads_stats
from app.tasks.icp import generate_icp
from app.tasks.offer_generator import generate_offers
from app.tasks.transcriber import transcribe_video

OPERATOR_REGISTRY: dict[str, dict[str, Any]] = {
    "CI-OPS-TRANSCRIBE": {
        "name": "Transcriber",
        "description": (
            "Transcribes video/audio URLs into text transcripts with "
            "call type classification"
        ),
        "task": transcribe_video,
        "departments": ["marketing", "sales", "fulfillment"],
    },
    "CI-OPS-ICP": {
        "name": "ICP Generator",
        "description": (
            "Aggregates shared intelligence pool data and synthesises "
            "Ideal Customer Profile segments via Claude"
        ),
        "task": generate_icp,
        "departments": ["marketing", "sales"],
    },
    "OPS-SA1": {
        "name": "Ads Stats Updater",
        "description": (
            "Pulls paid advertising metrics from Facebook Ads, Google Ads, "
            "and Instagram Ads and upserts them into the ads_stats table"
        ),
        "task": update_ads_stats,
        "departments": ["marketing"],
    },
    "OPS-O2": {
        "name": "Offer Generator",
        "description": (
            "Auto-generates offer drafts from ICP and pain point data, "
            "persisting them to the offers table for human review"
        ),
        "task": generate_offers,
        "departments": ["marketing", "sales"],
    },
}


def get_operator(operator_id: str) -> dict[str, Any] | None:
    """Look up an operator by its registry ID.

    Parameters
    ----------
    operator_id:
        e.g. ``"CI-OPS-TRANSCRIBE"``

    Returns
    -------
    dict | None
        The operator metadata dict, or ``None`` if not found.
    """
    return OPERATOR_REGISTRY.get(operator_id)
