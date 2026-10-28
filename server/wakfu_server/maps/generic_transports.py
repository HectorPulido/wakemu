"""Native bEk/aNE destinations for free, unconditional world teleporters.

This resolves data, not an execution transaction. The caller validates proximity
against its authoritative interaction/path state and commits the destination.
Unsupported criteria, item/kama costs and special instances remain explicit.
"""
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
import json
import struct
from pathlib import Path

_CATALOG = protocol_catalog.load(DATA_ROOT / "native-generic-teleporters.json")
_SOURCES = {(row["map_id"], row["id"]): row for row in _CATALOG}


def resolve(
    character,
    body,
    *,
    source_allowed,
    criterion_evaluator=None,
    allow_item_payment=False
):
    """Resolve cpJ12296; source_allowed(character,source) is mandatory.

    No arbitrary interaction radius is introduced here. The callback must check
    owned authoritative proximity/approach state before any travel is committed.
    """
    if len(body) != 17:
        raise ValueError("Invalid native teleporter request length")
    identity, destination_id, flag, mode = struct.unpack(">qiBi", body)
    if flag != 0 or mode != 2 or character.get("instance_id", 0) != 0:
        raise ValueError("Unsupported native teleporter mode or instance")
    source = _SOURCES.get((character["map_id"], identity))
    if source is None:
        raise ValueError("Unknown native teleporter in current map")
    if not source_allowed(character, dict(source)):
        raise ValueError("Authoritative source interaction not allowed")
    destination = next(
        (d for d in source["destinations"] if d["destination_id"] == destination_id),
        None,
    )
    if destination is None:
        raise ValueError("Unknown native teleporter destination")
    from wakfu_server import exploration_secrets, exploration_transport, travel_mists

    # Unlock only reviewed exploration travel; retain the immutable catalog so
    # unrelated story transports keep their native access rules and prices.
    mist = travel_mists.recognizes(source)
    mission_free = mist or exploration_transport.projected_access(source, character)
    criterion = "" if mission_free else destination["criterion"]
    item_price = 0 if mist else destination["cyW"]
    if item_price > 0 and exploration_secrets.projected_transport_access(
        character, destination["item_reference"], item_price
    ):
        item_price = 0
    if criterion.strip():
        if criterion_evaluator is None:
            raise ValueError("Unsupported native teleporter access criterion")
        if criterion_evaluator(criterion, character, destination["map_id"]) is not True:
            raise ValueError("Native teleporter access criterion is not met")
    if item_price > 0 and destination["item_reference"] > 0:
        if allow_item_payment is not True:
            raise ValueError("Native teleporter requires item transaction")
    if destination["cyX"] != 0:
        raise ValueError("Native teleporter requires kama transaction")
    # cvd/cyY map to flF.gev/gew: cXI.bxQ uses them only to hide
    # menu entries when criteria/dungeon checks fail. cof/cnb has no
    # observed caller and must not be invented as an instance flag.
    if destination["cyZ"] >= 0:
        raise ValueError("Unsupported native special teleporter context")
    if not destination["native_altitude_walkable"]:
        raise ValueError("Native destination altitude is not verified walkable")
    result = {
        "source_map": source["map_id"],
        "interactive_element_id": identity,
        "destination_id": destination_id,
        "source_position": {axis: int(source[axis]) for axis in ("x", "y", "z")},
        "destination": {
            **{axis: destination[axis] for axis in ("map_id", "x", "y", "z")},
            "instance_id": 0,
        },
        "direction": destination["direction"],
        "native_definition_id": source["definition_id"],
        "criterion": criterion,
    }
    if item_price > 0 and destination["item_reference"] > 0:
        result["item_payment"] = dict(
            reference=destination["item_reference"], quantity=item_price
        )
    return result


def source(map_id, identity):
    row = _SOURCES.get((map_id, identity))
    return (
        None
        if row is None
        else {**row, "destinations": [dict(d) for d in row["destinations"]]}
    )
