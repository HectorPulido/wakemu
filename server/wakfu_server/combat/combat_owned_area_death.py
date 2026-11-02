"""Native fbX.B -> Qs.l: retire owned areas when a fighter goes OFF_PLAY."""


def _owned_area_ids(fight, actor_id):
    """Read Qq.bcY, captured by eYQ.d as the inverse keep-after flag."""
    selected = []
    for identity, row in getattr(fight, "native_effect_areas", {}).items():
        if row.get("owner_id") != actor_id:
            continue
        if type(row.get("keep_after")) is not bool:
            raise ValueError("Missing actual owned area Qq.bcY constructor")
        if not row["keep_after"]:
            selected.append(identity)
    return selected


def apply_owned_area_death(fight, actor_id, *, retention):
    """Run Qs.l on the caller's private native OFF_PLAY damage preview.

    Qs.l snapshots areas whose bch is the defeated PV and whose bcY is true.
    eYQ.d initializes bcY to !keep_after. Qs.b removes spatial membership;
    it does not remove the creating eYQ from its owner's Qf.
    """
    selected = _owned_area_ids(fight, actor_id)
    if not selected:
        return ()

    from .combat_ordinary_death import registered_ordinary_death
    from .combat_global_pv_collections import global_area_order, global_fighter_guards

    actor = fight.actors.get(actor_id)
    if (
        actor is None
        or not registered_ordinary_death(fight, actor)
        or global_fighter_guards(fight, actor_id)["baG"] is not True
    ):
        raise ValueError("Owned area KO cleanup requires actual OFF_PLAY authority")
    callbacks = getattr(retention, "area_events", None)
    if (
        getattr(retention, "fight", None) is not fight
        or getattr(callbacks, "fight", None) is not fight
    ):
        raise ValueError("Owned area KO cleanup requires its native runtime callbacks")
    selected = set(selected)
    order = tuple(
        identity for identity in global_area_order(fight) if identity in selected
    )
    from .combat_effect_area import remove_owned_hour_area

    # Freeze actual object identities before the first synchronous callback.
    rows = tuple(fight.native_effect_areas[identity] for identity in order)
    for row in rows:
        current = fight.native_effect_areas.get(row["uid"])
        if current is None:
            continue  # A preceding Qs.b callback already removed it.
        if current is not row:
            raise ValueError("Owned area KO cleanup identity was replaced")
        remove_owned_hour_area(fight, row["uid"], callbacks=callbacks)
    retention.synchronize()
    return order
