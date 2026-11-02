"""Opt-in runtime bridge for deferred first choice; private integration candidate."""
import struct
from wakfu_server import dungeon_rotation


def enabled(config):
    return bool(config["topology"].get("excavation_access"))


def hydrate(db, instance_id, config):
    """Run after the original pinned configuration/hash has been validated."""
    if not enabled(config):
        return config
    dungeon_rotation.validate(config)
    run = db.execute(
        "SELECT catalog_hash,branch_key FROM dungeon_room_runs WHERE instance_id=%s",
        (instance_id,),
    ).fetchone()
    state = db.execute(
        "SELECT * FROM dungeon_excavation_runs WHERE instance_id=%s", (instance_id,)
    ).fetchone()
    if state is None or state["selected_source_id"] is None:
        if run is not None and run["branch_key"] is not None:
            raise ValueError("Pending excavation has an inconsistent durable choice")
        return dict(
            config,
            topology=dict(
                config["topology"],
                _rotation_pending=True,
                _rotation_key_character_id=None
                if state is None
                else state["key_character_id"],
            ),
        )
    if (
        run is None
        or state["catalog_hash"] != run["catalog_hash"]
        or run["branch_key"] != str(state["selected_source_id"])
    ):
        raise ValueError("Selected excavation differs from its pinned run")
    from wakfu_server.dungeon_rotation_cache import project_pinned

    return project_pinned(config, state["selected_source_id"])


def defer_spawn(config):
    return enabled(config) and config["topology"].get("_rotation_pending") is True


def blocked_gate_ids(topology):
    return (
        frozenset(g["source_id"] for g in topology.get("physical_doors", ()))
        if topology.get("_rotation_pending")
        else frozenset()
    )


def pending_gate_packets(config, *, character_id, key_character_id):
    """Close all gates; only the real key carrier receives native open actions.

    All peers still share one collision/progression authority. Usability only
    advertises the original Door action, and never authorizes the request.
    """
    if not defer_spawn(config):
        return ()
    from wakfu_server.dungeon_object_states import state_payload

    selectors = {s["source_id"] for s in dungeon_rotation.validate(config)["selectors"]}
    packets = []
    for gate in config["topology"]["physical_doors"]:
        usable = (
            type(key_character_id) is int
            and key_character_id > 0
            and character_id == key_character_id
            and gate["source_id"] in selectors
        )
        payload = state_payload(visible=True, usable=usable, state_id=1)
        packets.append(
            (12344, struct.pack(">qH", gate["source_id"], len(payload)) + payload)
        )
    return tuple(packets)


def flow_packets(
    topology,
    *,
    map_id,
    instance_id,
    unlocked_room,
    completed,
    recipient_character_id=None
):
    from wakfu_server import dungeon_physical_doors

    ordinary = dungeon_physical_doors.packets(
        topology,
        map_id=map_id,
        instance_id=instance_id,
        unlocked_room=unlocked_room,
        completed=completed,
    )
    if topology.get("_rotation_pending"):
        gate_ids = {g["source_id"] for g in topology["physical_doors"]}
        ordinary = tuple(
            p for p in ordinary if struct.unpack_from(">q", p[1])[0] not in gate_ids
        )
        # Already validated at pinned-config admission; no additional native
        # source query or geometry projection for packet construction.
        config = dict(topology=topology, compiled_plan=dict(rooms=topology["rooms"]))
        ordinary += pending_gate_packets(
            config,
            character_id=recipient_character_id,
            key_character_id=topology.get("_rotation_key_character_id"),
        )
    for held in topology.get("held_optional_sources", ()):
        payload = bytearray.fromhex(held["baseline_state_payload_hex"])
        if len(payload) != 19 or payload[:7] != bytes.fromhex("01020000000602"):
            raise ValueError("Unknown native optional source baseline framing")
        payload[10] = 0  # Disable use; preserve original visibility/auxiliary flags.
        ordinary += (
            (12344, struct.pack(">qH", held["source_id"], len(payload)) + payload),
        )
    return ordinary
