"""Strict declarative objective definitions; no executable admin expressions."""
import hashlib
import json
import re
from datetime import datetime, date
from zoneinfo import ZoneInfo


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def key(value):
    if type(value) is not str or not re.fullmatch(
        r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}", value
    ):
        raise ValueError("Invalid objective key")
    return value


def integer(value, maximum=2**63 - 1):
    if type(value) is not int or not 0 < value <= maximum:
        raise ValueError("Expected positive bounded integer")
    return value


def validate_schedule(schedule):
    if type(schedule) is not dict:
        raise ValueError("Invalid schedule")
    kind = schedule.get("type")
    required = {"type", "timezone"}
    if kind == "interval":
        required |= {"anchor", "seconds"}
    elif kind == "calendar":
        if not (schedule.get("dates") or schedule.get("month_days")):
            raise ValueError("Calendar requires dates or month_days")
        required |= set(schedule) & {"dates", "month_days"}
        for field in ("dates", "month_days"):
            if field in schedule and (
                type(schedule[field]) is not list or len(schedule[field]) > 3660
            ):
                raise ValueError("Calendar dates must be bounded lists")
        for value in schedule.get("dates", []):
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError("Invalid calendar date")
        for value in schedule.get("month_days", []):
            if (
                datetime.strptime("2000-" + value, "%Y-%m-%d").strftime("%m-%d")
                != value
            ):
                raise ValueError("Invalid calendar month/day")
    elif kind not in {"once", "daily", "weekly"}:
        raise ValueError("Unsupported schedule type")
    if set(schedule) != required:
        raise ValueError("Unexpected schedule fields")
    try:
        ZoneInfo(schedule["timezone"])
    except (KeyError, TypeError) as exc:
        raise ValueError("Unknown schedule timezone") from exc
    if kind == "interval":
        if not 60 <= integer(schedule["seconds"], 31536000):
            raise ValueError("Interval must be at least 60 seconds")
        if datetime.fromisoformat(schedule["anchor"]).tzinfo is None:
            raise ValueError("Interval anchor must include timezone")
    return schedule


def validate_reward(reward):
    if type(reward) is not dict:
        raise ValueError("Invalid reward")
    if reward.get("kind") == "scaled" and set(reward) == {"kind", "policy_key"}:
        key(reward["policy_key"])
    elif reward.get("kind") == "kamas" and set(reward) == {"kind", "amount"}:
        integer(reward["amount"])
    elif reward.get("kind") == "random_item" and set(reward) == {
        "kind",
        "references",
        "quantity",
    }:
        if (
            type(reward["references"]) is not list
            or not 1 <= len(reward["references"]) <= 1000
        ):
            raise ValueError("Invalid item pool")
        for ref in reward["references"]:
            integer(ref, 2**31 - 1)
        integer(reward["quantity"], 32767)
    elif (
        set(reward) == {"aeV", "ckl"}
        and type(reward["aeV"]) is int
        and reward["aeV"] in (2, 3, 5, 6)
    ):
        kind = reward["aeV"]
        if type(reward["ckl"]) is not list or len(reward["ckl"]) != (
            2 if kind == 5 else 1
        ):
            raise ValueError("Invalid native reward parameters")
        integer(reward["ckl"][0], 65535 if kind == 2 else (2**31 - 1))
        if kind == 5:
            integer(reward["ckl"][1], 32767)
    else:
        raise ValueError("Unsupported reward")
    return reward


def validate_definition(value):
    if type(value) is not dict or not {
        "key",
        "title",
        "description",
        "kind",
        "enabled",
        "objectives",
        "schedule",
        "rewards",
    } <= set(value):
        raise ValueError("Incomplete definition")
    if set(value) - {
        "key",
        "title",
        "description",
        "kind",
        "enabled",
        "objectives",
        "schedule",
        "rewards",
        "prerequisite_keys",
        "level_range",
        "scope",
    }:
        raise ValueError("Unexpected definition fields")
    value = json.loads(canonical(value))
    if type(value.get("scope", "character")) is not str or value.get(
        "scope", "character"
    ) not in {"character", "account"}:
        raise ValueError("Invalid objective scope")
    value.setdefault("scope", "account")
    key(value["key"])
    if "level_range" in value:
        band = value["level_range"]
        if (
            type(band) is not dict
            or set(band) != {"minimum", "maximum"}
            or integer(band["minimum"], 200) > integer(band["maximum"], 200)
        ):
            raise ValueError("Invalid objective level range")
    for field, size in (("title", 256), ("description", 4096)):
        if (
            type(value[field]) is not str
            or len(value[field]) > size
            or (field == "title" and not value[field])
        ):
            raise ValueError("Invalid definition text")
    if (
        value["kind"]
        not in {
            "task",
            "achievement",
            "mission",
            "daily",
            "recurring",
            "almanax",
            "pvp",
            "onboarding",
        }
        or type(value["enabled"]) is not bool
    ):
        raise ValueError("Invalid definition kind or enabled flag")
    if type(value["objectives"]) is not list or not 1 <= len(value["objectives"]) <= 32:
        raise ValueError("Expected 1 to 32 objectives")
    seen = set()
    for objective in value["objectives"]:
        if type(objective) is not dict or set(objective) != {
            "key",
            "event",
            "filters",
            "target",
        }:
            raise ValueError("Invalid objective")
        if key(objective["key"]) in seen:
            raise ValueError("Duplicate objective key")
        seen.add(objective["key"])
        key(objective["event"])
        integer(objective["target"])
        if (
            objective["event"] == "original_monster_killed"
            and "references" in objective["filters"]
        ):
            if (
                type(objective["filters"]["references"]) is not list
                or not objective["filters"]["references"]
            ):
                raise ValueError("Kill references must be a nonempty integer list")
            for ref in objective["filters"]["references"]:
                integer(ref, 2**31 - 1)
        if type(objective["filters"]) is not dict or len(objective["filters"]) > 32:
            raise ValueError("Invalid objective filters")
        if objective["event"] in {
            "account_character_level_progressed",
            "account_profession_level_progressed",
        }:
            if set(objective["filters"]) != {"minimum_level"}:
                raise ValueError(
                    "Account progression objectives require a native level threshold"
                )
            integer(objective["filters"]["minimum_level"], 1000)
        for field, expected in objective["filters"].items():
            key(field)
            values = expected if type(expected) is list else [expected]
            if not 1 <= len(values) <= 10000 or any(
                type(v) not in (str, int, bool) for v in values
            ):
                raise ValueError(
                    "Filters require scalar values or nonempty scalar lists"
                )
    if sum(o["target"] for o in value["objectives"]) > 2**31 - 1:
        raise ValueError("Aggregate native progress target exceeds signed 32-bit")
    validate_schedule(value["schedule"])
    if type(value["rewards"]) is not list or len(value["rewards"]) > 64:
        raise ValueError("Invalid rewards")
    for reward in value["rewards"]:
        validate_reward(reward)
    dependencies = value.setdefault("prerequisite_keys", [])
    if (
        type(dependencies) is not list
        or len(dependencies) > 32
        or len(set(dependencies)) != len(dependencies)
    ):
        raise ValueError("Invalid prerequisites")
    for dependency in dependencies:
        if key(dependency) == value["key"]:
            raise ValueError("Self prerequisite")
    return value


def semantic_signature(definition):
    value = validate_definition(definition)
    return hashlib.sha256(
        canonical(
            {
                k: v
                for k, v in value.items()
                if k not in {"title", "description", "enabled"}
            }
        ).encode()
    ).hexdigest()
