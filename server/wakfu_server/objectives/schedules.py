"""Timezone-aware recurrence evaluated against the authoritative event time."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "America/Bogota"


def period_key(schedule, occurred_at):
    if occurred_at.tzinfo is None:
        raise ValueError("Event timestamp must include timezone")
    local = occurred_at.astimezone(ZoneInfo(schedule["timezone"]))
    kind = schedule["type"]
    if kind == "once":
        return "once"
    if kind == "daily":
        return local.date().isoformat()
    if kind == "weekly":
        return (local.date() - timedelta(days=local.weekday())).isoformat()
    if kind == "calendar":
        if local.date().isoformat() not in schedule.get("dates", []) and local.strftime(
            "%m-%d"
        ) not in schedule.get("month_days", []):
            return None
        return local.date().isoformat()
    if kind == "interval":
        anchor = datetime.fromisoformat(schedule["anchor"])
        elapsed = (occurred_at - anchor).total_seconds()
        return None if elapsed < 0 else str(int(elapsed // schedule["seconds"]))
    raise ValueError("Unsupported schedule")
