"""Response schema for the analyze-view endpoint."""

from pydantic import BaseModel, Field, field_validator


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


# ─── Follow-up chat (deliverable 8) ─────────────────────────────────────────

MAX_CHAT_MESSAGES = 20
MAX_CHAT_CONTENT_LEN = 4000


class ChatMessageIn(BaseModel):
    """One turn in the running follow-up conversation."""

    role: str
    content: str = Field(default="")

    @field_validator("role")
    @classmethod
    def _role_must_be_user_or_assistant(cls, v: str) -> str:
        if v not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        return v

    @field_validator("content")
    @classmethod
    def _content_len(cls, v: str) -> str:
        if len(v) > MAX_CHAT_CONTENT_LEN:
            raise ValueError(f"content exceeds {MAX_CHAT_CONTENT_LEN} characters")
        return v


class AnalyzeChatRequest(BaseModel):
    messages: list[ChatMessageIn] = Field(default_factory=list)

    @field_validator("messages")
    @classmethod
    def _cap_message_count(cls, v: list[ChatMessageIn]) -> list[ChatMessageIn]:
        if len(v) > MAX_CHAT_MESSAGES:
            raise ValueError(f"messages exceeds cap of {MAX_CHAT_MESSAGES}")
        return v


class AnalyzeChatResponse(BaseModel):
    reply: str
    model: str | None = None
    generated_at: str
