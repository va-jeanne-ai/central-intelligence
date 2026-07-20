"""Per-instance business context for AI prompts.

Prompt modules declare ``{{slot}}`` tokens (e.g. ``{{vertical}}``) in their
templates and render them through :func:`render`. The values come from a
:class:`PromptProfile`, loaded from the ``instance_profile`` table and cached
per-process.

Defaults are the literals that were hardcoded in the prompts before
productization Phase 1 (this deployment's original client), so an instance
with no ``instance_profile`` row behaves exactly as before. New instances
always seed a profile (scripts/seed_instance_profile.py), which overrides
every default.

Token replacement is plain ``str.replace`` on ``{{name}}`` — deliberately not
``str.format`` or ``string.Template``, because prompt bodies are full of JSON
braces and currency ``$``/``£`` signs that those engines would trip on.

Cache lifecycle: ``prime_profile_cache()`` runs at FastAPI startup and Celery
worker init; the admin PUT /config/profile endpoint re-primes after a write.
Celery workers pick up profile edits on their next restart (or re-prime).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromptProfile:
    """The slot values prompts can reference. Defaults = pre-Phase-1 literals."""

    business_name: str = "the business"
    # What the platform calls itself in prompts (white-label name)
    app_name: str = "Central Intelligence"
    # Adjective form, composed in templates as e.g. "{{vertical}} businesses"
    vertical: str = "coaching and consulting"
    business_description: str = ""
    target_audience: str = ""
    brand_voice: str = ""
    # Named prose blocks (vertical_context JSONB), e.g. "icp_expertise"
    vertical_context: dict[str, str] = field(default_factory=dict)
    # Named benchmark snippets (benchmarks JSONB), referenced as {{bm_<key>}}
    benchmarks: dict[str, str] = field(default_factory=dict)
    currency_symbol: str = "$"

    def slots(self) -> dict[str, str]:
        base = {
            "business_name": self.business_name,
            "app_name": self.app_name,
            "vertical": self.vertical,
            "business_description": self.business_description,
            "target_audience": self.target_audience,
            "brand_voice": self.brand_voice,
            "currency_symbol": self.currency_symbol,
        }
        base.update({k: str(v) for k, v in self.vertical_context.items()})
        base.update({f"bm_{k}": str(v) for k, v in self.benchmarks.items()})
        return base


# The pre-Phase-1 literals. See module docstring for why these are the defaults.
DEFAULT_PROFILE = PromptProfile(
    vertical_context={
        # ICP generator, "Expertise" discipline #3 (icp_generator_v1.py)
        "icp_expertise": (
            "**Coaching & consulting business models** — You understand that buyers "
            "of high-ticket coaching programmes are driven by transformation, not "
            "information.  You know the difference between a lead who is "
            '"tire-kicking" and one who is at the edge of a buying decision.'
        ),
    },
)

_cached_profile: PromptProfile | None = None


def current_profile() -> PromptProfile:
    """The primed per-process profile, or the defaults when never primed."""
    return _cached_profile if _cached_profile is not None else DEFAULT_PROFILE


def render(template: str, profile: PromptProfile | None = None) -> str:
    """Substitute every ``{{slot}}`` token in ``template`` from the profile."""
    p = profile if profile is not None else current_profile()
    out = template
    for key, val in p.slots().items():
        out = out.replace("{{" + key + "}}", val)
    return out


def _profile_from_row(row) -> PromptProfile:
    """Build a PromptProfile from an instance_profile ORM row, keeping defaults
    for any NULL column so a partially-filled row never blanks a slot."""
    overrides: dict = {}
    for attr in (
        "business_name", "vertical", "business_description",
        "target_audience", "brand_voice", "currency_symbol",
    ):
        val = getattr(row, attr, None)
        if val:
            overrides[attr] = val
    merged_ctx = dict(DEFAULT_PROFILE.vertical_context)
    merged_ctx.update(row.vertical_context or {})
    merged_bm = dict(DEFAULT_PROFILE.benchmarks)
    merged_bm.update(row.benchmarks or {})
    overrides["vertical_context"] = merged_ctx
    overrides["benchmarks"] = merged_bm
    return PromptProfile(**overrides)


async def load_profile(session) -> PromptProfile:
    """Read instance_profile from the DB (no caching). Defaults when absent."""
    from sqlalchemy import select

    from app.models.instance import InstanceProfile

    row = (await session.execute(select(InstanceProfile).limit(1))).scalar_one_or_none()
    return _profile_from_row(row) if row is not None else DEFAULT_PROFILE


def load_profile_sync(session) -> PromptProfile:
    """Sync twin of :func:`load_profile` for sync-Session Celery tasks."""
    from sqlalchemy import select

    from app.models.instance import InstanceProfile

    row = session.execute(select(InstanceProfile).limit(1)).scalar_one_or_none()
    return _profile_from_row(row) if row is not None else DEFAULT_PROFILE


async def prime_profile_cache(session) -> PromptProfile:
    """Load the profile and cache it for this process. Failure-safe: on any
    error the cache is left as-is and defaults apply."""
    global _cached_profile
    try:
        _cached_profile = await load_profile(session)
        logger.info("Prompt profile primed (vertical=%r)", _cached_profile.vertical)
    except Exception:  # noqa: BLE001 — startup must not die on a config read
        logger.exception("Prompt profile prime failed; using defaults")
    return current_profile()


def invalidate_profile_cache() -> None:
    global _cached_profile
    _cached_profile = None
