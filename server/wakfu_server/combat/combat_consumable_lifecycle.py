"""Durable consumable ownership at combat membership and owned health return."""


def enter_participant(store, db, character_id, fight_id, *, generation):
    from wakfu_server.consumable_buffs import enter_combat

    return enter_combat(store, db, character_id, fight_id, generation=generation)


def refresh_participants(store, characters, fight_id):
    """Refresh native input rows immediately before the readiness transaction.

    Durable membership is already committed. No caller-owned character mapping
    is changed until every member has passed its identity/generation checks.
    """
    if not isinstance(characters, dict):
        raise ValueError("Owned combat character mapping required")
    result = {}
    with store.connection() as db:
        for identity in sorted(characters):
            character = characters[identity]
            if not isinstance(character, dict) or character.get("id") != identity:
                raise ValueError("Combat consumable character identity mismatch")
            participant = db.execute(
                "SELECT account_id,session_generation FROM combat_fight_participants "
                "WHERE fight_id=%s AND character_id=%s FOR UPDATE",
                (fight_id, identity),
            ).fetchone()
            if (
                participant is None
                or character.get("account_id", participant["account_id"])
                != participant["account_id"]
            ):
                raise ValueError("Missing owned consumable combat participant")
            states = enter_participant(
                store,
                db,
                identity,
                fight_id,
                generation=participant["session_generation"],
            )
            result[identity] = dict(character, consumable_states=states)
    return result


def return_participant(store, db, character_id, fight, *, generation):
    """Reconcile all protected world states inside the guarded health receipt.

    Placement aborts have not constructed native carriers, so their unchanged
    durable states return with elapsed clocks. Active carriers use their actual
    UID mapping, including explicit native removals and changed levels.
    """
    from wakfu_server import consumable_buffs
    from .combat_consumable_states import returning_states

    now_ms = int(store.clock() * 1000)
    states = consumable_buffs.active_states(
        store, db, character_id, generation=generation, now_ms=now_ms
    )
    protected = tuple(row for row in states if row["combat_id"] == fight.id)
    if not protected:
        return ()
    bindings = getattr(fight, "native_consumable_initializations", {})
    if character_id in bindings:
        updates = returning_states(fight, character_id, now_ms=now_ms)
    else:
        if character_id in getattr(fight, "native_class_initializations", {}):
            raise ValueError("Initialized consumable participant lacks native bindings")
        updates = tuple(
            dict(
                uid=row["uid"],
                state_id=row["state_id"],
                removed=False,
                level=row["level"],
                clock=row["clock"],
                remaining_ms=row["remaining_ms"],
            )
            for row in protected
        )
    consumable_buffs.return_from_combat(
        store,
        db,
        character_id,
        fight.id,
        updates,
        generation=generation,
        now_ms=now_ms,
    )
    if character_id in bindings:
        # Explicit Wakemu outcome boundary: native descriptors subscribe their
        # fight counters to1030 and one-fight foods to1043. The original server
        # producer is unavailable. Apply this only to owned durable consumables,
        # after rewards and the once-only health receipt, never Qf sublimations.
        return consumable_buffs.emit_events(
            store,
            db,
            character_id,
            (1030, 1043),
            generation=generation,
            now_ms=now_ms,
            fight_model=fight.native_fight_model,
        )
    return consumable_buffs.active_states(
        store, db, character_id, generation=generation, now_ms=now_ms
    )


def prepare_outcome(fight, runtime_factory, *, action_id):
    """Prepare once-only1026 for descendants of owned consumable carriers.

    This is an explicit Wakemu outcome policy inferred from original item22491:
    its beginning/end description pairs1028/1026 on the same native listener.
    The complete native replay view remains intact; only these owned listeners
    can receive the inferred END event. The caller publishes inside settlement.
    """
    from copy import deepcopy
    from .combat_event_replay import NativeExternalEvent

    if getattr(fight, "phase", None) != "finished":
        raise ValueError("Consumable outcome requires a finished fight")
    if getattr(fight, "native_consumable_outcome_delivered", False):
        return fight, ()
    bindings = getattr(fight, "native_consumable_initializations", {})
    roots = {row["combat_uid"] for rows in bindings.values() for row in rows}
    if not roots:
        return fight, ()
    if not callable(runtime_factory):
        raise ValueError("Consumable outcome requires the native runtime")
    preview = deepcopy(fight)
    dispatcher, packets = runtime_factory(action_id=action_id)(
        preview, {"native_retained_container": {"present": False}}
    )
    retention = dispatcher.native_retention
    if retention.fight is not preview:
        raise ValueError("Consumable outcome runtime belongs to another fight")
    scope = set(roots)
    entries = retention.view().entries
    changed = True
    while changed:
        previous = len(scope)
        scope.update(entry.uid for entry in entries if entry.owner_uid in scope)
        changed = previous != len(scope)
    scope = frozenset(scope)
    terminal_phase, terminal_winner = preview.phase, preview.winner
    # Replay the last native effect boundary before closing PN, on the private
    # preview only. Ordinary native runners require the still-owned QI/current
    # context; this grants no new turn and emits no turn-start event.
    preview.phase = "active"
    with preview.effect_resolution():
        for actor_id in sorted(bindings):
            for channel in (6, 60, 61):
                dispatcher.replay_event(
                    NativeExternalEvent(actor_id, (1026,), channel),
                    authority=dispatcher.native_clone_authority,
                    eligible_uids=scope,
                )
        preview.phase, preview.winner = terminal_phase, terminal_winner
    # End-of-fight healing cannot restart a resolved encounter.
    preview.phase, preview.winner = terminal_phase, terminal_winner
    preview.native_consumable_outcome_delivered = True
    return preview, tuple(packets)
