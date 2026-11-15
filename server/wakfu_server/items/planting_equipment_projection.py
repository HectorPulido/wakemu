"""Inventory-owned profession projection for bounded external planting plans.

Equipment eligibility, criteria and effect arithmetic remain in the existing
Inventory implementation. Ecology receives only the resulting integer and the
exact durable intent identity; World revalidates the accepted operation.
"""


def pending_projection(store, epoch, started_at_ms, limit=4, *, gardens_only=False):
    """Read one bounded intent window and selected equipment consistently.

    The optional open-policy garden filter runs after LIMIT: its observation
    window must stay identical to Ecology's reserved interactive lane. Neither
    locations nor full character/inventory aggregates leave this boundary.
    """
    if not isinstance(epoch, str) or not epoch or len(epoch) > 128:
        raise ValueError("Invalid planting equipment world epoch")
    if type(started_at_ms) is not int or not 0 < started_at_ms < 2**53:
        raise ValueError("Invalid planting equipment snapshot start time")
    if type(limit) is not int or not 1 <= limit <= 4:
        raise ValueError("Invalid planting equipment projection limit")
    if type(gardens_only) is not bool:
        raise ValueError("Invalid planting equipment garden policy")

    output = []
    with store.connection() as db:
        # This is the first statement in the transaction. Every lease, seed and
        # equipment read below sees the same durable observation without locks.
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        rows = db.execute(
            "SELECT id,world_epoch,account_id,generation,character_id,"
            "intent_version,body,actor_location FROM ecology_planting_intents "
            "WHERE world_epoch=%s AND status='pending' "
            "AND created_at < to_timestamp(%s / 1000.0) "
            "ORDER BY intent_version LIMIT %s",
            (epoch, started_at_ms, limit),
        ).fetchall()
        for row in rows:
            if gardens_only and row["actor_location"].get("map_id") != 9:
                continue
            body = bytes(row["body"])
            projected = {
                "intent_id": row["id"],
                "intent_version": row["intent_version"],
                "world_epoch": row["world_epoch"],
                "account_id": row["account_id"],
                "generation": row["generation"],
                "character_id": row["character_id"],
                "body_hex": body.hex(),
            }
            try:
                if (
                    db.execute(
                        "SELECT 1 FROM sessions s JOIN characters c "
                        "ON c.id=s.character_id AND c.account_id=s.account_id "
                        "WHERE s.account_id=%s AND s.generation=%s "
                        "AND s.character_id=%s AND s.expires_at>%s "
                        "AND c.deleted_at IS NULL",
                        (
                            row["account_id"],
                            row["generation"],
                            row["character_id"],
                            store.now(),
                        ),
                    ).fetchone()
                    is None
                ):
                    raise ValueError("Invalid inventory session")

                # Importing/reading the canonical seed definitions is lazy:
                # empty intent windows do not load any gameplay catalogue.
                from wakfu_server.planting import SEEDS, decode
                from wakfu_server.profession_equipment_modifiers import modifiers

                request = decode(body)
                item = db.execute(
                    "SELECT reference FROM inventory_items "
                    "WHERE uid=%s AND character_id=%s",
                    (request["item_uid"], row["character_id"]),
                ).fetchone()
                if item is None:
                    raise ValueError("Seed unavailable or foreign")
                seed = SEEDS.get(item["reference"])
                if seed is None or seed["action_id"] != request["action_id"]:
                    raise ValueError("Unknown or mismatched native seed action")
                profession = seed["profession_id"]
                if type(profession) is not int or profession <= 0:
                    raise ValueError("Invalid equipment profession identity")
                projected["profession_id"] = profession
                amount = modifiers(store, db, row["character_id"], profession)[
                    "plant_probability"
                ]
                if type(amount) is not int or not -(1 << 31) <= amount < (1 << 31):
                    raise ValueError("Invalid authoritative planting profession bonus")
                projected["plant_probability"] = amount
            except ValueError as error:
                # Deterministic domain rejection belongs to this exact intent.
                # Database/network/programming failures must fail the snapshot.
                projected["error"] = str(error)
            output.append(projected)
    return output
