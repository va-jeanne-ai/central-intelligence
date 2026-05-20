"""Pydantic schemas for DM outreach endpoints."""
from __future__ import annotations
from pydantic import BaseModel


class DMAnalyzeRequest(BaseModel):
    icp_segment: str | None = None
    objective: str | None = None


class DMAnalyzeResponse(BaseModel):
    analysis: str
    sequence: list[str]
    recommendations: list[str]
    data_used: dict


class DMDataResponse(BaseModel):
    outreach_sent: int
    response_rate: float
    meetings_booked: int
    top_sequences: list[dict]
    generated_at: str
