"""Qualified native protector speakers bound to captured exploration actors."""
import struct

from .npc_capture_contracts import authorized_identity

PROTECTOR_SPEAKER = 1
NPC_SPEAKER = 2


def speaker(row):
    """Return the exact native speaker identity, rejecting incomplete joins."""
    captured = row.get("native_capture_contract") or {}
    kind = captured.get("speaker_type", NPC_SPEAKER)
    if type(kind) is not int or kind not in (PROTECTOR_SPEAKER, NPC_SPEAKER):
        raise ValueError("Unsupported captured dialogue speaker type")
    if kind == NPC_SPEAKER:
        if (
            captured.get("speaker_id") is not None
            or row.get("native_protector_contract") is not None
        ):
            raise ValueError("Contradictory captured NPC speaker identity")
        return kind, row["actor_id"]
    contract = row.get("native_protector_contract")
    if not authorized_identity(row) or not isinstance(contract, dict):
        raise ValueError("Missing captured protector actor identity")
    keys = (
        "protector_id",
        "actor_id",
        "map_id",
        "territory_id",
        "appearance_id",
        "original_nation",
        "current_nation",
    )
    if any(type(contract.get(key)) is not int for key in keys):
        raise ValueError("Invalid captured protector contract")
    if (
        contract["actor_id"] != row["actor_id"]
        or contract["map_id"] != row["map_id"]
        or type(captured.get("speaker_id")) is not int
        or contract["protector_id"] != captured["speaker_id"]
        or not 0 < contract["protector_id"] < 2**31
        or not 0 < contract["territory_id"] < 2**31
        or not 0 < contract["appearance_id"] < 2**31
        or any(
            not 0 <= contract[key] < 2**31
            for key in ("original_nation", "current_nation")
        )
    ):
        raise ValueError("Contradictory captured protector actor identity")
    return kind, contract["protector_id"]


def record(row):
    """Native wW: ID, territory/nations and appearance/actor; optional parts absent."""
    kind, identity = speaker(row)
    if kind != PROTECTOR_SPEAKER:
        raise ValueError("NPC has no qualified protector publication")
    contract = row["native_protector_contract"]
    return struct.pack(
        ">iBiiiBiq",
        identity,
        1,
        contract["original_nation"],
        contract["current_nation"],
        contract["territory_id"],
        1,
        contract["appearance_id"],
        row["actor_id"],
    ) + bytes(11)


def records(rows):
    result, identities = [], set()
    for row in rows:
        kind, identity = speaker(row)
        if kind != PROTECTOR_SPEAKER:
            continue
        if identity in identities:
            raise ValueError("Duplicate qualified protector identity")
        identities.add(identity)
        result.append(record(row))
    return tuple(result)


def bootstrap_records(db, character):
    """Only the qualified original public scene can publish these protectors."""
    if (character["map_id"], character["instance_id"]) != (1385, 0):
        return ()
    from . import npc_world

    return npc_world.protector_records(db, 1385, 0)
