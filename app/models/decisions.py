"""AI decision models and parser."""

import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator


ElasticityDecision = Literal["scale_out", "scale_in", "change_flavor", "hold"]
NodeType = Literal["ess", "ess-client", "ess-master"]


class AIDecision(BaseModel):
    decision: ElasticityDecision = "hold"
    node_type: Optional[NodeType] = None
    delta: int = 0
    target_flavor_id: Optional[str] = None
    reason: str = "No decision"
    cooldown_minutes: int = 30
    expected_duration_minutes: int = 30
    valid: bool = True
    validation_message: str = "ok"

    @field_validator("delta", "cooldown_minutes", "expected_duration_minutes")
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("value must be non-negative")
        return value


def hold_decision(reason: str, raw_message: Optional[str] = None) -> AIDecision:
    suffix = f"; raw={raw_message}" if raw_message else ""
    return AIDecision(
        decision="hold",
        node_type=None,
        delta=0,
        target_flavor_id=None,
        reason=f"{reason}{suffix}",
        valid=False,
        validation_message=reason,
    )


def _normalize_ai_json(raw_response: str) -> str:
    text = raw_response.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def parse_ai_decision(raw_response: str) -> AIDecision:
    normalized = _normalize_ai_json(raw_response)
    try:
        data = json.loads(normalized)
    except json.JSONDecodeError:
        return hold_decision("AI response was not valid JSON", raw_response[:500])

    try:
        parsed = AIDecision.model_validate(data)
    except ValidationError as exc:
        return hold_decision(f"AI response failed validation: {exc.errors()}", raw_response[:500])

    if parsed.decision == "hold":
        parsed.delta = 0
        parsed.node_type = None
        parsed.target_flavor_id = None
    if parsed.decision in {"scale_out", "scale_in"} and parsed.node_type is None:
        return hold_decision("AI response missing node_type for scaling decision", raw_response[:500])
    if parsed.decision == "change_flavor" and (parsed.node_type is None or not parsed.target_flavor_id):
        return hold_decision("AI response missing node_type or target_flavor_id for flavor change", raw_response[:500])
    return parsed
