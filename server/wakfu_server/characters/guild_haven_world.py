"""Durable guild-owned private world scopes under explicit Wakemu assignment.

The native guild/world identity and rank bit are real authorities. Assigning a
map template to a private instance is an explicit server policy, not a recovered
Haven World auction, map generator, entry protocol, or initial ecology producer.
"""
from wakfu_server.guild_native_validators import permission_mask
from psycopg.types.json import Jsonb
from dataclasses import dataclass


@dataclass(frozen=True)
class _OwnedHavenWorldPosition:
    guild_id: int
    map_id: int
    instance_id: int
    guild_name: str = ""
    guild_blazon: int = 0


def world_identity(character):
    """Use only the signed identity derived from an owned SQL binding."""
    map_id = character.get("map_id")
    if type(map_id) is not int or not 0 <= map_id < 2**63:
        raise ValueError("Invalid native world map identity")
    if "native_world_id" not in character:
        return map_id
    authority = character.get("_native_haven_world_position")
    value = character["native_world_id"]
    if (
        not isinstance(authority, _OwnedHavenWorldPosition)
        or type(value) is not int
        or value != -authority.guild_id
        or authority.guild_id <= 0
        or value < -(1 << 63)
        or character.get("map_id") != authority.map_id
        or character.get("instance_id") != authority.instance_id
        or authority.instance_id <= 0
    ):
        raise ValueError("Unverified private native world position")
    return value


def authorize(db, store, account_id, generation, character_id, *, context):
    from wakfu_server.guild_service import GuildService

    if (
        not isinstance(context, dict)
        or any(
            type(context.get(k)) is not int
            for k in ("map_id", "instance_id", "native_world_id", "x", "y", "z")
        )
        or context["instance_id"] <= 0
    ):
        raise ValueError("A current private Haven World context is required")
    service = GuildService(store)
    policy = service._start(db, account_id, generation, character_id)
    capability = policy.get("haven_world")
    if not isinstance(capability, dict) or capability.get("enabled") is not True:
        raise ValueError("Guild Haven World operations are disabled")
    current = db.execute(
        "SELECT map_id,instance_id FROM characters WHERE id=%s AND account_id=%s",
        (character_id, account_id),
    ).fetchone()
    if current is None or any(
        current[k] != context[k] for k in ("map_id", "instance_id")
    ):
        raise ValueError("Haven World actor location changed")
    guild = service._guild(db, character_id)
    member = db.execute(
        "SELECT r.permissions FROM guild_members m JOIN guild_ranks r "
        "ON r.guild_id=m.guild_id AND r.id=m.rank_id WHERE m.guild_id=%s AND m.character_id=%s",
        (guild["id"], character_id),
    ).fetchone()
    if member is None or not member["permissions"] & permission_mask(
        ("MANAGE_HAVEN_WORLD",)
    ):
        raise ValueError("Guild permission denied: MANAGE_HAVEN_WORLD")
    binding = db.execute(
        "SELECT * FROM guild_haven_worlds WHERE guild_id=%s FOR UPDATE", (guild["id"],)
    ).fetchone()
    if binding is None or any(
        binding[k] != context[k] for k in ("map_id", "instance_id", "native_world_id")
    ):
        raise ValueError("This is not the guild's assigned Haven World")
    return dict(binding)


def assign(
    store,
    account_id,
    generation,
    character_id,
    *,
    guild_id,
    native_world_id,
    map_id,
    instance_id,
    entry,
):
    """Administrative durable assignment; never bind the public instance zero.

    The caller must prepare the real private world and its entry/publication
    first. This operation grants no terrain, teleport or population implicitly.
    """
    values = (guild_id, native_world_id, map_id, instance_id)
    if (
        any(type(v) is not int for v in values)
        or guild_id <= 0
        or map_id <= 0
        or instance_id <= 0
        or native_world_id != -guild_id
    ):
        raise ValueError("Haven World native identity must equal negative guild ID")
    from wakfu_server.combat_terrain import map_geometry

    geometry = map_geometry(map_id)
    if (
        not isinstance(entry, (tuple, list))
        or len(entry) != 3
        or any(type(v) is not int for v in entry)
        or tuple(entry) not in {tuple(c) for c in geometry["cells"]}
    ):
        raise ValueError("A native walkable Haven World arrival cell is required")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        admin = db.execute(
            "SELECT is_admin FROM accounts WHERE id=%s", (account_id,)
        ).fetchone()
        if admin is None or admin["is_admin"] is not True:
            raise ValueError("Haven World assignment requires administrator authority")
        guild = db.execute(
            "SELECT id FROM guilds WHERE id=%s AND dissolved_at IS NULL FOR UPDATE",
            (guild_id,),
        ).fetchone()
        if guild is None:
            raise ValueError("Haven World assignment requires an active guild")
        if db.execute(
            "SELECT 1 FROM dungeon_instances WHERE instance_id=%s", (instance_id,)
        ).fetchone():
            raise ValueError("A dungeon cannot be reassigned as a Haven World")
        existing = db.execute(
            "SELECT * FROM guild_haven_worlds WHERE guild_id=%s", (guild_id,)
        ).fetchone()
        desired = dict(
            zip(("guild_id", "native_world_id", "map_id", "instance_id"), values)
        )
        desired.update(zip(("entry_x", "entry_y", "entry_z"), entry))
        if existing is not None:
            if any(existing[k] != v for k, v in desired.items()):
                raise ValueError(
                    "Existing Haven World assignment cannot be overwritten"
                )
            return dict(existing)
        binding = dict(
            db.execute(
                "INSERT INTO guild_haven_worlds(guild_id,native_world_id,map_id,instance_id,entry_x,entry_y,entry_z,assigned_by,assignment_origin) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'wakemu_explicit_private_assignment_v1') RETURNING *",
                (*values, *entry, account_id),
            ).fetchone()
        )
        # Reuse the existing generic guild-holdings settlement boundary: a
        # guild cannot dissolve and strand an assigned world or its residents.
        db.execute(
            "INSERT INTO guild_service_state(guild_id,service,record) VALUES(%s,'haven_world',%s)",
            (
                guild_id,
                Jsonb(
                    dict(
                        native_world_id=native_world_id,
                        map_id=map_id,
                        instance_id=instance_id,
                    )
                ),
            ),
        )
        return binding


def project_character(db, character):
    """Derive signed native POSITION world ID from the durable private scope.

    The positive terrain definition and positive server instance stay distinct.
    This projection does not confer guild permissions or alter player data.
    """
    result = dict(character)
    result.pop("native_world_id", None)
    result.pop("_native_haven_world_position", None)
    if character.get("instance_id", 0) <= 0:
        return result
    row = db.execute(
        "SELECT w.guild_id,w.native_world_id,g.name,g.blazon FROM guild_haven_worlds w JOIN guilds g ON g.id=w.guild_id WHERE w.map_id=%s AND w.instance_id=%s",
        (character["map_id"], character["instance_id"]),
    ).fetchone()
    if row is not None:
        result["native_world_id"] = row["native_world_id"]
        result["_native_haven_world_position"] = _OwnedHavenWorldPosition(
            row["guild_id"],
            character["map_id"],
            character["instance_id"],
            row["name"],
            row["blazon"],
        )
    return result


def entry_plan(store, account_id, generation, character_id):
    """Return a guild member's authorized destination for the World transition.

    World owns company/session relocation, registry publication and return. It
    must use this server plan, never a client-supplied private destination.
    """
    from wakfu_server.guild_service import GuildService
    from wakfu_server.simple_item_actions import _idle

    service = GuildService(store)
    with store.connection() as db:
        policy = service._start(db, account_id, generation, character_id)
        capability = policy.get("haven_world")
        if not isinstance(capability, dict) or capability.get("enabled") is not True:
            raise ValueError("Guild Haven World access is disabled")
        guild = service._guild(db, character_id)
        _idle(db, character_id, store.now())
        row = db.execute(
            "SELECT * FROM guild_haven_worlds WHERE guild_id=%s", (guild["id"],)
        ).fetchone()
        if row is None:
            raise ValueError("This guild has no assigned Haven World")
        return dict(
            map_id=row["map_id"],
            instance_id=row["instance_id"],
            native_world_id=row["native_world_id"],
            x=row["entry_x"],
            y=row["entry_y"],
            z=row["entry_z"],
        )


def scene_context(store, map_id, instance_id):
    """Project only a server-owned scene scope for native NPC publication."""
    context = dict(map_id=map_id, instance_id=instance_id)
    if instance_id <= 0:
        return context
    with store.connection() as db:
        return project_character(db, context)


def bootstrap_packet(character):
    """Original12957 metadata and real partition must follow scene teardown."""
    if "native_world_id" not in character:
        return None
    world_identity(character)
    from wakfu_server.haven_world_native import bootstrap
    from wakfu_server.haven_world_terrain import TEMPLATE_MAP_ID, PARTITIONS

    if character["map_id"] != TEMPLATE_MAP_ID:
        raise ValueError("Assigned Haven World lacks a published native layout")
    proof = character["_native_haven_world_position"]
    if not proof.guild_name:
        raise ValueError("Missing owning guild's native world metadata")
    return bootstrap(
        proof.guild_id,
        proof.guild_name,
        proof.guild_blazon,
        partitions=PARTITIONS,
        m_ai=0,
        llx=False,
        lnq=False,
    )


def _provision_base(db, *, guild_id, assigned_by, origin):
    """Provision or adopt one base world under the caller's locked guild."""
    from wakfu_server.haven_world_terrain import TEMPLATE_MAP_ID, ENTRY
    from wakfu_server.combat_terrain import map_geometry

    existing = db.execute(
        "SELECT * FROM guild_haven_worlds WHERE guild_id=%s FOR UPDATE", (guild_id,)
    ).fetchone()
    if existing is not None:
        return dict(existing)
    geometry = map_geometry(TEMPLATE_MAP_ID)
    if ENTRY not in {tuple(cell) for cell in geometry["cells"]}:
        raise ValueError("Missing native Haven World starter arrival")
    instance = db.execute(
        "SELECT nextval('haven_world_instance_ids') AS id"
    ).fetchone()["id"]
    for table in ("dungeon_instances", "rift_instances", "objectives_challenge_runs"):
        if db.execute(
            f"SELECT 1 FROM {table} WHERE instance_id=%s", (instance,)
        ).fetchone():
            raise ValueError(
                "Reserved Haven World instance collides with an existing domain"
            )
    binding = dict(
        db.execute(
            "INSERT INTO guild_haven_worlds(guild_id,native_world_id,map_id,instance_id,entry_x,entry_y,entry_z,assigned_by,assignment_origin) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                guild_id,
                -guild_id,
                TEMPLATE_MAP_ID,
                instance,
                *ENTRY,
                assigned_by,
                origin,
            ),
        ).fetchone()
    )
    db.execute(
        "INSERT INTO guild_service_state(guild_id,service,record) VALUES(%s,'haven_world',%s)",
        (
            guild_id,
            Jsonb(
                dict(
                    native_world_id=-guild_id,
                    map_id=TEMPLATE_MAP_ID,
                    instance_id=instance,
                )
            ),
        ),
    )
    return binding


def provision_unlocked_world(db, store, account_id, guild_id):
    """Trusted bonus84 effect, inside the paid native purchase transaction.

    The progression caller verifies the selected session, BUY_BONUS permission,
    original bonus descriptor, points and learning state before this hook. No
    independent connection or commit may escape its debit/receipt transaction.
    """
    if (
        type(account_id) is not int
        or account_id <= 0
        or type(guild_id) is not int
        or guild_id <= 0
    ):
        raise ValueError("Invalid native Haven World unlock authority")
    guild = db.execute(
        "SELECT id FROM guilds WHERE id=%s AND dissolved_at IS NULL FOR UPDATE",
        (guild_id,),
    ).fetchone()
    member = db.execute(
        "SELECT 1 FROM guild_members m JOIN characters c ON c.id=m.character_id "
        "WHERE m.guild_id=%s AND c.account_id=%s LIMIT 1",
        (guild_id, account_id),
    ).fetchone()
    if guild is None or member is None:
        raise ValueError(
            "Native Haven World unlock requires its actual purchasing guild member"
        )
    return _provision_base(
        db,
        guild_id=guild_id,
        assigned_by=account_id,
        origin="explicit_native_bonus84_base_world_v1",
    )


def create_assignment(store, account_id, generation, character_id, guild_id):
    """Explicit administrative starter assignment; normal unlock uses bonus84."""
    if type(guild_id) is not int or guild_id <= 0:
        raise ValueError("Invalid Haven World guild assignment")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        admin = db.execute(
            "SELECT is_admin FROM accounts WHERE id=%s", (account_id,)
        ).fetchone()
        if admin is None or admin["is_admin"] is not True:
            raise ValueError("Haven World assignment requires administrator authority")
        guild = db.execute(
            "SELECT id FROM guilds WHERE id=%s AND dissolved_at IS NULL FOR UPDATE",
            (guild_id,),
        ).fetchone()
        if guild is None:
            raise ValueError("Haven World assignment requires an active guild")
        return _provision_base(
            db,
            guild_id=guild_id,
            assigned_by=account_id,
            origin="wakemu_explicit_private_assignment_v1",
        )
