"""OpenAI-compatible AI decision client."""

import time

from openai import OpenAI

from app.config import Settings
from app.models.decisions import AIDecision, hold_decision, parse_ai_decision
from app.prompts import SYSTEM_PROMPT, build_user_prompt
from app.state import AgentState


class AIClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAI(base_url=settings.openai_base_url, api_key=settings.openai_api_key or "missing")

    def decide(self, state: AgentState) -> tuple[str, AIDecision]:
        if not self.settings.openai_api_key:
            raw = '{"decision":"hold","delta":0,"reason":"OPENAI_API_KEY not configured","cooldown_minutes":30}'
            return raw, parse_ai_decision(raw)

        attempts = max(1, self.settings.ai_max_retries + 1)
        last_error = ""
        for attempt in range(attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.settings.openai_model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_user_prompt(state)},
                    ],
                    temperature=0,
                )
                raw = response.choices[0].message.content or ""
                return raw, parse_ai_decision(raw)
            except Exception as exc:
                last_error = str(exc)
                if attempt < attempts - 1:
                    time.sleep(self.settings.ai_retry_backoff_seconds * (2 ** attempt))
        raw = f"AI client error after {attempts} attempts: {last_error}"
        return raw, hold_decision("AI client call failed", raw)
