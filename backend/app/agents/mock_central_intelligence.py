"""
MockCentralIntelligence — Simulates Central Intelligence responses without an Anthropic API key.

Used when MOCK_MODE=true in settings. Returns realistic canned responses
with simulated streaming delays so the full UI pipeline can be tested.
"""

import asyncio
import random
from typing import AsyncIterator

MOCK_RESPONSES: dict[str, str] = {
    "default": (
        "Great question! Here's what I'm seeing across your departments:\n\n"
        "**Sales** is performing well this week with **47 new leads** — that's up 9% from last week. "
        "Your best-performing source is **Webinar** at an 18.4% close rate.\n\n"
        "**Marketing** metrics are solid:\n"
        "- Email CTR: **8.4%** (above industry average)\n"
        "- Social reach: **12k** this week\n"
        "- ROAS: **2.1x** on paid campaigns\n\n"
        "**Fulfillment** is steady with **84 active members** and 91% satisfaction. "
        "However, I'd flag that **3 members** missed their weekly submission — "
        "a quick check-in could prevent churn.\n\n"
        "**My top recommendation for this week:** Follow up on the 23 stale applications "
        "averaging 11 days old. Those leads are going cold. Want me to break down any department in detail?"
    ),
    "leads": (
        "Here's your lead pipeline breakdown:\n\n"
        "**This Week:** 47 new leads (up 9%)\n\n"
        "| Source | Leads | Close Rate |\n"
        "|--------|-------|------------|\n"
        "| Webinar | 21 (45%) | 18.4% |\n"
        "| VSL | 14 (30%) | 11.2% |\n"
        "| Opt-in | 12 (25%) | 7.9% |\n\n"
        "**Best day:** Tuesday with 12 leads.\n\n"
        "**Action items:**\n"
        "1. Prioritize the **8 webinar leads** that haven't booked — highest quality source\n"
        "2. **23 stale applications** need follow-up (avg age: 11 days)\n"
        "3. Consider A/B testing the VSL hook — the \"cash flow\" pain point appeared in 7 recent calls\n\n"
        "Would you like me to dig deeper into any source?"
    ),
    "marketing": (
        "Here's the Marketing Department overview:\n\n"
        "**Email Performance:**\n"
        "- Open rate: **42.3%** (excellent)\n"
        "- CTR: **8.4%** (above 5% benchmark)\n"
        "- Unsubscribe rate: **0.3%** (healthy)\n\n"
        "**Social Media:**\n"
        "- Total reach: **12,400** this week\n"
        "- Engagement rate: **4.2%**\n"
        "- Best performer: Instagram Reel on objection handling (+340 saves)\n\n"
        "**Funnels:**\n"
        "- Webinar funnel conversion: **3.8%** (down 4% — needs attention)\n"
        "- VSL funnel: **2.1%** (stable)\n\n"
        "**Recommendation:** The webinar funnel drop is your biggest lever right now. "
        "The last email sequence had low CTR (2.1%) — I'd suggest A/B testing the CTA button copy."
    ),
    "hello": (
        "Good morning! I'm Central Intelligence, your AI business command center.\n\n"
        "I have access to insights across all three departments:\n"
        "- **Sales** — Leads, pipeline, call analysis\n"
        "- **Marketing** — Email, social, funnels, ads, content\n"
        "- **Fulfillment** — Members, coaching, accountability\n\n"
        "I can help you with:\n"
        "- Cross-department performance summaries\n"
        "- Strategic recommendations based on your data\n"
        "- Identifying trends and action items\n\n"
        "What would you like to explore today?"
    ),
}


def _pick_response(message: str) -> str:
    """Choose a mock response based on keywords in the user message."""
    lower = message.lower()
    if any(w in lower for w in ["hello", "hi", "hey", "morning", "help"]):
        return MOCK_RESPONSES["hello"]
    if any(w in lower for w in ["lead", "pipeline", "prospect", "sales call"]):
        return MOCK_RESPONSES["leads"]
    if any(w in lower for w in ["marketing", "email", "social", "funnel", "ad"]):
        return MOCK_RESPONSES["marketing"]
    return MOCK_RESPONSES["default"]


class MockCentralIntelligence:
    """Drop-in replacement for CentralIntelligence that streams canned responses."""

    def __init__(self) -> None:
        self.agent_id = "CI-CORE-00-MOCK"
        self.name = "Central Intelligence (Mock)"

    async def stream_response(self, message: str) -> AsyncIterator[str]:
        """Simulate streaming by yielding small chunks with random delays."""
        response = _pick_response(message)
        words = response.split(" ")

        # Yield 2-4 words at a time with small delays
        i = 0
        while i < len(words):
            chunk_size = random.randint(2, 4)
            chunk = " ".join(words[i : i + chunk_size])
            if i > 0:
                chunk = " " + chunk
            yield chunk
            i += chunk_size
            await asyncio.sleep(random.uniform(0.02, 0.08))

    async def execute(self, message: str) -> dict:
        """Non-streaming mock execution."""
        chunks = []
        async for chunk in self.stream_response(message):
            chunks.append(chunk)
        return {"agent_id": self.agent_id, "response": "".join(chunks)}

    def reset_conversation(self) -> None:
        pass
