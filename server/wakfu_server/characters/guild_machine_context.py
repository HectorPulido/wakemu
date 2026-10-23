"""Authorize native guild identity operations at original machine use cells."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

SOURCE_SHA256 = "c08625b34e9fe635b87a91067ece95670046fb60d9459f38a7a74aea62264453"
PRIMARY_OPCODES = frozenset((13757, 12575, 12937))


@lru_cache(maxsize=1)
def machines():
    raw = Path(__file__).with_name("native_guild_machines.json").read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Conflicting native guild machine authority")
    return tuple(json.loads(raw)["machines"])


def validate(character, objects):
    """Resolve real installed identity and exact standing cell, not a radius.

    Position comes from the current World identity. The native request contains
    no machine or position fields. Payment separately applies the shared idle
    fence inside its transaction; this function never grants guild membership.
    """
    if character.get("instance_id", 0) != 0:
        raise ValueError("Guild identity operations require an ordinary world machine")
    fields = ("map_id", "x", "y", "z")
    if any(type(character.get(key)) is not int for key in fields):
        raise ValueError("Missing live native guild machine position")
    standing = [character[key] for key in ("x", "y", "z")]
    candidates = [
        row
        for row in machines()
        if row["map_id"] == character["map_id"] and row["use_cell"] == standing
    ]
    if len(candidates) != 1:
        raise ValueError("Stand at the native guild machine interaction cell")
    machine = candidates[0]
    installed = [
        row
        for row in objects
        if row.get("id") == machine["object_id"]
        and row.get("type") == "GuildMachine"
        and row.get("map_id") == machine["map_id"]
    ]
    if (
        len(installed) != 1
        or [installed[0].get(key) for key in ("x", "y", "z")]
        != machine["object_position"]
    ):
        raise ValueError("The original native guild machine is unavailable")
    return dict(
        map_id=machine["map_id"],
        object_id=machine["object_id"],
        use_cell=tuple(machine["use_cell"]),
    )
