"""Canonical applied territory HP under the caller's owned character lock.

Observing a region never heals. A changed maximum preserves current HP except
for the actual lower cap, and rebases canonical wounds and regeneration once.
The ledger is applied state, not a fresh ecology observation or an icon marker.
"""
from datetime import datetime, timezone

from psycopg.pq import TransactionStatus


def load(db, character_id):
    """Return the persisted applied contribution without deriving region state."""
    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Invalid territorial health owner")
    row = db.execute(
        "SELECT * FROM character_territory_health_projection WHERE character_id=%s",
        (character_id,),
    ).fetchone()
    return None if row is None else dict(row)


def reconcile_in_transaction(
    db, character, *, applied_flat, state_id, map_id, instance_id, region_id, now_ms
):
    """Apply one complete regional observation to an already locked owner.

    The caller supplies the actual owner/hero position, not the leader's stored
    coordinates, and validates selected-generation authority before calling.
    No global policy is changed and no native equipment roots are replayed.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Territorial health requires an owned transaction")
    if (
        not isinstance(character, dict)
        or type(character.get("id")) is not int
        or character["id"] <= 0
        or type(character.get("account_id")) is not int
        or type(applied_flat) is not int
        or not -1000 <= applied_flat <= 1000
        or state_id not in (None, 1915, 1916, 1917)
        or (state_id is not None and type(state_id) is not int)
        or (state_id is None and applied_flat != 0)
        or type(map_id) is not int
        or map_id <= 0
        or type(instance_id) is not int
        or instance_id < 0
        or (region_id is not None and type(region_id) is not int)
        or type(now_ms) is not int
        or now_ms < 0
    ):
        raise ValueError("Invalid territorial health observation")
    previous = load(db, character["id"])
    if character.get("territory_health_projection") != previous:
        raise ValueError("Stale territorial health projection")
    metadata = dict(
        applied_flat=applied_flat,
        state_id=state_id,
        map_id=map_id,
        instance_id=instance_id,
        region_id=region_id,
    )
    if previous is not None and all(
        previous[key] == value for key, value in metadata.items()
    ):
        return dict(character)
    revision = 1 if previous is None else previous["revision"] + 1
    projection = dict(
        metadata, character_id=character["id"], revision=revision, updated_at_ms=now_ms
    )
    updated = dict(character, territory_health_projection=projection)
    from wakfu_server.equipment_stats import effective_character

    # Only inspect the new cap here; a legitimate zero-current marker is
    # revalidated against the rebased wound after the cap has been computed.
    maximum = effective_character(
        dict(updated, hp_zero_valid=False), include_consumable_buffs=True
    )["max_hp"]
    hp = min(character["hp"], maximum)
    damage = (
        character["hp_damage"] + maximum - character["max_hp"] + character["hp"] - hp
    )
    if damage < 0:
        raise ValueError("Territorial health disagrees with canonical wound")
    updated.update(hp=hp, max_hp=maximum, hp_damage=damage)
    changed = maximum != character["max_hp"] or hp != character["hp"]
    old_flat = 0 if previous is None else previous["applied_flat"]
    if old_flat != applied_flat:
        from wakfu_server.equipment_hp_lifecycle import reconcile_territory_projection

        equipment_projection = reconcile_territory_projection(
            db, character, updated, hp=hp
        )
        if equipment_projection is not None:
            updated["equipment_hp_projection"] = equipment_projection
    if changed:
        result = db.execute(
            """UPDATE characters SET hp=%s,max_hp=%s,hp_damage=%s
            WHERE id=%s AND account_id=%s AND hp=%s AND max_hp=%s AND hp_damage=%s
              AND health_dead=%s AND hp_zero_valid=%s""",
            (
                hp,
                maximum,
                damage,
                character["id"],
                character["account_id"],
                character["hp"],
                character["max_hp"],
                character["hp_damage"],
                character["health_dead"],
                character.get("hp_zero_valid", False),
            ),
        )
        if result.rowcount != 1:
            raise ValueError("Stale canonical territorial health transition")
        regeneration = db.execute(
            "SELECT coefficient FROM character_regeneration WHERE character_id=%s FOR UPDATE",
            (character["id"],),
        ).fetchone()
        if regeneration is not None:
            from wakfu_server.health import exploration_coefficient

            coefficient = (
                exploration_coefficient(maximum, hp)
                if regeneration["coefficient"] and not character["health_dead"]
                else 0
            )
            now = datetime.fromtimestamp(now_ms / 1000, timezone.utc)
            # The existing baseline trigger snapshots the newly committed wound.
            db.execute(
                """UPDATE character_regeneration SET initial_hp=%s,coefficient=%s,
                started_at=%s,last_at=%s WHERE character_id=%s""",
                (hp, coefficient, now, now, character["id"]),
            )
    if previous is None:
        db.execute(
            """INSERT INTO character_territory_health_projection
            (character_id,applied_flat,state_id,map_id,instance_id,region_id,revision,updated_at_ms)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                character["id"],
                applied_flat,
                state_id,
                map_id,
                instance_id,
                region_id,
                revision,
                now_ms,
            ),
        )
    else:
        result = db.execute(
            """UPDATE character_territory_health_projection SET applied_flat=%s,state_id=%s,
            map_id=%s,instance_id=%s,region_id=%s,revision=%s,updated_at_ms=%s
            WHERE character_id=%s AND revision=%s""",
            (
                applied_flat,
                state_id,
                map_id,
                instance_id,
                region_id,
                revision,
                now_ms,
                character["id"],
                previous["revision"],
            ),
        )
        if result.rowcount != 1:
            raise ValueError("Stale territorial health ledger transition")
    return updated
