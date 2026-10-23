"""Atomic, lease-scoped fight-exit HP persistence without reward side effects."""
from . import health_store, health


def _settled_level_health_baseline(db, fight, character, saved, generation, maximum):
    """Attest a reward-only maximum change without accepting newer wounds."""
    row = db.execute(
        "SELECT p.session_generation,p.entry_hp,p.entry_max_hp,p.entry_hp_damage,"
        "p.entry_health_dead,f.status AS fight_status,r.start_level,r.end_level "
        "FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "JOIN fight_rewards r ON r.fight_id=p.fight_id AND r.character_id=p.character_id "
        "AND r.account_id=p.account_id WHERE p.fight_id=%s AND p.character_id=%s "
        "AND p.account_id=%s",
        (fight.id, character["id"], saved["account_id"]),
    ).fetchone()
    if row is None:
        return None
    entry = tuple(
        row[key]
        for key in ("entry_hp", "entry_max_hp", "entry_hp_damage", "entry_health_dead")
    )
    if (
        row["session_generation"] != generation
        or row["fight_status"] != "finished"
        or any(type(value) is not int for value in entry[:3])
        or type(entry[3]) is not bool
        or type(row["start_level"]) is not int
        or type(row["end_level"]) is not int
        or row["end_level"] <= row["start_level"]
        or saved["level"] != row["end_level"]
        or not 0 < entry[1] < 2**31
        or not 0 <= entry[0] <= entry[1]
        or not 0 <= entry[2] < 2**63
    ):
        return None
    from wakfu_server.health_policy import visible

    if (
        entry[0] != visible(entry[1], entry[2], entry[3])
        or saved["max_hp"] != maximum
        or (saved["hp_damage"], saved["health_dead"]) != entry[2:]
        or saved["hp"] != visible(maximum, entry[2], entry[3])
    ):
        return None
    source = tuple(
        character.get(key) for key in ("hp", "max_hp", "hp_damage", "health_dead")
    )
    current = tuple(saved[key] for key in ("hp", "max_hp", "hp_damage", "health_dead"))
    if not (
        (source == entry and character.get("level") == row["start_level"])
        or (source == current and character.get("level") == row["end_level"])
    ):
        return None
    return entry[:2]


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
            if lease["character_id"] != (
                character["id"]
                if session_character_id is None
                else session_character_id
            ):
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
        existing = db.execute(
            "SELECT reason FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
            (fight.id, character["id"]),
        ).fetchone()
        if existing is not None:
            return dict(character=saved, applied=False)
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
    if not 0 <= actor.hp <= actor.max_hp:
        raise ValueError("Invalid authoritative fight HP")
    from wakfu_server.equipment_stats import effective_character

    maximum = effective_character(saved)["max_hp"]
    baseline = None
    if reason == "return":
        baseline = _settled_level_health_baseline(
            db, fight, character, saved, generation, maximum
        )
    if saved["hp"] != character["hp"] and baseline is None:
        raise ValueError("Stale fight exit HP")
    from wakfu_server.health_policy import visible, recover_finished_return

    # Translate the fight's wound delta, rather than its temporary maximum,
    # back to the persisted configuration. Preserve pre-existing hidden wounds.
    initial_wound = (
        character["max_hp"] - character["hp"]
        if baseline is None
        else baseline[1] - baseline[0]
    )
    final_wound = actor.max_hp - actor.hp
    damage = max(0, saved["hp_damage"] + final_wound - initial_wound)
    dead = actor.hp == 0
    if reason == "return":
        damage, dead = recover_finished_return(maximum, damage, dead)
        from wakfu_server.neo_regeneration import state_from_database

        # Finished-return fencing above owns this one full restoration. Keep
        # aborts/disconnects outside the account potion's end-of-combat grant.
        restored = state_from_database(
            db,
            dict(
                saved,
                hp=visible(maximum, damage, dead),
                max_hp=maximum,
                hp_damage=damage,
                health_dead=dead,
            ),
            native_map_id=character["map_id"],
            boundary="return",
        )
        if restored is not None:
            damage, dead = restored["hp_damage"], restored["health_dead"]
    hp = visible(maximum, damage, dead)
    from wakfu_server.equipment_hp_lifecycle import sync_fight_raw_current

    existing_hp_projection = sync_fight_raw_current(
        db,
        saved,
        actor,
        resulting_hp=hp,
        resulting_maximum=maximum,
    )
    hp_zero_valid = existing_hp_projection and hp == 0 and not dead
    now = store.now()
    db.execute(
        "UPDATE characters SET hp=%s,max_hp=%s,hp_damage=%s,health_dead=%s,hp_zero_valid=%s "
        "WHERE account_id=%s AND id=%s",
        (hp, maximum, damage, dead, hp_zero_valid, account_id, character["id"]),
    )
    if existing_hp_projection:
        from wakfu_server.equipment_hp_lifecycle import rebase_after_fight

        rebased = rebase_after_fight(
            db,
            dict(
                saved,
                hp=hp,
                max_hp=maximum,
                hp_damage=damage,
                health_dead=dead,
                hp_zero_valid=hp_zero_valid,
            ),
            actor,
        )
        if rebased is not None:
            hp = rebased["character"]["hp"]
            maximum = rebased["character"]["max_hp"]
            damage = rebased["character"]["hp_damage"]
            dead = rebased["character"]["health_dead"]
    coefficient = health.exploration_coefficient(maximum, hp)
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
    from .combat_consumable_lifecycle import return_participant

    return_fight = fight
    captured_external = ()
    if reason == "return" and getattr(fight, "native_external_state_origins", None):
        from copy import copy
        from .combat_external_retained_state import capture_all

        # Only the return binding map is changed. Actors, native ledgers and
        # origins are read-only; SQL rollback discards this private binding map.
        return_fight = copy(fight)
        captured_external = capture_all(
            store,
            db,
            account_id,
            generation,
            character["id"],
            return_fight,
        )
    return_participant(store, db, character["id"], return_fight, generation=generation)
    returned = store.character(account_id, character["id"], db)
    if any(row is not None for row in captured_external):
        from wakfu_server.consumable_characteristics import reconcile_health

        returned = reconcile_health(db, returned)
        coefficient = health.exploration_coefficient(returned["max_hp"], returned["hp"])
        db.execute(
            "UPDATE character_regeneration SET coefficient=%s WHERE character_id=%s",
            (coefficient, character["id"]),
        )
    return dict(
        character=returned,
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
    store,
    shared,
    *,
    groups=None,
    reconnecting_session=None,
    requesting_session=None,
    db=None,
):
    """Atomically persist all owners' final HP and abort a disconnected PvE fight.

    Entry health comes from the durable participant rows, not a value sampled
    at disconnect time. A disconnected generation may have no session row; the
    participant generation plus exact entry-health CAS still fences its write.
    """
    from .fight_store import abort
    from contextlib import nullcontext

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

    from .combat_companions import registered_companion_ids

    summon_ids = registered_summon_actor_ids(fight) | registered_companion_ids(fight)
    controlled_roster = {
        (actor.owner_id, actor.id)
        for actor in fight.actors.values()
        if actor.controlled and actor.id not in summon_ids
    }
    sessions_by_account = {session.account_id: session for session in sessions}
    if (
        len(sessions_by_account) != len(sessions)
        or any(owner not in sessions_by_account for owner, _ in controlled_roster)
        or any(
            (session.account_id, session.character_id) not in controlled_roster
            for session in sessions
        )
    ):
        raise ValueError("Shared fight controlled actors do not match its roster")
    if requesting_session is not None:
        from .combat_pve_withdraw import live_owner_accounts

        if (
            reconnecting_session is not None
            or shared.participants.get(requesting_session.account_id)
            != requesting_session
            or requesting_session.account_id not in shared.connected
            or live_owner_accounts(fight) - {requesting_session.account_id}
        ):
            raise ValueError(
                "Explicit shared abort requires the final live owned session"
            )
    results = {}
    with store.connection() if db is None else nullcontext(db) as db:
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
        certified_returned = set()
        if requesting_session is not None:
            exits = {
                row["character_id"]: row
                for row in db.execute(
                    "SELECT e.character_id,e.reason,e.return_acknowledged_at,w.returned_at, "
                    "w.character_id AS withdrawn_id,w.account_id AS withdrawn_account, "
                    "w.session_generation AS withdrawn_generation "
                    "FROM fight_health_exits e LEFT JOIN combat_pve_withdrawals w "
                    "ON w.fight_id=e.fight_id AND w.character_id=e.character_id "
                    "WHERE e.fight_id=%s FOR UPDATE OF e",
                    (fight.id,),
                )
            }
            for owner in set(shared.returned) | set(shared.withdrawals):
                actors = [
                    fight.actors[identity]
                    for account, identity in controlled_roster
                    if account == owner
                ]
                if not actors or any(
                    not getattr(actor, "pve_withdrawn", False) for actor in actors
                ):
                    raise ValueError("Returned shared owner lacks native retirement")
                receipt = shared.withdrawals.get(owner)
                for actor in actors:
                    row = exits.get(actor.id)
                    if row is None:
                        raise ValueError(
                            "Retired shared owner lacks durable health exit"
                        )
                    if receipt is not None:
                        if (
                            row["reason"] != "abort"
                            or row["withdrawn_id"] != actor.id
                            or row["withdrawn_account"] != owner
                            or row["withdrawn_generation"]
                            != receipt["session"].generation
                        ):
                            raise ValueError(
                                "Retired shared owner lacks its owned native continuation"
                            )
                    elif (
                        row["return_acknowledged_at"] is None
                        and row["returned_at"] is None
                    ):
                        raise ValueError(
                            "Returned shared owner lacks durable native return"
                        )
                certified_returned.add(owner)
        frozen_generations = {
            (row["account_id"], row["character_id"]): row["session_generation"]
            for row in durable_rows
        }
        expected_roster = {
            (
                owner,
                identity,
                frozen_generations.get((owner, identity))
                if owner in certified_returned
                else sessions_by_account[owner].generation,
            )
            for owner, identity in controlled_roster
        }
        durable_roster = {
            (row["account_id"], row["character_id"], row["session_generation"])
            for row in durable_rows
        }
        if durable_roster != expected_roster:
            raise ValueError("Shared fight roster or generation changed")
        if set(shared.connected) and requesting_session is None:
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
            if session.account_id in certified_returned:
                continue  # Durable historical return cannot rewrite a newer selected character.
            lease = db.execute(
                "SELECT generation,character_id,expires_at FROM sessions "
                "WHERE account_id=%s FOR UPDATE",
                (session.account_id,),
            ).fetchone()
            if session == requesting_session and (
                lease is None
                or lease["generation"] != session.generation
                or lease["character_id"] != session.character_id
                or lease["expires_at"] <= store.now()
            ):
                raise ValueError("Explicit shared abort requester lease changed")
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
        for owner, identity in sorted(controlled_roster):
            if owner in certified_returned:
                continue
            if (
                db.execute(
                    "SELECT id FROM characters WHERE account_id=%s AND id=%s "
                    "AND deleted_at IS NULL FOR UPDATE",
                    (owner, identity),
                ).fetchone()
                is None
            ):
                raise ValueError("Fight participant character is unavailable")

        rows_by_identity = {
            (row["account_id"], row["character_id"]): row for row in durable_rows
        }
        if fight_row["status"] == "aborted" and requesting_session is not None:
            raise ValueError(
                "Explicit abort already committed; owned continuation required"
            )
        if fight_row["status"] == "aborted":
            exits = {
                (row["character_id"], row["reason"])
                for row in db.execute(
                    "SELECT character_id,reason FROM fight_health_exits "
                    "WHERE fight_id=%s",
                    (fight.id,),
                )
            }
            expected_exits = {(identity, "abort") for _, identity in controlled_roster}
            if exits == expected_exits:
                return {
                    identity: dict(applied=False) for _, identity in controlled_roster
                }
            if reconnecting_session is None or exits:
                raise ValueError("Aborted shared fight has incomplete health receipts")

        for owner, identity in sorted(controlled_roster):
            if owner in certified_returned:
                results[identity] = dict(applied=False)
                continue
            session = sessions_by_account[owner]
            row = rows_by_identity[(owner, identity)]
            baseline = {
                "hp": row["entry_hp"],
                "max_hp": row["entry_max_hp"],
                "hp_damage": row["entry_hp_damage"],
                "health_dead": row["entry_health_dead"],
            }
            if any(value is None for value in baseline.values()):
                raise ValueError("Shared fight participant has no durable HP baseline")
            actor = fight.actors.get(identity)
            if (
                actor is None
                or not actor.controlled
                or actor.owner_id != session.account_id
            ):
                raise ValueError("Shared fight actor does not match its durable owner")
            character = store.character(owner, identity, db)
            character.update(baseline)
            results[identity] = persist(
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
                session_character_id=session.character_id,
            )

        from wakfu_server.characters.companions import settle_owner_exit

        for owner in sorted(sessions_by_account):
            settle_owner_exit(db, store, fight, owner)
        anchor = requesting_session if requesting_session is not None else sessions[0]
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

    from .combat_companions import registered_companion_ids

    registrations = registered_summon_actor_ids(fight) | registered_companion_ids(fight)
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
    if reason == "abort":
        from wakfu_server.characters.companions import settle_owner_exit

        settle_owner_exit(db, store, fight, account_id)
    main = results[main_id]
    return dict(
        main,
        characters={
            identity: result["character"] for identity, result in results.items()
        },
        applied=any(result["applied"] for result in results.values()),
    )
