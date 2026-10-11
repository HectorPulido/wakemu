"""Current NPC eHj format11 appearance and ctE12608 world spawn.

The breed reference supplies its native NPC visual data; sN only toggles
visibility and never contains a player ProtoAppearance or arbitrary sprite ID.
"""
import struct
from functools import lru_cache
from wakfu_server.monsters import owned_instance, reference


@lru_cache(maxsize=None)
def corpse_collect_actions(monster_ref):
    """Keep native unrestricted/dead actions enabled; disable unknown criteria."""
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    catalog = native_catalog.load(DATA_ROOT / "monster-encyclopedia.json")
    for row in catalog["monsters"]:
        if row["ref"] == monster_ref:
            identities = tuple(
                sorted(
                    {
                        action["d"]
                        for action in row["collect_actions"]
                        if action["clT"].strip()
                        not in ("", 'IsDead("target")', 'not IsDead("target")')
                    }
                )
            )
            if len(identities) > 65535 or any(
                type(value) is not int or not -(2**31) <= value < 2**31
                for value in identities
            ):
                raise ValueError("Invalid native corpse collection actions")
            return identities
    raise ValueError("Corpse breed missing native collection catalog")


def world_actor(monster, *, name=None, group_id, direction=3, members=None, dead=False):
    if type(dead) is not bool:
        raise ValueError("Native death state must be explicit")
    verified = owned_instance(
        monster["ref"],
        monster["level"],
        monster["id"],
        map_id=monster["map_id"],
        x=monster["x"],
        y=monster["y"],
        z=monster["z"],
        team=monster["team"],
        instance_id=monster["instance_id"],
    )
    if monster != verified or monster["id"] >= 0:
        raise ValueError("Expected verified own negative NPC instance")
    if (
        type(group_id) is not int
        or not 0 < group_id < 2**63
        or type(direction) is not int
        or not 0 <= direction < 8
    ):
        raise ValueError("Invalid own NPC group or direction")
    if name is None:
        name = reference(monster["ref"])["name"]
    if not isinstance(name, str) or not name or len(name.encode("utf-8")) > 65535:
        raise ValueError("Invalid NPC name")
    encoded_name = name.encode("utf-8")
    # ID, IDENTITY, NAME, BREED, empty guild sections.
    out = (
        b"\x0b"
        + struct.pack(">qBqH", monster["id"], 1, -1, len(encoded_name))
        + encoded_name
        + struct.pack(">h", monster["ref"])
    )
    out += struct.pack(
        ">iihqBB",
        monster["x"],
        monster["y"],
        monster["z"],
        monster["map_id"],
        direction,
        0,
    )
    out += b"\x01" + struct.pack(
        ">hH", monster["level"], 0
    )  # sN visible; sP public characteristics.
    out += b"\x00" + struct.pack(
        ">iBBBBbB", -1, 0, int(dead), 0, 0, -1, 0
    )  # fight props empty; no fight yet.
    # Outside combat eGZ.gg is a no-op. bje.dsA and native interaction menus
    # read eHQ.DEAD (19) from rK/rN/wU world properties instead. cgN then
    # calls bje.dsq, selecting the native AnimStatiqueCadavre presentation.
    out += b"\x01\x00\x01\x13\x01" if dead else b"\x00"
    members = tuple(members) if members is not None else (monster,)
    if (
        not members
        or len(members) > 127
        or len({m["id"] for m in members}) != len(members)
        or monster not in members
    ):
        raise ValueError("Invalid own monster group membership")
    for member in members:
        actual = owned_instance(
            member["ref"],
            member["level"],
            member["id"],
            map_id=member["map_id"],
            x=member["x"],
            y=member["y"],
            z=member["z"],
            team=member["team"],
            instance_id=member["instance_id"],
        )
        if (
            member != actual
            or member["map_id"] != monster["map_id"]
            or member["instance_id"] != monster["instance_id"]
            or member["id"] >= 0
        ):
            raise ValueError("Group member is not a verified own NPC on this map")
    out += struct.pack(">qH", group_id, len(members)) + b"".join(
        struct.pack(">hh", member["ref"], member["level"]) for member in members
    )
    out += struct.pack(
        ">hh", -1, -1
    )  # sight/aggro-radius unspecified, captured native sentinels.
    disabled = corpse_collect_actions(monster["ref"]) if dead else ()
    out += struct.pack(">H", len(disabled)) + b"".join(
        struct.pack(">i", identity) for identity in disabled
    )  # sR is the native disabled collection action set, consumed by bjh.
    out += b"\x00\x00"  # current movement py absent.
    out += bytes(16)  # companion controller sL (none).
    out += bytes(2) + b"\x00"  # downscale pK0, hero qpfalse.
    return out


def spawn_monster(monster, *, group_id, name=None, direction=3):
    blob = world_actor(monster, group_id=group_id, name=name, direction=direction)
    if len(blob) > 65535:
        raise ValueError("NPC appearance too large")
    return b"\x00\x01" + struct.pack(">BqH", 1, monster["id"], len(blob)) + blob


def spawn_group(members, *, group_id, direction=3):
    """Register all owned world actors with the same full native group roster."""
    members = tuple(members)
    if not members or len(members) > 127:
        raise ValueError("Invalid owned group size")
    entries = []
    for member in members:
        blob = world_actor(
            member, group_id=group_id, direction=direction, members=members
        )
        if len(blob) > 65535:
            raise ValueError("NPC appearance too large")
        entries.append(struct.pack(">BqH", 1, member["id"], len(blob)) + blob)
    return bytes([0, len(members)]) + b"".join(entries)


def remove_message(actor_ids):
    """ctA12304 world-only removal: two false flags,u8 count,(type1,i64 ID)."""
    actor_ids = tuple(actor_ids)
    if not actor_ids or len(actor_ids) > 255 or len(set(actor_ids)) != len(actor_ids):
        raise ValueError("Invalid NPC removal list")
    if any(
        type(identity) is not int or not -(2**63) <= identity < 0
        for identity in actor_ids
    ):
        raise ValueError("Expected owned negative NPC identities")
    return 12304, bytes([0, 0, len(actor_ids)]) + b"".join(
        struct.pack(">Bq", 1, identity) for identity in actor_ids
    )
