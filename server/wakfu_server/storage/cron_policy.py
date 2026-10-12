"""Database-only operational policy for the Redis world scheduler."""
from copy import deepcopy
import math
from urllib.parse import urlsplit

SETTING_NAME = "cron_scheduler_policy"


def validate_policy(value):
    if not isinstance(value, dict) or not isinstance(value.get("tasks"), dict):
        raise ValueError("Cron policy must contain a tasks object")
    value = deepcopy(value)
    poll = value.setdefault("poll_seconds", 1)
    _positive_number(poll, "poll_seconds")
    for name, task in value["tasks"].items():
        if not isinstance(name, str) or not name or not isinstance(task, dict):
            raise ValueError("Cron tasks must have nonempty names and object policies")
        if "enabled" in task and not isinstance(task["enabled"], bool):
            raise ValueError("Cron enabled must be boolean")
        _positive_number(task.get("interval"), "interval")
        for field in (
            "lease_seconds",
            "retry_seconds",
            "retention_seconds",
            "timeout_seconds",
        ):
            if field in task:
                _positive_number(task[field], field)
        attempts = task.get("max_attempts", 3)
        if type(attempts) is not int or attempts < 1:
            raise ValueError("Cron max_attempts must be a positive integer")
        for field in ("url", "poll_url"):
            if field not in task and field == "poll_url":
                continue
            url = task.get(field)
            if not isinstance(url, str):
                raise ValueError("Cron task URL must be an HTTP URL")
            parsed = urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError("Cron task URL must be an HTTP URL")
        if not isinstance(task.get("body", {}), dict):
            raise ValueError("Cron task body must be an object")
    return value


def _positive_number(value, field):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("Cron " + field + " must be finite and positive")


def load_policy(database):
    with database.connection() as connection:
        row = connection.execute(
            "SELECT value FROM settings WHERE name = %s", (SETTING_NAME,)
        ).fetchone()
    if row is None:
        raise ValueError("Missing database setting: " + SETTING_NAME)
    return validate_policy(row["value"])
