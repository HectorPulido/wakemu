"""Strict server-mode evaluation for the native dungeon criterion subset.

The client exposes a global server-group key `server.group.isneo`, defaulting
to false. The criterion visitor itself is not present in the available client
decompilation, so this module intentionally supports only the two exact
expressions used by the configured Jalató routes.
"""
from __future__ import annotations


SETTING = "dungeon_server_mode"
VERSION = 1


def is_neo_server(store):
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name=%s", (SETTING,)
        ).fetchone()
    if row is None:
        raise ValueError("Dungeon server mode is not configured")
    value = row["value"]
    if (
        not isinstance(value, dict)
        or type(value.get("version")) is not int
        or value["version"] != VERSION
        or type(value.get("is_neo_server")) is not bool
        or set(value) != {"version", "is_neo_server"}
    ):
        raise ValueError("Dungeon server mode configuration is invalid")
    return value["is_neo_server"]


def evaluate(store, criterion):
    """Evaluate only the exact native mode predicates used by dungeon routes."""
    mode = is_neo_server(store)
    if criterion == "IsNeoServer()":
        return mode
    if criterion == "not IsNeoServer()":
        return not mode
    raise ValueError("Unsupported dungeon criterion")
