"""Qualify a virtual quest branch over an unchanged captured dialogue actor.

The overlay does not publish, move or duplicate the physical NPC. Its root may
differ from the captured default, while physical identity and source actions
remain pinned to the enabled database row and native dialogue catalogue.
"""

from wakfu_server import npc_dialogue
from wakfu_server.achievements.conversation import _digest


PHYSICAL_FIELDS = (
    "actor_id",
    "reference_id",
    "map_id",
    "instance_id",
    "x",
    "y",
    "z",
    "direction",
    "interaction_range",
)


def _actions(value):
    if (
        not isinstance(value, list)
        or not value
        or any(type(identity) is not int or identity <= 0 for identity in value)
        or len(set(value)) != len(value)
    ):
        raise ValueError("Invalid existing dialogue actor actions")
    return set(value)


def validate(db, item):
    """Return the actual source row; never mutate it or accept a changed pin."""
    if not isinstance(item, dict) or not isinstance(item.get("row"), dict):
        raise ValueError("Missing existing dialogue actor overlay")
    row = item["row"]
    proof = item.get("existing_dialogue_actor")
    if (
        not isinstance(proof, dict)
        or set(proof) != {"source_sha256", "quest_ids", "evidence"}
        or not isinstance(proof["source_sha256"], str)
        or len(proof["source_sha256"]) != 64
        or any(char not in "0123456789abcdef" for char in proof["source_sha256"])
        or not isinstance(proof["quest_ids"], list)
        or not proof["quest_ids"]
        or any(
            type(identity) is not int or identity <= 0
            for identity in proof["quest_ids"]
        )
        or len(set(proof["quest_ids"])) != len(proof["quest_ids"])
        or not isinstance(proof["evidence"], str)
        or not proof["evidence"].strip()
        or any(type(row.get(key)) is not int for key in PHYSICAL_FIELDS)
        or row["actor_id"] >= 0
        or type(row.get("dialogue_root")) is not int
        or row["dialogue_root"] <= 0
    ):
        raise ValueError("Malformed existing dialogue actor overlay proof")
    requested_actions = _actions(row.get("action_ids"))
    actual = db.execute(
        "SELECT * FROM world_dialogue_npcs WHERE actor_id=%s AND enabled FOR SHARE",
        (row["actor_id"],),
    ).fetchone()
    if (
        actual is None
        or actual.get("enabled") is not True
        or type(actual.get("native_capture_id")) is not int
        or actual["native_capture_id"] != row["actor_id"]
        or actual.get("native_publication_authorized") is not True
        or any(
            type(actual.get(key)) is not int or actual[key] != row[key]
            for key in PHYSICAL_FIELDS
        )
    ):
        raise ValueError("Captured dialogue actor is unavailable or changed")
    try:
        matches = _digest(dict(actual)) == proof["source_sha256"]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Existing dialogue actor source is not canonical JSON"
        ) from exc
    if not matches:
        raise ValueError("Existing dialogue actor source attestation changed")
    source_actions = _actions(actual.get("action_ids"))
    if not requested_actions <= source_actions:
        raise ValueError("Dialogue overlay introduces an unapproved physical action")
    native = npc_dialogue.catalog()
    speakers = [
        speaker
        for speaker in native["speakers"]
        if speaker["ref"] == actual["reference_id"]
    ]
    if len(speakers) != 1:
        raise ValueError("Existing dialogue actor lacks its native speaker")
    native_actions = {
        action["id"]
        for action in speakers[0]["actions"]
        if type(action.get("id")) is int and action["id"] > 0
    }
    if not source_actions <= native_actions:
        raise ValueError("Captured dialogue actions differ from the native speaker")
    roots = native.get("node_index")
    if roots is None:
        roots = {node["id"]: node for node in native["nodes"]}
    if row["dialogue_root"] not in roots:
        raise ValueError("Dialogue overlay lacks its native root")
    return actual
