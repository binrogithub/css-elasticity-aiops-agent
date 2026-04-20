"""Cooldown helpers."""

from datetime import datetime, timezone


def in_cooldown(cooldown_until: datetime | None) -> bool:
    return bool(cooldown_until and datetime.now(timezone.utc) < cooldown_until)


def cooldown_status(cooldown_until: datetime | None) -> str:
    if not in_cooldown(cooldown_until):
        return "not_in_cooldown"
    remaining = int((cooldown_until - datetime.now(timezone.utc)).total_seconds())
    return f"in_cooldown_remaining_seconds={remaining}"
