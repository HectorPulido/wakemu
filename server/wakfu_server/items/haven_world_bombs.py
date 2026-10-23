"""Atomic native bHQ area removal inside an assigned guild Haven World only."""
import struct
from psycopg.types.json import Jsonb

# Original bHQ descriptors: one radius parameter, consumed source, target X/Y.
ACTIONS = {4728: (17551, 4), 4838: (17592, 8), 4828: (17593, 16)}


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid Haven World bomb request")
    action, uid = struct.unpack_from(">iq", body)
    if action not in ACTIONS:
        return None
    if len(body) != 20 or uid <= 0:
        raise ValueError("Invalid native Haven World bomb target grammar")
    return "bHQ"


def in_disk(member, x, y, radius):
    return (member["x"] - x) ** 2 + (member["y"] - y) ** 2 <= radius**2


def _remove_available(db, map_id, instance_id, x, y, radius):
    """Reuse durable group tombstones without fake defeats, XP or loot awards.

    Fighting/reserved groups remain untouched. Existing row triggers filter
    removed members, and their tombstones prevent seed/respawn resurrection.
    """
    from wakfu_server.combat_monster_world import remove_message, spawn_group

    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"monster-population:{map_id}:{instance_id}",),
    )
    rows = list(
        db.execute(
            "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s "
            "AND status='available' ORDER BY group_id FOR UPDATE",
            (map_id, instance_id),
        )
    )
    changed, packets = [], []
    for row in rows:
        prior = set(row["ecology_admin_removed_ids"])
        live = [m for m in row["members"] if m["id"] not in prior]
        removed = [m for m in live if in_disk(m, x, y, radius)]
        if not removed:
            continue
        ids = sorted(m["id"] for m in removed)
        key = (map_id, instance_id, row["group_id"])
        db.execute(
            "UPDATE combat_groups SET ecology_admin_removed_ids=%s,revision=revision+1 "
            "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
            (Jsonb(sorted(prior | set(ids))), *key),
        )
        for table in ("monster_maturation_timers", "monster_reproduction_timers"):
            db.execute(
                f"DELETE FROM {table} WHERE map_id=%s AND instance_id=%s AND monster_id=ANY(%s)",
                (map_id, instance_id, ids),
            )
        db.execute(
            "UPDATE monster_maturation_outbox SET published=TRUE "
            "WHERE map_id=%s AND instance_id=%s AND group_id=%s AND monster_id=ANY(%s)",
            (*key, ids),
        )
        db.execute(
            "UPDATE monster_reproduction_outbox o SET published=TRUE "
            "FROM monster_reproduction_receipts r WHERE o.map_id=r.map_id "
            "AND o.instance_id=r.instance_id AND o.monster_id=r.monster_id AND o.cycle=r.cycle "
            "AND o.map_id=%s AND o.instance_id=%s AND o.group_id=%s "
            "AND (o.monster_id=ANY(%s) OR r.child_id=ANY(%s))",
            (*key, ids, ids),
        )
        # A partial group's layout must be republished as a complete remaining
        # group, using the existing native encoders and retained physical IDs.
        for offset in range(0, len(live), 255):
            packets.append(
                remove_message(tuple(m["id"] for m in live[offset : offset + 255]))
            )
        survivors = [m for m in live if m["id"] not in set(ids)]
        if survivors:
            from wakfu_server.guild_haven_world import project_character

            context = project_character(
                db, dict(map_id=map_id, instance_id=instance_id)
            )
            packets.append(
                (
                    12608,
                    spawn_group(
                        survivors, group_id=row["group_id"], world_context=context
                    ),
                )
            )
        changed.append(dict(group_id=row["group_id"], actor_ids=ids))
    return changed, packets


def use(store, account_id, generation, character_id, body, *, in_fight, context):
    """Caller supplies trusted current World context, never request identities.

    SQL ownership, rank, private scope, debit, population mutation and outcome
    commit together. Native requests have no nonce; another stack unit is a new
    legitimate use. Publication follows commit and never retries the mutation.
    """
    if type(in_fight) is not bool or in_fight or action_class(body) != "bHQ":
        raise ValueError("Use this bomb outside combat in your Haven World")
    action, uid, x, y = struct.unpack(">iqii", body)
    reference, radius = ACTIONS[action]
    from wakfu_server.combat_terrain import map_geometry
    from wakfu_server.guild_haven_world import authorize
    from wakfu_server.inventory_owner import lock_item_owner
    from wakfu_server.simple_item_actions import _idle, _equipped
    from wakfu_server.haven_bag_furniture_knowledge import _rules

    if (
        not isinstance(context, dict)
        or any(
            type(context.get(k)) is not int
            for k in ("map_id", "instance_id", "native_world_id", "x", "y", "z")
        )
        or context["map_id"] <= 0
        or context["instance_id"] <= 0
    ):
        raise ValueError("Current Haven World terrain authority is required")
    geometry = map_geometry(context["map_id"])
    grounds = [
        c
        for c in geometry["cells"]
        if c[0] == x and c[1] == y and abs(c[2] - context["z"]) <= 1
    ]
    if not grounds:
        raise ValueError("Invalid native bomb target ground or height")
    with store.connection() as db:
        binding = authorize(
            db, store, account_id, generation, character_id, context=context
        )
        owner = lock_item_owner(store, db, account_id, generation, character_id, (uid,))
        if owner != character_id:
            raise ValueError("Select the guild member carrying this bomb")
        _idle(db, character_id, store.now())
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (uid, character_id),
        ).fetchone()
        if item is None or item["reference"] != reference or item["quantity"] < 1:
            raise ValueError("The source does not match this native bomb")
        published = _rules().get(reference, {})
        if (
            published.get("use_action_id") != action
            or published.get("use_action_class") != "bHQ"
        ):
            raise ValueError("Bomb differs from the active native action catalog")
        character = store.character(account_id, character_id, db)
        if _equipped(character, uid):
            raise ValueError("Unequip the bomb before using it")
        changed, scene_packets = _remove_available(
            db, binding["map_id"], binding["instance_id"], x, y, radius
        )
        if item["quantity"] == 1:
            db.execute(
                "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                (uid, character_id),
            )
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s AND character_id=%s",
                (uid, character_id),
            )
        outcome = dict(
            removed_groups=changed,
            removed_count=sum(len(r["actor_ids"]) for r in changed),
        )
        receipt = db.execute(
            "INSERT INTO haven_world_bomb_uses(guild_id,account_id,character_id,source_uid,source_reference,"
            "native_world_id,map_id,instance_id,center_x,center_y,radius,outcome) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (
                binding["guild_id"],
                account_id,
                character_id,
                uid,
                reference,
                binding["native_world_id"],
                binding["map_id"],
                binding["instance_id"],
                x,
                y,
                radius,
                Jsonb(outcome),
            ),
        ).fetchone()
        return dict(
            character=store.character(account_id, character_id, db),
            applied=True,
            native_class="bHQ",
            consumed=1,
            packets=[(12470, struct.pack(">qh", uid, -1))],
            scene_packets=scene_packets,
            scene=(binding["map_id"], binding["instance_id"]),
            receipt_id=receipt["id"],
            **outcome,
        )
