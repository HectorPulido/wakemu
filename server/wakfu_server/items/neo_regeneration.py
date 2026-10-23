"""Native character/account Neo potions at caller-fenced human fight boundaries.

Original EN/FR/ES descriptions establish start/end full HP, account scope,
Neo-server lifetime, and Battlefield exclusion. Original item instances reject
ordinary use for both references, so durable owned possession supplies scope:
32701 in this character's ordinary bags,32702 in account quest inventory.
"""
from psycopg.pq import TransactionStatus

ACCOUNT_REFERENCE = 32702
CHARACTER_REFERENCE = 32701


def _transaction(db):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Neo restoration requires the caller transaction")


def mode_from_database(db):
    """Read the existing typed server-mode authority without a nested transaction."""
    _transaction(db)
    row = db.execute(
        "SELECT value FROM settings WHERE name='dungeon_server_mode'"
    ).fetchone()
    return mode_from_record(row)


def mode_from_record(row):
    """Validate the same settings receipt when supplied by an owned read join."""
    value = None if row is None else row["value"]
    if row is None:
        from types import SimpleNamespace
        from wakfu_server.combat_system_conditions import (
            boolean_system_configuration,
            fresh_system_configuration,
        )

        # An unconfigured ordinary server retains the original fresh-client
        # false default; an explicitly malformed setting is never accepted.
        return boolean_system_configuration(
            SimpleNamespace(native_system_configuration=fresh_system_configuration()),
            "server.group.isneo",
        )
    if (
        not isinstance(value, dict)
        or set(value) != {"version", "is_neo_server"}
        or type(value.get("version")) is not int
        or value["version"] != 1
        or type(value.get("is_neo_server")) is not bool
    ):
        raise ValueError("Missing or malformed authoritative Neo server mode")
    return value["is_neo_server"]


def _held_source(db, account_id, character_id=None):
    """Resolve only real owned custody, never a chest/temporary/build projection."""
    _transaction(db)
    if (
        type(account_id) is not int
        or account_id <= 0
        or (
            character_id is not None
            and (type(character_id) is not int or character_id <= 0)
        )
    ):
        raise ValueError("Invalid Neo restoration possession owner")
    rows = db.execute(
        "SELECT 'account' AS scope,NULL::jsonb AS container WHERE EXISTS("
        "SELECT 1 FROM account_quest_items WHERE account_id=%s AND reference=%s AND quantity>0) "
        "AND (%s::bigint IS NULL OR EXISTS(SELECT 1 FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL)) "
        "UNION ALL SELECT DISTINCT 'character',to_jsonb(c) FROM inventory_items i "
        "JOIN inventory_containers c ON c.uid=i.container AND c.character_id=i.character_id "
        "JOIN characters owner ON owner.id=i.character_id AND owner.account_id=%s AND owner.deleted_at IS NULL "
        "WHERE i.character_id=%s AND i.reference=%s AND i.quantity>0 "
        "AND c.kind BETWEEN 0 AND 3 AND c.flags=0 AND i.slot>=0 AND i.slot<c.capacity LIMIT 5",
        (
            account_id,
            ACCOUNT_REFERENCE,
            character_id,
            character_id,
            account_id,
            account_id,
            character_id,
            CHARACTER_REFERENCE,
        ),
    ).fetchall()
    for row in rows:
        if row["scope"] == "account":
            return row["scope"]
        from wakfu_server.combat_drop_delivery import _container_can_hold

        if _container_can_hold(row["container"], character_id):
            return row["scope"]
    return None


def eligible(db, account_id, *, native_map_id, is_neo_server, character_id=None):
    """Inspect exact owner scope and explicit trusted current server context."""
    _transaction(db)
    if (
        type(account_id) is not int
        or account_id <= 0
        or type(is_neo_server) is not bool
    ):
        raise ValueError("Invalid Neo restoration account or server context")
    from wakfu_server.native_world_context import is_battleground

    battlefield = is_battleground(native_map_id)
    if not is_neo_server or battlefield:
        return False
    return _held_source(db, account_id, character_id) is not None


def restoration_state(db, character, *, native_map_id, is_neo_server, boundary):
    """Return canonical full health, leaving authorization/once-only fencing to caller.

    Entry must precede both frozen membership health and actor construction.
    Return runs after ordinary casualty recovery, inside the existing successful
    finished-return fence. Abort/disconnect/withdrawal are not end-of-fight grants.
    """
    _transaction(db)
    if boundary not in ("entry", "return"):
        raise ValueError("Unsupported Neo restoration boundary")
    from wakfu_server.health_policy import visible

    identity, account = character.get("id"), character.get("account_id")
    if type(identity) is not int or identity <= 0:
        raise ValueError("Invalid Neo restoration character")
    if not eligible(
        db,
        account,
        native_map_id=native_map_id,
        is_neo_server=is_neo_server,
        character_id=identity,
    ):
        return None
    expected_hp = visible(
        character["max_hp"],
        character["hp_damage"],
        character["health_dead"],
        character.get("hp_zero_valid", False),
    )
    if character["hp"] != expected_hp:
        raise ValueError("Inconsistent canonical health for Neo restoration")
    if boundary == "entry" and character["health_dead"]:
        raise ValueError("Dead characters cannot enter combat through Neo restoration")
    return {
        "hp": character["max_hp"],
        "hp_damage": 0,
        "health_dead": False,
        "hp_zero_valid": False,
    }


def restore_canonical(store, db, character, *, native_map_id, is_neo_server, boundary):
    """Apply to an already-authorized durable human owner in the caller transaction.

    This is an internal health boundary, not a network handler. It intentionally
    adds no selected-main-only or live-session check: the caller's existing
    active-hero/frozen-return lease and once-only receipts remain authoritative.
    """
    _transaction(db)
    saved = db.execute(
        "SELECT hp,max_hp,hp_damage,health_dead,hp_zero_valid FROM characters WHERE id=%s "
        "AND account_id=%s AND deleted_at IS NULL FOR UPDATE",
        (character["id"], character["account_id"]),
    ).fetchone()
    keys = ("hp", "max_hp", "hp_damage", "health_dead", "hp_zero_valid")
    if saved is None or any(saved[key] != character[key] for key in keys):
        raise ValueError("Stale or foreign canonical Neo restoration owner")
    state = restoration_state(
        db,
        character,
        native_map_id=native_map_id,
        is_neo_server=is_neo_server,
        boundary=boundary,
    )
    if state is None:
        return dict(character=character, applied=False)
    return _apply_canonical(db, character, state, now=store.now())


def _apply_canonical(db, character, state, *, now=None):
    from wakfu_server import health_policy

    health_policy.apply_damage(db, character, state["hp_damage"], state["health_dead"])
    db.execute(
        "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) "
        "VALUES(%s,%s,COALESCE(%s,CURRENT_TIMESTAMP),0,COALESCE(%s,CURRENT_TIMESTAMP)) "
        "ON CONFLICT(character_id) DO UPDATE SET "
        "initial_hp=EXCLUDED.initial_hp,started_at=EXCLUDED.started_at,coefficient=0,last_at=EXCLUDED.last_at",
        (character["id"], state["hp"], now, now),
    )
    return dict(character=dict(character, **state), applied=True)


def state_from_database(db, character, *, native_map_id, boundary):
    """Cheap account-source probe first; only entitled owners need server mode."""
    _transaction(db)
    if _held_source(db, character["account_id"], character["id"]) is None:
        return None
    return restoration_state(
        db,
        character,
        native_map_id=native_map_id,
        is_neo_server=mode_from_database(db),
        boundary=boundary,
    )


def restore_entry_baseline(db, character):
    """Used only by the already-authorized locked human admission baseline."""
    state = state_from_database(
        db, character, native_map_id=character["map_id"], boundary="entry"
    )
    return (
        character
        if state is None
        else _apply_canonical(db, character, state)["character"]
    )


def project_entry_character(character, canonical_health):
    """Merge only committed canonical health into an existing live actor source."""
    if any(
        character.get(key) != canonical_health.get(key) for key in ("id", "account_id")
    ):
        raise ValueError("Foreign canonical entry health projection")
    from wakfu_server.health_policy import visible

    hp = visible(
        canonical_health["max_hp"],
        canonical_health["hp_damage"],
        canonical_health["health_dead"],
        canonical_health.get("hp_zero_valid", False),
    )
    if hp != canonical_health["hp"]:
        raise ValueError("Inconsistent canonical entry health projection")
    keys = ("hp", "max_hp", "hp_damage", "health_dead", "hp_zero_valid")
    return dict(
        character,
        **{key: canonical_health[key] for key in keys if key in canonical_health}
    )


def align_entry_actor(actor, before, after):
    """Project only an actual canonical admission heal into a fresh candidate."""
    projected = project_entry_character(before, after)
    keys = ("hp", "max_hp", "hp_damage", "health_dead")
    if all(before[key] == projected[key] for key in keys):
        return False
    if (
        actor.id != projected["id"]
        or actor.owner_id != projected["account_id"]
        or before["max_hp"] != projected["max_hp"]
        or projected["hp_damage"] != 0
        or projected["health_dead"]
        or projected["hp"] != projected["max_hp"]
    ):
        raise ValueError("Unexpected canonical admission health change")
    from wakfu_server.combat_hp_raw import hp_raw_present, set_hp_raw_current

    # Keep native maxima, retained effects, movement, and every other resource.
    if hp_raw_present(actor):
        set_hp_raw_current(actor, actor.max_hp)
    else:
        actor.hp = actor.max_hp
        if hasattr(actor, "effect_stats"):
            actor.effect_stats[1] = actor.hp
    return True


def freeze_fight_configuration(db, fight):
    """Pin typed Neo mode once on a new fight, preserving other native overrides."""
    from types import SimpleNamespace
    from wakfu_server.combat_system_conditions import (
        boolean_system_configuration,
        fresh_system_configuration,
    )

    configuration = getattr(fight, "native_system_configuration", None)
    if configuration is None:
        configuration = fresh_system_configuration()
    context = SimpleNamespace(native_system_configuration=configuration)
    boolean_system_configuration(context, "server.group.isneo")
    frozen = configuration.get("wakemu_neo_mode")
    if frozen is not None:
        if (
            not isinstance(frozen, dict)
            or set(frozen) != {"version", "is_neo_server"}
            or type(frozen["version"]) is not int
            or frozen["version"] != 1
            or type(frozen["is_neo_server"]) is not bool
            or configuration["overrides"].get("server.group.isneo")
            is not frozen["is_neo_server"]
        ):
            raise ValueError("Conflicting frozen fight Neo mode")
        return frozen["is_neo_server"]
    mode = mode_from_database(db)
    fight.native_system_configuration = dict(
        configuration,
        overrides=dict(configuration["overrides"], **{"server.group.isneo": mode}),
        wakemu_neo_mode={"version": 1, "is_neo_server": mode},
    )
    return mode
