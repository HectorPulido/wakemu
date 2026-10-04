"""Verified local zaap routes; no guessed cross-map destinations."""
from .paths import DATA_ROOT
import json
import struct
from pathlib import Path
from protocol_codec import decode_body
from wakfu_server import wire
from wakfu_server.haven_bag import map_transition

CATALOG = json.loads((DATA_ROOT / "world-maps.json").read_text())


def resolve(character, body):
    request = decode_body("out", 12296, body)
    if request["flag"] or request["iTS"] != 2 or character["instance_id"] != 0:
        raise ValueError("Unsupported transport mode")
    for route in CATALOG["routes"]:
        if (
            route["source_map"],
            route["interactive_element_id"],
            route["destination_id"],
        ) != (
            character["map_id"],
            request["interactive_element_id"],
            request["destination_id"],
        ):
            continue
        origin = route["source_position"]
        if (
            abs(character["x"] - origin["x"]) + abs(character["y"] - origin["y"]) > 3
            or abs(character["z"] - origin["z"]) > 1
        ):
            raise ValueError("Character is too far from the zaap")
        return route
    raise ValueError("Unknown local transport route")


def bootstrap(character, route):
    if (
        character["map_id"] != route["destination"]["map_id"]
        or character["instance_id"] != 0
    ):
        raise ValueError("Transport bootstrap does not match persisted destination")
    yield 13256, b""
    for packet in route["packets"]:
        body = bytes.fromhex(packet["body_hex"])
        if packet["opcode"] == 13974:
            body = map_transition(body, character, character["map_id"])
        else:
            body = wire.identity(body, character["account_id"], character)
        yield packet["opcode"], body
    yield 12318, struct.pack(">ii", character["x"], character["y"])


def for_map(map_id):
    return next(
        (
            route
            for route in CATALOG["routes"]
            if route["destination"]["map_id"] == map_id
        ),
        None,
    )
