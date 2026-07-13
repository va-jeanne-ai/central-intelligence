"""View analysis — grounded LLM narrative over the current filtered list view.

Each filterable list surface registers a Surface here. The /analyze/{surface}
route looks the surface up, re-runs the filtered query via its aggregate()
(which builds filters from app.repositories.list_filters — the same builders
the list endpoints use), and hands the aggregates to the narrative step.
Numbers in the narrative can only come from the aggregates.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class Surface:
    key: str                 # URL segment: /analyze/{key}
    label: str               # human label: "appointments"
    describe: str            # one paragraph telling the LLM what the fields mean
    parse_filters: Callable[[Mapping[str, str]], dict]      # query params -> builder kwargs
    echo: Callable[[dict], str]                             # kwargs -> human-readable filter echo
    aggregate: Callable[[AsyncSession, dict], Awaitable[dict]]


_REGISTRY: dict[str, Surface] = {}


def register(surface: Surface) -> Surface:
    _REGISTRY[surface.key] = surface
    return surface


def get_surface(key: str) -> Surface | None:
    return _REGISTRY.get(key)


def all_surfaces() -> list[Surface]:
    return list(_REGISTRY.values())


# Import for side effect: each module registers its Surface at import time.
# These imports MUST stay at the bottom (they import this module back).
# TODO(Task 5-8): Uncomment the four surface imports once their modules exist
# from app.analytics.view_analysis import (  # noqa: E402,F401
#     appointments,
#     leads,
#     sales_calls,
#     team_members,
# )
