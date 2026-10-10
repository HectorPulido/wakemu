"""Atomic, lease-scoped fight-exit HP persistence without reward side effects."""
from . import health_store, health


def persist(
    store,
    account_id,
    generation,
    character,
    fight,
    *,
    reason="return",
    db=None,
    disconnected_baseline=None,
    session_character_id=None,
):
    """Record HP once; duplicate callbacks preserve subsequent world HP/position.

    'return' requires a finished fight; 'abort' also handles placement/active
    disconnection. Session replacement or stale HP must never overwrite the
    newer owner's state. No rewards or fight phase changes occur here.
    """
    actor = fight.actors.get(character["id"])
    if (
        reason not in ("return", "abort")
        or actor is None
        or not actor.controlled
        or actor.owner_id != account_id
    ):
        raise ValueError("Invalid own fight health exit")
    if reason == "return" and fight.phase != "finished":
        raise ValueError("Fight has not finished")
    if db is None:
        with store.connection() as connection:
            return persist(
                store,
                account_id,
                generation,
                character,
                fight,
                reason=reason,
                disconnected_baseline=disconnected_baseline,
                session_character_id=session_character_id,
                db=connection,
            )
    from psycopg.pq import TransactionStatus

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Fight health persistence requires an active transaction")
    if disconnected_baseline is None and session_character_id not in (
        None,
        character["id"],
    ):
        store.lock_character(db, account_id, generation, session_character_id)
        member = db.execute(
            "SELECT session_generation FROM combat_fight_participants WHERE fight_id=%s "
            "AND character_id=%s AND account_id=%s FOR UPDATE",
            (fight.id, character["id"], account_id),
        ).fetchone()
        if member is None or member["session_generation"] != generation:
            raise ValueError("Hero health exit lacks a frozen account combat lease")
        store.lock_character(
            db, account_id, generation, character["id"], selected=False
        )
        saved = store.character(account_id, character["id"], db)
    elif disconnected_baseline is None:
        saved = health_store._owned(store, db, account_id, generation, character["id"])
    else:
        # A shared owner may have cleanly disconnected before the final owner.
        # The durable participant row fences that old generation; the captured
        # entry values below fence the character row against intervening edits.
        lease = db.execute(
            "SELECT generation,character_id,expires_at FROM sessions "
            "WHERE account_id=%s FOR UPDATE",
            (account_id,),
        ).fetchone()
        now = store.now()
        if lease is not None and lease["generation"] != generation:
            raise ValueError("Fight participant session generation was replaced")
        if lease is not None and lease["expires_at"] > now:
            if lease["character_id"] != character["id"]:
                raise ValueError(
                    "Fight participant is no longer the selected character"
                )
        if (
            db.execute(
                "SELECT id FROM characters WHERE account_id=%s AND id=%s "
                "AND deleted_at IS NULL FOR UPDATE",
                (account_id, character["id"]),
            ).fetchone()
            is None
        ):
            raise ValueError("Disconnected fight character is unavailable")
        saved = store.character(account_id, character["id"], db)
        expected = (
            disconnected_baseline["hp"],
            disconnected_baseline["max_hp"],
            disconnected_baseline["hp_damage"],
            disconnected_baseline["health_dead"],
        )
        actual = (
            saved["hp"],
            saved["max_hp"],
            saved["hp_damage"],
            saved["health_dead"],
        )
        if actual != expected:
            raise ValueError(
                "Disconnected participant health changed since fight entry"
            )
    if (
        db.execute(
            "SELECT reason FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
            (fight.id, character["id"]),
        ).fetchone()
        is not None
    ):
        return dict(character=saved, applied=False)
    if (
        db.execute(
            "SELECT character_id FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s AND account_id=%s",
            (fight.id, character["id"], account_id),
        ).fetchone()
        is None
    ):
        raise ValueError("Missing owned durable fight participant")
    if saved["hp"] != character["hp"]:
        raise ValueError("Stale fight exit HP")
    if not 0 <= actor.hp <= actor.max_hp:
        raise ValueError("Invalid authoritative fight HP")
    from wakfu_server.equipment_stats import effective_character

    maximum = effective_character(saved)["max_hp"]
    from wakfu_server.health_policy import visible

    # Translate the fight's wound delta, rather than its temporary maximum,
    # back to the persisted configuration. Preserve pre-existing hidden wounds.
    initial_wound = character["max_hp"] - character["hp"]
    final_wound = actor.max_hp - actor.hp
    damage = max(0, saved["hp_damage"] + final_wound - initial_wound)
    dead = actor.hp == 0
    hp = visible(maximum, damage, dead)
    coefficient = 1 if hp > 0 else 0
    now = store.now()
    db.execute(
        "UPDATE characters SET hp=%s,max_hp=%s,hp_damage=%s,health_dead=%s "
        "WHERE account_id=%s AND id=%s",
        (hp, maximum, damage, dead, account_id, character["id"]),
    )
    db.execute(
        "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET "
        "initial_hp=excluded.initial_hp,started_at=excluded.started_at,coefficient=excluded.coefficient,last_at=excluded.last_at",
        (character["id"], hp, now, coefficient, now),
    )
    db.execute(
        "INSERT INTO fight_health_exits(generation,fight_id,character_id,reason,created_at,return_acknowledged_at) "
        "VALUES(%s,%s,%s,%s,%s,%s)",
        (
            generation,
            fight.id,
            character["id"],
            reason,
            now,
            now if reason == "return" else None,
        ),
    )
    from .combat_captured_roster_checkpoint import persist_departing_captured_roster

    # This is the actual owned return/abort teardown, after all lease, durable
    # membership and duplicate-receipt guards. Keep capture availability and HP
    # atomic, and load the returned character after both writes.
    persist_departing_captured_roster(db, fight, saved)
    return dict(
        character=store.character(account_id, character["id"], db),
        applied=True,
        coefficient=coefficient,
    )


def persist_aborted_fight(store, account_id, generation, character, fight):
    """Safe finally helper: damage survives disconnect; stale leases are ignored.

    Return {applied, character} on a valid/duplicate exit, otherwise None. The
    caller still releases its world/fight lease. This never grants rewards.
    """
    if character is None or fight is None or account_id is None or generation is None:
        return None
    from .fight_store import abort

    try:
        with store.connection() as db:
            # Match shared settlement/join's fight-first lock order so a stale
            # disconnect cannot hold its character while waiting behind a
            # settlement that needs to lock the fight.
            db.execute(
                "SELECT id FROM combat_fights WHERE id=%s FOR UPDATE", (fight.id,)
            ).fetchone()
            result = persist(
                store,
                account_id,
                generation,
                character,
                fight,
                reason="abort",
                db=db,
            )
            abort(
                store,
                account_id,
                character["id"],
                fight.id,
                expected_generation=generation,
                db=db,
            )
        return result
    except ValueError:
        # A replaced session cannot update health. Its old durable identity
        # can still be released without touching the current character/fight.
        abort(
            store,
            account_id,
            character["id"],
            fight.id,
            expected_generation=generation,
        )
        return None


def persist_aborted_shared_fight(
    store, shared, *, groups=None, reconnecting_session=None
):
    """Atomically persist all owners' final HP and abort a disconnected PvE fight.

    Entry health comes from the durable participant rows, not a value sampled
    at disconnect time. A disconnected generation may have no session row; the
    participant generation plus exact entry-health CAS still fences its write.
    """
    from .fight_store import abort

    fight = shared.fight
    sessions = tuple(
        sorted(
            shared.participants.values(),
            key=lambda member: (member.account_id, member.character_id),
        )
    )
    if not sessions or getattr(shared, "is_duel", False):
        raise ValueError("Shared PvE abort requires a participant roster")
    if reconnecting_session is not None:
        previous = shared.participants.get(reconnecting_session.account_id)
        if (
            previous is None
            or previous.character_id != reconnecting_session.character_id
            or previous.generation == reconnecting_session.generation
            or not store.current_character_session(
                reconnecting_session.account_id,
                reconnecting_session.generation,
                reconnecting_session.character_id,
            )
        ):
            raise ValueError("Missing current owned reconnect for shared PvE abort")
    from .combat_terminal_metadata import registered_summon_actor_ids

    summon_ids = registered_summon_actor_ids(fight)
    controlled_roster = {
        (actor.owner_id, actor.id)
        for actor in fight.actors.values()
        if actor.controlled and actor.id not in summon_ids
    }
    if controlled_roster != {
        (session.account_id, session.character_id) for session in sessions
    }:
        raise ValueError("Shared fight controlled actors do not match its roster")
    results = {}
    with store.connection() as db:
        fight_row = db.execute(
            "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE", (fight.id,)
        ).fetchone()
        if fight_row is None or fight_row["status"] not in (
            "placement",
            "active",
            "aborted",
        ):
            raise ValueError("Shared fight is not available for abort")
        durable_rows = list(
            db.execute(
                "SELECT account_id,character_id,session_generation,entry_hp,"
                "entry_max_hp,entry_hp_damage,entry_health_dead "
                "FROM combat_fight_participants WHERE fight_id=%s "
                "ORDER BY account_id,character_id FOR UPDATE",
                (fight.id,),
            )
        )
        expected_roster = {
            (session.account_id, session.character_id, session.generation)
            for session in sessions
        }
        durable_roster = {
            (row["account_id"], row["character_id"], row["session_generation"])
            for row in durable_rows
        }
        if durable_roster != expected_roster:
            raise ValueError("Shared fight roster or generation changed")
        if set(shared.connected):
            raise ValueError("Shared fight still has connected owners")

        # begin_session locks the account row before inserting/replacing the
        # sessions row. Lock every account first, in stable order, so an absent
        # session row cannot race this terminal health write.
        for account_id in sorted({session.account_id for session in sessions}):
            if (
                db.execute(
                    "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,)
                ).fetchone()
                is None
            ):
                raise ValueError("Fight participant account is unavailable")
        for session in sessions:
            lease = db.execute(
                "SELECT generation,character_id,expires_at FROM sessions "
                "WHERE account_id=%s FOR UPDATE",
                (session.account_id,),
            ).fetchone()
            replacement = (
                reconnecting_session is not None
                and reconnecting_session.account_id == session.account_id
                and reconnecting_session.character_id == session.character_id
            )
            if lease is not None and lease["generation"] != session.generation:
                if not (
                    replacement
                    and lease["generation"] == reconnecting_session.generation
                    and lease["character_id"] == reconnecting_session.character_id
                    and lease["expires_at"] > store.now()
                ):
                    raise ValueError(
                        "Fight participant session generation was replaced"
                    )
            elif replacement:
                raise ValueError(
                    "Owned reconnect lease changed during shared PvE abort"
                )
            if (
                lease is not None
                and lease["expires_at"] > store.now()
                and lease["character_id"] != session.character_id
            ):
                raise ValueError(
                    "Fight participant is no longer the selected character"
                )
        for session in sessions:
            if (
                db.execute(
                    "SELECT id FROM characters WHERE account_id=%s AND id=%s "
                    "AND deleted_at IS NULL FOR UPDATE",
                    (session.account_id, session.character_id),
                ).fetchone()
                is None
            ):
                raise ValueError("Fight participant character is unavailable")

        rows_by_identity = {
            (row["account_id"], row["character_id"]): row for row in durable_rows
        }
        if fight_row["status"] == "aborted":
            exits = {
                (row["character_id"], row["reason"])
                for row in db.execute(
                    "SELECT character_id,reason FROM fight_health_exits "
                    "WHERE fight_id=%s",
                    (fight.id,),
                )
            }
            expected_exits = {(session.character_id, "abort") for session in sessions}
            if exits == expected_exits:
                return {
                    session.character_id: dict(applied=False) for session in sessions
                }
            if reconnecting_session is None or exits:
                raise ValueError("Aborted shared fight has incomplete health receipts")

        for session in sessions:
            row = rows_by_identity[(session.account_id, session.character_id)]
            baseline = {
                "hp": row["entry_hp"],
                "max_hp": row["entry_max_hp"],
                "hp_damage": row["entry_hp_damage"],
                "health_dead": row["entry_health_dead"],
            }
            if any(value is None for value in baseline.values()):
                raise ValueError("Shared fight participant has no durable HP baseline")
            actor = fight.actors.get(session.character_id)
            if (
                actor is None
                or not actor.controlled
                or actor.owner_id != session.account_id
            ):
                raise ValueError("Shared fight actor does not match its durable owner")
            character = store.character(session.account_id, session.character_id, db)
            character.update(baseline)
            results[session.character_id] = persist(
                store,
                session.account_id,
                reconnecting_session.generation
                if reconnecting_session is not None
                and reconnecting_session.account_id == session.account_id
                else session.generation,
                character,
                fight,
                reason="abort",
                db=db,
                disconnected_baseline=baseline,
            )

        anchor = sessions[0]
        if fight_row["status"] != "aborted" and not abort(
            store,
            anchor.account_id,
            anchor.character_id,
            fight.id,
            expected_generation=anchor.generation,
            db=db,
        ):
            raise ValueError("Shared fight abort lost its participant fence")
        if shared.group_lease is not None:
            if groups is None or not groups.finish(
                shared.group_lease, defeated=False, db=db
            ):
                raise ValueError("Shared fight group lease could not be restored")
    return results


def persist_owned(
    store, account_id, generation, character, fight, *, reason="return", db=None
):
    """Persist real account PCs together under the selected main session fence."""
    if db is None:
        with store.connection() as connection:
            return persist_owned(
                store,
                account_id,
                generation,
                character,
                fight,
                reason=reason,
                db=connection,
            )
    main_id = character["id"]
    from .combat_terminal_metadata import registered_summon_actor_ids

    registrations = registered_summon_actor_ids(fight)
    identities = [main_id] + sorted(
        actor.id
        for actor in fight.actors.values()
        if actor.controlled
        and actor.owner_id == account_id
        and actor.id != main_id
        and actor.id not in registrations
    )
    results = {}
    for identity in identities:
        source = (
            character
            if identity == main_id
            else store.character(account_id, identity, db)
        )
        results[identity] = persist(
            store,
            account_id,
            generation,
            source,
            fight,
            reason=reason,
            db=db,
            session_character_id=main_id,
        )
    main = results[main_id]
    return dict(
        main,
        characters={
            identity: result["character"] for identity, result in results.items()
        },
        applied=any(result["applied"] for result in results.values()),
    )
