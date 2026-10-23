"""Read-only connected-time view of exact world-owned combat consumables."""
from copy import copy


def online_snapshot_view(store, fight, actor_id, *, now_ms):
    """Rebase copied carrier clocks, without mutating the live fight or SQL.

    Native combat timers suppress expiry. Their wire remaining time must still
    follow the durable connected-time clock across logout and reconnect.
    """
    bindings = tuple(
        row
        for row in getattr(fight, "native_consumable_initializations", {}).get(
            actor_id, ()
        )
        if row.get("clock") == "online"
    )
    if not bindings:
        return fight
    actor = fight.actors.get(actor_id)
    if actor is None or not actor.controlled or type(now_ms) is not int:
        raise ValueError("Invalid consumable snapshot actor or clock")
    ledger = getattr(actor, "state_ledger", None)
    entries = {} if ledger is None else {row.uid: row for row in ledger.entries}
    bindings = tuple(row for row in bindings if row.get("combat_uid") in entries)
    if not bindings:
        return fight
    with store.connection() as db:
        rows = db.execute(
            "SELECT b.*,c.account_id,s.generation AS current_generation, "
            "s.character_id AS selected_id, "
            "(c.id=s.character_id OR EXISTS (SELECT 1 FROM account_hero_rosters r "
            "JOIN account_hero_slots h ON h.account_id=r.account_id "
            "WHERE r.account_id=c.account_id AND r.leader_id=s.character_id "
            "AND h.character_id=c.id)) AS active_company "
            "FROM character_consumable_buffs b JOIN characters c ON c.id=b.character_id "
            "LEFT JOIN sessions s ON s.account_id=c.account_id AND s.expires_at>%s "
            "WHERE b.character_id=%s AND b.combat_id=%s AND b.uid=ANY(%s)",
            (store.now(), actor_id, fight.id, [row["world_uid"] for row in bindings]),
        ).fetchall()
    owned = {row["uid"]: row for row in rows}
    view, actor_view, ledger_view = copy(fight), copy(actor), copy(ledger)
    for binding in bindings:
        row = owned.get(binding["world_uid"])
        native = entries[binding["combat_uid"]]
        if (
            row is None
            or row["account_id"] != actor.owner_id
            or row["clock"] != "online"
            or row["state_id"] != binding["state_id"]
            or native.reference != row["state_id"]
            or native.level != row["level"]
            or native.target_id != actor_id
            or native.caster_id != actor_id
        ):
            raise ValueError("Missing exact durable consumable snapshot authority")
        remaining = row["remaining_ms"]
        if (
            row["online_generation"] is not None
            and row["online_generation"] == row["current_generation"]
            and row["active_company"]
        ):
            if now_ms < row["online_anchor_ms"]:
                raise ValueError("Consumable snapshot clock moved backwards")
            remaining = max(0, remaining - (now_ms - row["online_anchor_ms"]))
        ledger_view.install_realtime_clock(
            native.uid,
            deadline_ms=now_ms + max(1, remaining),
            in_combat=True,
        )
    actor_view.state_ledger = ledger_view
    view.actors = dict(fight.actors, **{})
    view.actors[actor_id] = actor_view
    return view
