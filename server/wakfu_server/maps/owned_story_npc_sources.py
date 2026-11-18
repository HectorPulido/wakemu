"""Finite native NPC action overlays for authenticated private story actors.

An overlay adds an originally shipped action-bearing prototype to a caller's
local render catalog. It never changes the global conversational catalog or
attaches actions to an originally inert prototype.
"""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path


def digest(value):
    return sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@lru_cache(maxsize=16)
def _source(filename, pin):
    if Path(filename).name != filename:
        raise ValueError("Owned NPC source escapes its reviewed directory")
    raw = (Path(__file__).with_name("owned_story_npc_profiles") / filename).read_bytes()
    if sha256(raw).hexdigest() != pin:
        raise ValueError("Owned NPC original action source changed")
    value = json.loads(raw)
    if value.get("schema") != "owned-story-native-npc-actions-v1" or not value.get(
        "provenance"
    ):
        raise ValueError("Missing owned NPC original source evidence")
    from wakfu_server import monsters

    seen = set()
    for row in value["speakers"]:
        if (
            set(row) != {"ref", "min_level", "max_level", "visual_id", "actions"}
            or row["ref"] in seen
        ):
            raise ValueError("Invalid owned native NPC speaker")
        seen.add(row["ref"])
        original = monsters.reference(row["ref"])
        if any(
            row[key] != original[native]
            for key, native in (
                ("min_level", "min_level"),
                ("max_level", "max_level"),
                ("visual_id", "sprite_id"),
            )
        ):
            raise ValueError("Owned native NPC appearance differs from its prototype")
        if not row["actions"] or any(
            set(a) != {"id", "type", "criteria"}
            or type(a["id"]) is not int
            or a["id"] <= 0
            or a["type"] != 1
            or type(a["criteria"]) is not str
            for a in row["actions"]
        ):
            raise ValueError(
                "Owned native NPC overlay supports exact original type1 actions only"
            )
    return value


def catalog(profile, base=None):
    from wakfu_server import npc_dialogue

    base = npc_dialogue.catalog() if base is None else base
    pin = profile.get("native_action_source")
    if pin is None:
        return base
    if set(pin) != {"path", "sha256"}:
        raise ValueError("Malformed owned native NPC action pin")
    source = _source(pin["path"], pin["sha256"])
    needed = {row["reference_id"] for row in profile["npcs"]}
    if {row["ref"] for row in source["speakers"]} != needed:
        raise ValueError("Owned NPC source does not match its finite templates")
    existing = {row["ref"]: row for row in base["speakers"]}
    speakers = list(base["speakers"])
    for row in source["speakers"]:
        if row["ref"] in existing and row != existing[row["ref"]]:
            raise ValueError(
                "Owned NPC overlay cannot replace an existing native speaker"
            )
        if row["ref"] not in existing:
            speakers.append(row)
    return dict(base, speakers=speakers)
