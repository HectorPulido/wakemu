"""PostgreSQL fight identities and owned durable participants."""

from psycopg.pq import TransactionStatus


def _require_transaction(db):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Fight membership requires an active transaction")


def _health_baseline(db, account_id, character_id):
    row = db.execute(
        "SELECT id,account_id,map_id,hp,max_hp,hp_damage,health_dead FROM characters "
        "WHERE account_id=%s AND id=%s AND deleted_at IS NULL FOR UPDATE",
        (account_id, character_id),
    ).fetchone()
    if row is None:
        raise ValueError("Fight participant character is unavailable")
    from wakfu_server.neo_regeneration import restore_entry_baseline

    row = restore_entry_baseline(db, dict(row))
    hp, maximum, damage, dead = (
        row["hp"],
        row["max_hp"],
        row["hp_damage"],
        row["health_dead"],
    )
    if (
        any(type(value) is not int for value in (hp, maximum, damage))
        or type(dead) is not bool
        or maximum <= 0
        or not 0 <= hp <= maximum
        or damage < 0
    ):
        raise ValueError("Invalid fight participant health baseline")
    return hp, maximum, damage, dead


def create(store, account_id, generation, character_id, *, team=0, on_created=None):
    if type(team) is not int or team not in (0, 1):
        raise ValueError("Invalid fight participant team")
    if on_created is not None and not callable(on_created):
        raise ValueError("Fight creation callback must be callable")
    with store.connection() as db:
        # Roster and selected-character mutations use account-before-session.
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character_id)
        baseline = _health_baseline(db, account_id, character_id)
        fight_id = db.execute(
            "INSERT INTO combat_fights(status) VALUES('placement') RETURNING id"
        ).fetchone()["id"]
        db.execute(
            "INSERT INTO combat_fight_participants"
            "(fight_id,character_id,account_id,team,session_generation,"
            "entry_hp,entry_max_hp,entry_hp_damage,entry_health_dead) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (fight_id, character_id, account_id, team, generation, *baseline),
        )
        from .combat_consumable_lifecycle import enter_participant

        enter_participant(store, db, character_id, fight_id, generation=generation)
        if on_created is not None:
            on_created(db, fight_id)
        return fight_id


def join_participant(
    store,
    db,
    account_id,
    generation,
    character_id,
    fight_id,
    *,
    target_character_id,
    team,
):
    """Persist one admitted player in an existing placement fight.

    Network/map/team/cell admission belongs to the shared fight registry. This
    storage boundary rechecks the live selected-character lease, the target's
    durable membership, same-team placement phase, and idempotent identity.
    """
    _require_transaction(db)
    if (
        type(team) is not int
        or team not in (0, 1)
        or type(fight_id) is not int
        or not 0 < fight_id < 2**31
        or type(target_character_id) is not int
        or target_character_id <= 0
    ):
        raise ValueError("Invalid shared fight participant")
    fight = db.execute(
        "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE", (fight_id,)
    ).fetchone()
    if fight is None or fight["status"] != "placement":
        raise ValueError("Fight is not open for participant admission")
    store.lock_character(db, account_id, generation, character_id)
    baseline = _health_baseline(db, account_id, character_id)
    target = db.execute(
        "SELECT account_id,team FROM combat_fight_participants "
        "WHERE fight_id=%s AND character_id=%s FOR UPDATE",
        (fight_id, target_character_id),
    ).fetchone()
    if target is None or target["team"] != team:
        raise ValueError("Join target is not a durable same-team participant")
    if target["account_id"] == account_id:
        raise ValueError("Account already owns a fight participant")

    prior = db.execute(
        "SELECT fight_id,account_id,team,session_generation "
        "FROM combat_fight_participants WHERE character_id=%s "
        "AND fight_id=%s FOR UPDATE",
        (character_id, fight_id),
    ).fetchone()
    if prior is not None:
        if (
            prior["account_id"] == account_id
            and prior["team"] == team
            and prior["session_generation"] == generation
        ):
            return False
        raise ValueError("Conflicting durable fight participant")
    if db.execute(
        "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=%s AND f.status IN ('placement','active') "
        "AND NOT EXISTS(SELECT 1 FROM combat_pve_withdrawals w "
        "WHERE w.fight_id=p.fight_id AND w.character_id=p.character_id) LIMIT 1",
        (character_id,),
    ).fetchone():
        raise ValueError("Character already has an active durable fight")
    if db.execute(
        "SELECT 1 FROM combat_fight_participants WHERE fight_id=%s AND account_id=%s LIMIT 1",
        (fight_id, account_id),
    ).fetchone():
        raise ValueError("Account already owns a fight participant")
    db.execute(
        "INSERT INTO combat_fight_participants"
        "(fight_id,character_id,account_id,team,session_generation,"
        "entry_hp,entry_max_hp,entry_hp_damage,entry_health_dead) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (fight_id, character_id, account_id, team, generation, *baseline),
    )
    from .combat_consumable_lifecycle import enter_participant

    enter_participant(store, db, character_id, fight_id, generation=generation)
    return True


def finish(store, db, account_id, generation, character_id, fight_id):
    _require_transaction(db)
    row = db.execute(
        "SELECT f.status,p.session_generation FROM combat_fights f JOIN combat_fight_participants p ON p.fight_id=f.id "
        "WHERE f.id=%s AND p.character_id=%s AND p.account_id=%s FOR UPDATE OF f",
        (fight_id, character_id, account_id),
    ).fetchone()
    if (
        row is None
        or row["status"] == "aborted"
        or row["session_generation"] not in (None, generation)
    ):
        raise ValueError("Missing or aborted owned durable fight")
    store.lock_character(db, account_id, generation, character_id)
    db.execute("UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,))


def settle_shared(
    store, account_id, generation, character_id, fight, settle, *, trace=None
):
    """Commit one shared result and all owner settlements atomically.

    Only the current lease of the finalizer is required. Other owners are
    authorized by their durable participant rows and recorded join generation,
    so a disconnected teammate does not lose a committed reward. ``settle`` is
    a trusted storage callback receiving ``(db, participant_rows, fight)`` and
    must apply all participant receipts using this same transaction.
    """
    if (
        not callable(settle)
        or getattr(fight, "phase", None) != "finished"
        or getattr(fight, "winner", None) not in (0, 1)
        or type(getattr(fight, "id", None)) is not int
        or not 0 < fight.id < 2**31
    ):
        raise ValueError("Invalid shared fight settlement")
    from .combat_terminal_metadata import registered_summon_actor_ids

    from .combat_companions import registered_companion_ids

    summon_ids = registered_summon_actor_ids(fight) | registered_companion_ids(fight)
    controlled = {
        actor.id: actor.owner_id
        for actor in fight.actors.values()
        if actor.controlled and actor.id not in summon_ids
    }
    if (
        not controlled
        or character_id not in controlled
        or controlled[character_id] != account_id
    ):
        raise ValueError("Finalizer is not a fight participant")
    from .fight_checkpoint_store import _trace_stage
    import time

    started = time.monotonic()
    _trace_stage(trace, "pool_wait", fight.id, operation="settle")
    with store.connection() as db:
        _trace_stage(
            trace,
            "pool_acquired",
            fight.id,
            operation="settle",
            elapsed_ms=(time.monotonic() - started) * 1000,
        )
        started = time.monotonic()
        _trace_stage(trace, "fight_lock_started", fight.id, operation="settle")
        fight_row = db.execute(
            "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE", (fight.id,)
        ).fetchone()
        _trace_stage(
            trace,
            "fight_lock_finished",
            fight.id,
            operation="settle",
            elapsed_ms=(time.monotonic() - started) * 1000,
        )
        if fight_row is None or fight_row["status"] not in (
            "placement",
            "active",
            "finished",
        ):
            raise ValueError("Shared fight is missing or terminal-aborted")
        started = time.monotonic()
        _trace_stage(trace, "participant_locks_started", fight.id, operation="settle")
        finalizer = db.execute(
            "SELECT session_generation FROM combat_fight_participants "
            "WHERE fight_id=%s AND character_id=%s AND account_id=%s FOR UPDATE",
            (fight.id, character_id, account_id),
        ).fetchone()
        if finalizer is None or finalizer["session_generation"] != generation:
            raise ValueError("Finalizer no longer owns the durable fight lease")
        store.lock_character(db, account_id, generation, character_id)
        rows = tuple(
            db.execute(
                "SELECT p.character_id,p.account_id,p.team,p.session_generation,"
                "EXISTS(SELECT 1 FROM combat_pve_withdrawals w WHERE "
                "w.fight_id=p.fight_id AND w.character_id=p.character_id) AS withdrawn "
                "FROM combat_fight_participants p WHERE p.fight_id=%s "
                "ORDER BY p.character_id FOR UPDATE OF p",
                (fight.id,),
            )
        )
        for row in rows:
            locked = db.execute(
                "SELECT id FROM characters WHERE id=%s AND account_id=%s "
                "AND deleted_at IS NULL FOR UPDATE",
                (row["character_id"], row["account_id"]),
            ).fetchone()
            if locked is None:
                raise ValueError("Shared fight participant character is unavailable")
        durable = {row["character_id"]: row["account_id"] for row in rows}
        if durable != controlled:
            raise ValueError("Runtime and durable shared fight rosters differ")
        by_id = {actor.id: actor for actor in fight.actors.values()}
        if any(
            row["team"] != by_id[row["character_id"]].team
            or row["session_generation"] is None
            for row in rows
        ):
            raise ValueError("Shared fight participant authority is incomplete")
        if fight_row["status"] != "finished":
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s",
                (fight.id,),
            )
        _trace_stage(
            trace,
            "participant_locks_finished",
            fight.id,
            operation="settle",
            elapsed_ms=(time.monotonic() - started) * 1000,
        )
        started = time.monotonic()
        _trace_stage(trace, "award_callback_started", fight.id, operation="settle")
        from wakfu_server.combat_reward_ownership import _durable_settlement_scope

        # The finalizer lease, exact runtime/durable roster and all character
        # locks above authorize this transaction's earned offline-peer loot.
        with _durable_settlement_scope(db, fight, rows):
            packets = settle(db, rows, fight)
            from wakfu_server.characters.companions import settle_rewards

            settle_rewards(db, store, fight)
            from wakfu_server.custom_tasks.external import enabled as objectives_enabled

            if objectives_enabled():
                from wakfu_server.objectives.challenges import settle_fight

                # The finished fight, normal rewards and private challenge receipt
                # commit together. Replays retain the original attempt and score.
                settle_fight(db, fight)
        _trace_stage(
            trace,
            "award_callback_finished",
            fight.id,
            operation="settle",
            elapsed_ms=(time.monotonic() - started) * 1000,
        )
        started = time.monotonic()
        _trace_stage(trace, "terminal_snapshot_started", fight.id, operation="settle")
        _write_terminal_checkpoint(db, store, account_id, generation, fight)
        _trace_stage(
            trace,
            "terminal_snapshot_finished",
            fight.id,
            operation="settle",
            elapsed_ms=(time.monotonic() - started) * 1000,
        )
        return packets


def _write_terminal_checkpoint(db, store, account_id, generation, fight):
    """Commit a terminal snapshot with settlement so restart recovery is safe."""
    from psycopg.types.json import Jsonb
    from .fight_checkpoint_store import snapshot

    if getattr(fight, "phase", None) != "finished":
        raise ValueError("Terminal checkpoint requires a finished fight")
    from .combat_consumable_handoff import persist as persist_consumable_handoff

    persist_consumable_handoff(store, db, fight)
    state = snapshot(fight)
    row = db.execute(
        "SELECT revision,status FROM fight_checkpoints WHERE fight_id=%s FOR UPDATE",
        (fight.id,),
    ).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO fight_checkpoints"
            "(fight_id,account_id,generation,revision,status,snapshot,updated_at) "
            "VALUES(%s,%s,%s,1,'ended',%s,%s)",
            (fight.id, account_id, generation, Jsonb(state), store.now()),
        )
        return
    db.execute(
        "UPDATE fight_checkpoints SET account_id=%s,generation=%s,"
        "revision=revision+1,status='ended',snapshot=%s,updated_at=%s "
        "WHERE fight_id=%s AND revision=%s",
        (
            account_id,
            generation,
            Jsonb(state),
            store.now(),
            fight.id,
            row["revision"],
        ),
    )


def recoverable_finished_fight(store, account_id, character_id):
    """Find a terminal PvE identity safe to recover after a process restart.

    Only settlement-time terminal checkpoints qualify. An old active snapshot
    cannot supply final actor HP after the in-memory runtime has been lost.
    The actual recovery rechecks and locks every condition transactionally.
    """
    with store.connection() as db:
        rows = tuple(
            db.execute(
                "SELECT f.id,p.session_generation FROM combat_fights f "
                "JOIN combat_fight_participants p ON p.fight_id=f.id "
                "JOIN fight_checkpoints c ON c.fight_id=f.id "
                "WHERE f.status='finished' AND f.fight_kind='pve' "
                "AND p.account_id=%s AND p.character_id=%s "
                "AND c.status IN ('active','ended','aborted') "
                "AND c.snapshot->>'phase'='finished' "
                "AND NOT EXISTS(SELECT 1 FROM fight_health_exits e "
                "WHERE e.fight_id=f.id AND e.character_id=p.character_id "
                "AND (e.reason<>'return' OR e.return_acknowledged_at IS NOT NULL)) "
                "AND NOT EXISTS(SELECT 1 FROM combat_fight_participants p2 "
                "JOIN combat_fights f2 ON f2.id=p2.fight_id "
                "WHERE p2.character_id=p.character_id "
                "AND f2.status IN ('placement','active')) "
                "ORDER BY f.id DESC LIMIT 2",
                (account_id, character_id),
            )
        )
        if len(rows) > 1:
            raise ValueError("Multiple unreturned terminal fights require review")
        return (
            None
            if not rows
            else dict(
                fight_id=rows[0]["id"],
                previous_generation=rows[0]["session_generation"],
            )
        )


def activate(store, account_id, generation, character_id, fight_id):
    with store.connection() as db:
        row = db.execute(
            "SELECT status FROM combat_fights WHERE id=%s FOR UPDATE", (fight_id,)
        ).fetchone()
        if row is None or row["status"] not in ("placement", "active"):
            raise ValueError("Missing or terminal owned durable fight")
        store.lock_character(db, account_id, generation, character_id)
        result = db.execute(
            "UPDATE combat_fights f SET status='active' FROM combat_fight_participants p "
            "WHERE f.id=p.fight_id AND f.id=%s AND p.character_id=%s AND p.account_id=%s "
            "AND f.status IN ('placement','active') "
            "AND (p.session_generation IS NULL OR p.session_generation=%s)",
            (fight_id, character_id, account_id, generation),
        )
        if result.rowcount != 1:
            raise ValueError("Missing or terminal owned durable fight")


def takeover_participant(
    store,
    account_id,
    generation,
    character_id,
    fight_id,
    *,
    previous_generation,
):
    """Fence the owner's frozen main and hero memberships onto one lease."""
    if not isinstance(previous_generation, str) or not previous_generation:
        raise ValueError("Invalid previous combat participant generation")
    with store.connection() as db:
        row = db.execute(
            "SELECT f.status,p.session_generation,"
            "EXISTS(SELECT 1 FROM fight_health_exits e "
            "WHERE e.fight_id=f.id AND e.character_id=p.character_id "
            "AND e.return_acknowledged_at IS NOT NULL) AS return_acknowledged "
            "FROM combat_fights f "
            "JOIN combat_fight_participants p ON p.fight_id=f.id "
            "WHERE f.id=%s AND p.character_id=%s AND p.account_id=%s FOR UPDATE OF f,p",
            (fight_id, character_id, account_id),
        ).fetchone()
        if row is None or row["status"] not in ("placement", "active", "finished"):
            raise ValueError("Fight participant is unavailable for takeover")
        if row["status"] == "finished" and row["return_acknowledged"]:
            raise ValueError("Finished fight participant already acknowledged return")
        store.lock_character(db, account_id, generation, character_id)
        if row["session_generation"] not in (previous_generation, generation):
            raise ValueError("Stale durable combat participant generation")
        return _takeover_account_memberships(
            db, fight_id, account_id, generation, previous_generation
        )


def _takeover_account_memberships(
    db, fight_id, account_id, generation, previous_generation
):
    """Keep every frozen hero behind the same validated selected-main lease."""
    members = db.execute(
        "SELECT character_id,session_generation FROM combat_fight_participants "
        "WHERE fight_id=%s AND account_id=%s ORDER BY character_id FOR UPDATE",
        (fight_id, account_id),
    ).fetchall()
    if not members or any(
        member["session_generation"] not in (previous_generation, generation)
        for member in members
    ):
        raise ValueError("Stale durable account combat participant generation")
    changed = any(member["session_generation"] != generation for member in members)
    if changed:
        db.execute(
            "UPDATE combat_fight_participants SET session_generation=%s "
            "WHERE fight_id=%s AND account_id=%s AND session_generation=%s",
            (generation, fight_id, account_id, previous_generation),
        )
    return changed


def recover_finished_return(
    store,
    account_id,
    generation,
    character_id,
    fight,
    character,
    *,
    previous_generation,
    fight_id=None,
):
    """Persist an idempotent PvE return after a fresh world bootstrap.

    Rewards are already settled. This only advances the participant fence and
    records or reuses its return-health receipt in the same transaction.
    """
    recovered_from_checkpoint = fight is None
    fight_id = getattr(fight, "id", None) if fight_id is None else fight_id
    if (
        not isinstance(previous_generation, str)
        or not previous_generation
        or type(fight_id) is not int
        or fight_id <= 0
        or not isinstance(character, dict)
        or character.get("id") != character_id
    ):
        raise ValueError("Invalid settled-fight recovery identity")
    with store.connection() as db:
        row = db.execute(
            "SELECT f.status,f.fight_kind,p.session_generation,"
            "c.status AS checkpoint_status,c.revision AS checkpoint_revision,"
            "c.snapshot AS checkpoint_snapshot "
            "FROM combat_fights f "
            "JOIN combat_fight_participants p ON p.fight_id=f.id "
            "JOIN fight_checkpoints c ON c.fight_id=f.id "
            "WHERE f.id=%s AND p.character_id=%s AND p.account_id=%s "
            "FOR UPDATE OF f,p,c",
            (fight_id, character_id, account_id),
        ).fetchone()
        if row is None or row["fight_kind"] != "pve" or row["status"] != "finished":
            raise ValueError("Fight is not durably settled for world recovery")
        if row["checkpoint_status"] not in ("active", "ended", "aborted"):
            raise ValueError("Fight checkpoint is not recoverable")
        from .fight_checkpoint_store import Checkpoints

        checkpoint_state = Checkpoints._read_snapshot(row["checkpoint_snapshot"])
        terminal_snapshot = checkpoint_state.get("phase") == "finished"
        if row["checkpoint_status"] == "aborted" and not terminal_snapshot:
            raise ValueError("Aborted checkpoint has no durable terminal snapshot")
        if fight is None:
            if not terminal_snapshot:
                raise ValueError("No durable terminal fight snapshot is available")
            from types import SimpleNamespace

            actors = {}
            for identity, actor_state in checkpoint_state.get("actors", {}).items():
                try:
                    actor_id = int(identity)
                    actors[actor_id] = SimpleNamespace(
                        id=actor_id,
                        controlled=actor_state["controlled"],
                        owner_id=actor_state.get("owner_id"),
                        hp=actor_state["hp"],
                        max_hp=actor_state["max_hp"],
                    )
                except (KeyError, TypeError, ValueError):
                    raise ValueError("Malformed terminal actor snapshot") from None
            fight = SimpleNamespace(
                id=fight_id,
                phase="finished",
                actors=actors,
            )
            from .combat_consumable_states import restore_checkpoint_projection

            restore_checkpoint_projection(fight, checkpoint_state)
        elif (
            getattr(fight, "id", None) != fight_id
            or getattr(fight, "phase", None) != "finished"
        ):
            raise ValueError("Runtime fight does not match durable terminal identity")
        actor = fight.actors.get(character_id)
        if (
            actor is None
            or not actor.controlled
            or actor.owner_id != account_id
            or type(actor.hp) is not int
            or type(actor.max_hp) is not int
        ):
            raise ValueError("Settled-fight recovery actor is not owned")
        # The settlement transaction commits fight status plus this terminal
        # snapshot. Do not infer successful settlement from rewards: a valid
        # loss or NPC victory may award no player a reward.
        if row["session_generation"] not in (previous_generation, generation):
            raise ValueError("Stale settled-fight participant generation")
        store.lock_character(db, account_id, generation, character_id)
        existing_exit = db.execute(
            "SELECT reason FROM fight_health_exits "
            "WHERE fight_id=%s AND character_id=%s FOR UPDATE",
            (fight.id, character_id),
        ).fetchone()
        if existing_exit is not None and existing_exit["reason"] not in (
            "return",
            "abort",
        ):
            raise ValueError("Settled fight has an unknown health exit")
        if (
            existing_exit is not None
            and existing_exit["reason"] == "abort"
            and not terminal_snapshot
        ):
            raise ValueError("Abort health recovery requires a terminal checkpoint")
        # A disconnect can persist its owned abort health receipt after the
        # terminal settlement commits but before native UI return. The durable
        # finished/checkpoint/lease checks above still fence this recovery.
        # persist_owned reuses that receipt and current canonical HP verbatim;
        # do not apply wounds again, revive, or rewrite abort provenance.
        _takeover_account_memberships(
            db, fight.id, account_id, generation, previous_generation
        )
        if row["checkpoint_status"] != "ended" or not terminal_snapshot:
            from .fight_checkpoint_store import snapshot
            from psycopg.types.json import Jsonb

            closed = db.execute(
                "UPDATE fight_checkpoints SET account_id=%s,generation=%s,"
                "revision=revision+1,status='ended',snapshot=%s,updated_at=%s "
                "WHERE fight_id=%s AND revision=%s AND status=%s",
                (
                    account_id,
                    generation,
                    Jsonb(snapshot(fight)),
                    store.now(),
                    fight.id,
                    row["checkpoint_revision"],
                    row["checkpoint_status"],
                ),
            )
            if closed.rowcount != 1:
                raise ValueError("Stale active checkpoint during terminal recovery")
        from .combat_health import persist_owned as persist_health

        exit_result = persist_health(
            store,
            account_id,
            generation,
            character,
            fight,
            reason="return",
            db=db,
        )
        return {
            **exit_result,
            "fight": fight,
            "recovered_from_checkpoint": recovered_from_checkpoint,
        }


def abort(
    store,
    account_id,
    character_id,
    fight_id,
    *,
    expected_generation=None,
    db=None,
    on_aborted=None,
):
    """Cleanup only this durable identity; never mutate character or finished fight."""
    if on_aborted is not None and not callable(on_aborted):
        raise ValueError("Fight abort callback must be callable")
    if db is None:
        with store.connection() as connection:
            return abort(
                store,
                account_id,
                character_id,
                fight_id,
                expected_generation=expected_generation,
                db=connection,
                on_aborted=on_aborted,
            )
    from psycopg.pq import TransactionStatus

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Fight abort requires an active transaction")
    query = (
        "UPDATE combat_fights f SET status='aborted' FROM combat_fight_participants p "
        "WHERE f.id=p.fight_id AND f.id=%s AND p.character_id=%s AND p.account_id=%s "
        "AND f.status IN ('placement','active')"
    )
    params = [fight_id, character_id, account_id]
    if expected_generation is not None:
        # NULL rows are legacy participants with no generation fence. Once a
        # takeover writes a concrete newer generation, an old finalizer cannot
        # abort that live owner's fight.
        query += " AND (p.session_generation IS NULL OR p.session_generation=%s)"
        params.append(expected_generation)
    applied = db.execute(query, tuple(params)).rowcount == 1
    if applied:
        from wakfu_server.rift_runtime import abort_bound_fight

        abort_bound_fight(db, fight_id)
        if on_aborted is not None:
            on_aborted(db, fight_id)
    return applied
