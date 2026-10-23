"""Refresh derived equipment state within an owned item's transaction."""
from contextlib import contextmanager


@contextmanager
def refresh_equipment_after_mutation(store, db, account_id, character_id, uid):
    """Keep saved UID references while recomputing active stats without healing."""
    before = store.character(account_id, character_id, db)
    from wakfu_server.wire import proto_fields

    active = before.get("builds", {}).get(before.get("active_build_index", 0), {})
    references_target = any(
        tag == 10 and dict(proto_fields(value)).get(8) == uid
        for tag, value in proto_fields(bytes.fromhex(active.get("equipment", "")))
    )
    yield
    if not references_target:
        return
    after = store.character(account_id, character_id, db)
    from wakfu_server.equipment_hp_lifecycle import reconcile_selected_build

    reconcile_selected_build(db, after)
    after = store.character(account_id, character_id, db)
    from wakfu_server.equipment_stats import effective_character
    from wakfu_server.health_policy import reconfigure

    maximum = effective_character(after)["max_hp"]
    hp = reconfigure(db, after, maximum)
    if hp != before["hp"] or maximum != before["max_hp"]:
        now = store.now()
        db.execute(
            "UPDATE character_regeneration SET initial_hp=%s,started_at=%s,last_at=%s "
            "WHERE character_id=%s",
            (hp, now, now, character_id),
        )
