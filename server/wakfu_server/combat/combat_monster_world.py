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


def _native_actor_fields(monster):
    """Separate the exact trusted interaction marker from native actor fields.

    The marker prevents combat admission in the group registry. It is server
    metadata, not an extra native characteristic or a relaxed actor descriptor.
    """
    if "environmental_world_action_only" not in monster:
        return monster
    if monster["environmental_world_action_only"] is not True:
        raise ValueError("Invalid world-action-only NPC marker")
    return {
        key: value
        for key, value in monster.items()
        if key != "environmental_world_action_only"
    }


def world_actor(
    monster,
    *,
    name=None,
    group_id,
    direction=3,
    members=None,
    dead=False,
    summon_identity=False,
    companion_source=None,
    world_context=None,
    fighter=None,
    fight=None,
):
    """Encode eHj format-11 appearance for an owned world actor.

    ``summon_identity`` is reserved for the reconnect snapshot bridge: it
    permits the positive native fighter UID while keeping the exact NPC bje
    appearance. The following saved 307 descriptor applies summon authority.
    """
    if type(dead) is not bool:
        raise ValueError("Native death state must be explicit")
    if (fighter is None) != (fight is None):
        raise ValueError("NPC fight appearance requires its actual fighter and fight")
    fight_id, obstacle_id = -1, -1
    if fighter is not None:
        fight_id = getattr(fight, "id", None)
        obstacle_id = getattr(fighter, "native_obstacle_id", None)
        if (
            type(fight_id) is not int
            or not 0 < fight_id < 2**31
            or getattr(fighter, "id", None) != monster["id"]
            or getattr(fight, "actors", {}).get(monster["id"]) is not fighter
            or type(obstacle_id) is not int
            or not 0 <= obstacle_id <= 126
            or dead
            or summon_identity
            or not fight._in_play(fighter)
        ):
            raise ValueError("NPC fight appearance lacks an admitted physical fighter")
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
    if companion_source is not None:
        from .combat_companions import COMPANION_BREEDS

        if (
            companion_source.get("id") != monster["id"]
            or companion_source.get("ref") != monster["ref"]
            or monster["ref"] not in COMPANION_BREEDS
            or companion_source.get("native_actor_type") != 5
            or type(companion_source.get("owner_character_id")) is not int
            or companion_source["owner_character_id"] <= 0
        ):
            raise ValueError("Missing companion world ownership")
    if _native_actor_fields(monster) != verified or (
        monster["id"] >= 0 and not summon_identity and companion_source is None
    ):
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
        + struct.pack(
            ">qBqH",
            monster["id"],
            5 if companion_source is not None else 1,
            companion_source["account_id"] if companion_source is not None else -1,
            len(encoded_name),
        )
        + encoded_name
        + struct.pack(">h", monster["ref"])
    )
    out += struct.pack(
        ">iihqBB",
        monster["x"],
        monster["y"],
        monster["z"],
        _world_position_identity(monster, world_context),
        direction,
        0,
    )
    out += b"\x01" + struct.pack(
        ">hH", monster["level"], 0
    )  # sN visible; sP public characteristics.
    # aVH admits an existing world NPC BEFORE applying its format2 snapshot.
    # Supply the owned byte here so client buH.x can call QI.i while admitting
    # it. Otherwise big.doV rejects a slot still held by an AnimMort corpse.
    # QI.i replaces the pointer; the old corpse's later QI.g cannot remove it.
    out += b"\x00" + struct.pack(
        ">iBBBBbB", fight_id, 0, int(dead), 0, 0, obstacle_id, 0
    )
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
            _native_actor_fields(member) != actual
            or member["map_id"] != monster["map_id"]
            or member["instance_id"] != monster["instance_id"]
            or (member["id"] >= 0 and not summon_identity and companion_source is None)
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
    # sL.ZF supplies bje.ika (owner), sL.ZG supplies bje.ikb (collection ID).
    out += (
        bytes(16)
        if companion_source is None
        else struct.pack(
            ">qq", companion_source["owner_character_id"], companion_source["id"]
        )
    )
    out += bytes(2) + b"\x00"  # downscale pK0, hero qpfalse.
    return out


def spawn_monster(
    monster,
    *,
    group_id,
    name=None,
    direction=3,
    summon_identity=False,
    world_context=None,
    fighter=None,
    fight=None,
):
    blob = world_actor(
        monster,
        group_id=group_id,
        name=name,
        direction=direction,
        summon_identity=summon_identity,
        world_context=world_context,
        fighter=fighter,
        fight=fight,
    )
    if len(blob) > 65535:
        raise ValueError("NPC appearance too large")
    return b"\x00\x01" + struct.pack(">BqH", 1, monster["id"], len(blob)) + blob


def spawn_group(members, *, group_id, direction=3, world_context=None):
    """Publish eligible ordinary actors with one consistent native roster."""
    members = tuple(members)
    if not members or len(members) > 127:
        raise ValueError("Invalid owned group size")
    entries = []
    for member in members:
        blob = world_actor(
            member,
            group_id=group_id,
            direction=direction,
            members=members,
            world_context=world_context,
        )
        if len(blob) > 65535:
            raise ValueError("NPC appearance too large")
        entries.append(struct.pack(">BqH", 1, member["id"], len(blob)) + blob)
    from .monster_minigame_policy import ordinary_group_members

    # Validate the complete original roster above, including excluded members.
    # Ecological publications may supply durable legacy rows directly, bypassing
    # available() projections. Keep private encounter and summon paths intact.
    eligible = ordinary_group_members(members, instance_id=members[0]["instance_id"])
    if eligible != members:
        if not eligible:
            # Original ctE.dp reads unsigned count0 and returns true; no actors
            # are admitted. An originally empty/invalid roster still fails above.
            return b"\x00\x00"
        entries = []
        for member in eligible:
            blob = world_actor(
                member,
                group_id=group_id,
                direction=direction,
                members=eligible,
                world_context=world_context,
            )
            if len(blob) > 65535:
                raise ValueError("NPC appearance too large")
            entries.append(struct.pack(">BqH", 1, member["id"], len(blob)) + blob)
        members = eligible
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


def _world_position_identity(monster, world_context):
    from wakfu_server.guild_haven_world import world_identity

    if world_context is None:
        return world_identity(monster)
    if not isinstance(world_context, dict) or any(
        world_context.get(k) != monster.get(k) for k in ("map_id", "instance_id")
    ):
        raise ValueError("NPC position belongs to a different world scope")
    return world_identity(world_context)
