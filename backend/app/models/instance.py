"""Instance-level configuration — the per-company profile of THIS deployment.

One CI deployment serves exactly one company (instance-per-client model), and
``instance_profile`` is that company's identity: what vertical they're in, how
their prompts should speak, what the app is called, what currency reports use.

Distinct from ``business_profile`` (models/intelligence.py), which is *synced
from the client's source database* and would overwrite admin edits — this table
is CI-owned and only written through the admin config API / seed script.
"""

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class InstanceProfile(Base, TimestampMixin):
    """Singleton row (id=1) describing the company this instance is deployed for."""

    __tablename__ = "instance_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)

    # Who the client is — injected into AI prompts
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vertical: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_voice: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Vertical-specific domain expertise paragraph(s) keyed by prompt slot,
    # e.g. {"icp_expertise": "...", "call_analysis_notes": "..."}
    vertical_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"lead": "applicant", "closed_sale": "placement"}
    terminology: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Numeric/prose benchmarks prompts may cite, keyed by slot
    benchmarks: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # White-labeling — what the app calls itself in this deployment
    app_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tagline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # e.g. {"primary": "#F59E0B", "marketing": "#10B981", ...}
    colors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Reporting locale
    currency_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    currency_symbol: Mapped[str | None] = mapped_column(String(8), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(16), nullable=True)
