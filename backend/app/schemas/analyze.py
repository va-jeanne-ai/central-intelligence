"""Response schema for the analyze-view endpoint."""

from pydantic import BaseModel


class AnalyzeViewResponse(BaseModel):
    surface: str
    label: str
    filters_echo: str
    row_count: int
    empty: bool = False
    stats: dict
    narrative: str
    highlights: list[str]
    hypotheses: list[str]
    generated_at: str
    model: str | None = None
