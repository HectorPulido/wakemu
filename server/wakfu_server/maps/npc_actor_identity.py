"""Durable NPC actor blocks exact through native Java long -> Lua double."""

MINIMUM = 1 << 50
MAXIMUM = (1 << 51) - 1
BLOCK_SIZE = 128


def lua_exact_identity(identity):
    return (
        type(identity) is int
        and identity != 0
        and abs(identity) <= (1 << 53)
        and int(float(identity)) == identity
    )


def allocate_block(db, quantity):
    """Reserve a global block without changing group or encounter receipt IDs."""
    if type(quantity) is not int or not 1 <= quantity <= BLOCK_SIZE:
        raise ValueError("Invalid NPC actor block size")
    for _ in range(1024):
        magnitude = db.execute(
            "SELECT nextval('lua_exact_npc_actor_ids') AS id"
        ).fetchone()["id"]
        if (
            type(magnitude) is not int
            or not MINIMUM <= magnitude <= MAXIMUM - BLOCK_SIZE + 1
        ):
            raise ValueError("Invalid Lua-exact NPC actor sequence")
        # Legacy random namespaces may have used this range. Never reuse a
        # claimed actor identity even in a different map/instance.
        collision = db.execute(
            "SELECT 1 FROM combat_group_members WHERE monster_id BETWEEN %s AND %s LIMIT 1",
            (-(magnitude + BLOCK_SIZE - 1), -magnitude),
        ).fetchone()
        if collision is None:
            return magnitude
    raise ValueError("Unable to reserve collision-free NPC actor block")


def repair_available_dungeon_members(db, key, row):
    """Use the alias-aware shared repair before available room publication."""
    members = tuple(row["members"])
    if (
        all(lua_exact_identity(member["id"]) for member in members)
        or row["status"] != "available"
    ):
        return members
    from .npc_actor_identity_repair import aliased_members, repair_available_group

    result = repair_available_group(db, key)
    if result["status"] != "remapped":
        raise ValueError("Unsafe dungeon actors require completed identity repair")
    return tuple(aliased_members(members, result["aliases"]))
