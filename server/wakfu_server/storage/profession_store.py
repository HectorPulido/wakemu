"""Account-owned craft progress; leased characters provide action context."""
from wakfu_server import native_catalog as protocol_catalog
import json
import struct

from .inventory_items import _lease
from .paths import DATA_ROOT
from .profession_wire import MAX_XP, level as xp_level, snapshot


def _validate(profession_id):
    if type(profession_id) is not int or not 0 < profession_id < 2**31:
        raise ValueError("Invalid profession identity")


def stored_level(db, account_id, profession_id):
    """Use within an already leased transaction; None means unlearned."""
    _validate(profession_id)
    row = db.execute(
        "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=%s",
        (account_id, profession_id),
    ).fetchone()
    return None if row is None else xp_level(row["xp"])


def level(store, account_id, generation, character_id, profession_id):
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        result = stored_level(db, account_id, profession_id)
        return 0 if result is None else result


def account_packet(db, account_id):
    """Restore owned absolute progress, including counters/actions/settings."""
    db.execute(
        "INSERT INTO account_craft_state(account_id) VALUES(%s) "
        "ON CONFLICT(account_id) DO NOTHING",
        (account_id,),
    )
    state = db.execute(
        "SELECT configuration,additional FROM account_craft_state WHERE account_id=%s",
        (account_id,),
    ).fetchone()
    professions = {
        row["profession_id"]: {k: row[k] for k in ("xp", "counters", "actions")}
        for row in db.execute(
            "SELECT * FROM account_professions WHERE account_id=%s ORDER BY profession_id",
            (account_id,),
        )
    }
    return snapshot(
        professions,
        configuration=bytes(state["configuration"]),
        additional=bytes(state["additional"]),
    )


def ensure_learned(store, account_id, generation, character_id, profession_ids):
    known = set(
        protocol_catalog.load(DATA_ROOT / "profession-actions.json")["profession_ids"]
    )
    ids = list(profession_ids)
    if any(type(i) is not int or i not in known for i in ids) or len(set(ids)) != len(
        ids
    ):
        raise ValueError("Unknown native profession requested")
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        for profession_id in ids:
            db.execute(
                "INSERT INTO account_professions(account_id,profession_id) VALUES(%s,%s) "
                "ON CONFLICT(account_id,profession_id) DO NOTHING",
                (account_id, profession_id),
            )
        levels = {
            row["profession_id"]: xp_level(row["xp"])
            for row in db.execute(
                "SELECT profession_id,xp FROM account_professions WHERE account_id=%s",
                (account_id,),
            )
        }
        packet = account_packet(db, account_id)
    # Absolute state follows learning so defaults cannot overwrite partial XP.
    return dict(
        levels=levels, packets=[(12675, struct.pack(">i", i)) for i in ids] + [packet]
    )


def ensure_all_learned(store, account_id, generation, character_id):
    """Unlock every native job at zero XP without resetting existing progress.

    Profession progress is account-owned, so this also repairs older accounts
    when any of their characters joins the world.
    """
    ids = protocol_catalog.load(DATA_ROOT / "profession-actions.json")["profession_ids"]
    return ensure_learned(store, account_id, generation, character_id, sorted(ids))


def learned(store, account_id, generation, character_id, profession_id):
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        return stored_level(db, account_id, profession_id) is not None


def award(
    store,
    db,
    account_id,
    generation,
    character_id,
    profession_id,
    *,
    base_xp,
    operation,
    territory_percent=None,
    action_category=None,
    native_map_id=None,
):
    """Credit once inside the same transaction as the successful action reward.

    Callers supply a server-owned token and an independently verified reward.
    This function does not infer flora or recipe XP from previews. A replay
    returns no delta packet, because replaying a delta adds XP twice.
    """
    _validate(profession_id)
    if (
        type(base_xp) is not int
        or not 0 <= base_xp < 2**63
        or type(operation) is not str
        or not 1 <= len(operation) <= 128
        or (
            territory_percent is not None
            and (
                type(territory_percent) is not int
                or not -100 <= territory_percent <= 100
            )
        )
    ):
        raise ValueError("Invalid profession reward")
    _lease(store, db, account_id, generation, character_id)
    previous = db.execute(
        "SELECT character_id,applied_xp FROM profession_xp_receipts "
        "WHERE account_id=%s AND operation=%s AND profession_id=%s",
        (account_id, operation, profession_id),
    ).fetchone()
    if previous is not None:
        if previous["character_id"] != character_id:
            raise ValueError("Profession reward belongs to another actor")
        return dict(applied=False, xp=previous["applied_xp"], packets=[])
    row = db.execute(
        "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=%s FOR UPDATE",
        (account_id, profession_id),
    ).fetchone()
    if row is None:
        raise ValueError("Profession reward requires a learned profession")
    configuration = db.execute(
        "SELECT value FROM settings WHERE name='profession_xp'"
    ).fetchone()
    policy = None if configuration is None else configuration["value"]
    if (
        not isinstance(policy, dict)
        or set(policy) != {"multiplier_basis_points"}
        or type(policy["multiplier_basis_points"]) is not int
        or not 0 <= policy["multiplier_basis_points"] <= 1_000_000
    ):
        raise ValueError("Invalid profession XP policy")
    if territory_percent is None:
        territory_percent = 0
        if action_category in ("planting", "harvest"):
            from wakfu_server.territory_bonuses import (
                current_region,
                profession_xp_percent,
            )

            # All native collection routes use the same regional job effect,
            # including monster collection as well as flora collection.
            character = store.character(account_id, character_id, db)
            territory_percent = profession_xp_percent(
                current_region(db, character),
                action_category,
            )
    consumable_percent = 0
    if action_category is not None:
        categories = {
            "recipe": "craft_xp",
            "planting": "plant_xp",
            "harvest": "collect_xp",
        }
        if action_category not in categories:
            raise ValueError("Invalid profession reward action category")
        from wakfu_server.profession_consumable_modifiers import modifiers
        from wakfu_server.native_world_context import is_battleground

        if native_map_id is None:
            native_map_id = store.character(account_id, character_id, db)["map_id"]
        consumable_percent = modifiers(
            store,
            db,
            character_id,
            profession_id,
            generation=generation,
            is_battleground=is_battleground(native_map_id),
        )[categories[action_category]]
    # Native protector job effects are applied to the base reward first; the
    # configurable account-wide profession multiplier is applied afterward.
    regional_base = (
        base_xp * max(0, 100 + territory_percent + consumable_percent) // 100
    )
    delta = min(
        MAX_XP - row["xp"],
        regional_base * policy["multiplier_basis_points"] // 10000,
    )
    db.execute(
        "UPDATE account_professions SET xp=xp+%s WHERE account_id=%s AND profession_id=%s",
        (delta, account_id, profession_id),
    )
    db.execute(
        "INSERT INTO profession_xp_receipts(account_id,operation,profession_id,character_id,applied_xp) "
        "VALUES(%s,%s,%s,%s,%s)",
        (account_id, operation, profession_id, character_id, delta),
    )
    return dict(
        applied=True,
        xp=delta,
        packets=[]
        if delta == 0
        else [(12916, struct.pack(">iq", profession_id, delta))],
    )
