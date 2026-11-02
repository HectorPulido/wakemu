"""Native side-floor permissions derived only from an owned optional vote view."""
import struct


def rule_view(topology):
    binding = topology.get("optional_vote_access")
    view = topology.get("_optional_vote_state")
    if binding is None:
        return None, None
    from wakfu_server.dungeon_optional_votes import rules, digest

    matches = [r for r in rules() if r["key"] == binding.get("rule_key")]
    if len(matches) != 1 or digest(matches[0]) != binding.get("rule_sha256"):
        raise ValueError("Optional vote terrain contract changed")
    if view is None:
        view = dict(checkpoint=False, winner=None, rule_sha256=binding["rule_sha256"])
    if (
        view.get("catalog_hash", binding.get("plan_sha256"))
        != binding.get("plan_sha256")
        or view.get("rule_sha256") != binding["rule_sha256"]
        or view.get("winner") not in (None, "archimonster", "treasure")
    ):
        raise ValueError("Optional gate view is not qualified")
    return matches[0], view


def extra_cells(topology):
    rule, view = rule_view(topology)
    if rule is None or view.get("checkpoint") is not True:
        return frozenset()
    cells = set(map(tuple, rule["council_cells"]))
    if view["winner"] is not None:
        branch = rule["branches"][view["winner"]]
        cells.update(map(tuple, branch["cells"]))
        cells.add(tuple(branch["door_position"]))
    return frozenset(cells)


def unlocked_transports(topology):
    rule, view = rule_view(topology)
    return (
        frozenset()
        if rule is None or view.get("checkpoint") is not True
        else frozenset(r["source_id"] for r in rule["transports"])
    )


def blocked_gate_cells(topology):
    rule, view = rule_view(topology)
    if rule is None:
        return frozenset()
    winner = view["winner"] if view.get("checkpoint") is True else None
    return frozenset(
        tuple(branch["door_position"])
        for name, branch in rule["branches"].items()
        if name != winner
    )


def optional_room_allowed(topology, order):
    rule, view = rule_view(topology)
    if (
        rule is None
        or view.get("checkpoint") is not True
        or view["winner"] != "archimonster"
    ):
        return False
    source = rule["branches"]["archimonster"]["optional_source_order"]
    return any(
        r["order"] == order and r["source_order"] == source
        for r in topology["optional_room_policy"]["optional_rooms"]
    )


def gate_packets(topology):
    rule, view = rule_view(topology)
    if rule is None:
        return ()
    from wakfu_server.dungeon_object_states import state_payload

    result = []
    for name, branch in rule["branches"].items():
        opened = view.get("checkpoint") is True and view["winner"] == name
        payload = state_payload(
            visible=not opened, usable=False, state_id=0 if opened else 1
        )
        result.append(
            (12344, struct.pack(">qH", branch["door_id"], len(payload)) + payload)
        )
    return tuple(result)


def resolve_transport(topology, character, body, *, source_allowed):
    if type(body) is not bytes or len(body) != 17:
        return None
    source_id, destination_id, flag, mode = struct.unpack(">qiBi", body)
    rule, view = rule_view(topology)
    if rule is None or source_id not in {r["source_id"] for r in rule["transports"]}:
        return None
    if (
        flag != 0
        or mode != 2
        or view.get("checkpoint") is not True
        or character.get("instance_id") != view.get("instance_id")
    ):
        raise ValueError("Native council transport has no committed checkpoint")
    from wakfu_server import generic_transports

    source = generic_transports.source(character["map_id"], source_id)
    binding = next(r for r in rule["transports"] if r["source_id"] == source_id)
    if source is None or source_allowed(character, source) is not True:
        raise ValueError("Council portal requires its native owned approach")
    destination = next(
        (d for d in source["destinations"] if d["destination_id"] == destination_id),
        None,
    )
    if (
        destination is None
        or destination_id != binding["destination_id"]
        or character["map_id"] != rule["map_id"]
        or destination["map_id"] != rule["map_id"]
        or [destination[k] for k in ("x", "y", "z")] != binding["destination_position"]
        or not destination["native_altitude_walkable"]
        or destination["criterion"].strip()
        or destination["cyZ"] >= 0
        or destination["cyX"] != 0
        or destination.get("cyW", 0) != 0
        or destination.get("item_reference", 0) != 0
    ):
        raise ValueError("Original council portal binding changed")
    return dict(destination)
