"""Native ranch menu availability and owned exit interaction authority."""
import struct

from wakfu_server.haven_ranch import MAPS, QUALIFIED_DESTINATIONS


def _objects(map_id):
    from wakfu_server import world_static

    return world_static.objects(map_id)


def config_message():
    """22318/cEp disables only installed biomes lacking qualified destinations."""
    key = b"ranch.biomes.forbidden"
    value = "|".join(
        str(biome) for biome in sorted(set(MAPS) - set(QUALIFIED_DESTINATIONS))
    ).encode("ascii")
    return (
        22318,
        struct.pack(">I", len(key)) + key + struct.pack(">I", len(value)) + value,
    )


def validate_exit(character, ranch_session, body, *, validate_lease):
    """Authorize12870/CLOSE on the current installed RanchExit, without entry rights."""
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Invalid native ranch exit request")
    identity, action, parameter = struct.unpack(">qHH", body)
    if ranch_session is None or not ranch_session.owns(character):
        raise ValueError("Ranch exit requires its live private session")
    validate_lease()
    sources = [
        row
        for row in _objects(character["map_id"])
        if row["id"] == identity and row["type"] == "RanchExit"
    ]
    if len(sources) != 1 or action != 18 or parameter != 0:
        raise ValueError("Unknown native ranch exit source or action")
    source = sources[0]
    if (
        source.get("map_id") != character["map_id"]
        or source["z"] != character["z"]
        or abs(source["x"] - character["x"]) + abs(source["y"] - character["y"]) > 1
    ):
        raise ValueError("Ranch exit is out of reach")
    return identity
