"""Durable single-fight rift sessions; caller owns native movement and combat."""
import json
from .rift_policy import select_wave, validate


def _setting(db, name):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (name,)).fetchone()
    if row is None:
        raise ValueError("Missing rift setting " + name)
    return row["value"]


def enter(db, wave_id, owner_character_id, members, *, seed, authorize):
    """Freeze roster/policy in the caller's movement transaction after validation.

    authorize(catalog, members) must validate native source object/proximity,
    session ownership, party scope and map access. This is never inferred here.
    """
    policy = validate(_setting(db, "rift_policy"))
    from wakfu_server.rift_native_gameplay_policy import load as native_gameplay_policy

    native_gameplay = native_gameplay_policy(db)
    if native_gameplay is not None:
        policy["native_gameplay"] = native_gameplay
    catalog = _setting(db, "rift_catalog").get(str(wave_id))
    if not policy["enabled"] or catalog is None:
        raise ValueError("Rift is unavailable")
    if catalog["type"] == "ULTIMATE_INFINITE_WAVE":
        from wakfu_server.rift_key_admission import contract

        contract(catalog)
        if policy.get("ultimate_enabled", False) is not True:
            raise ValueError("Ultimate rift key authority is disabled by policy")
    members = tuple(members)
    if (
        not members
        or len(members) > policy["max_members"]
        or len(set(members)) != len(members)
        or owner_character_id not in members
        or any(type(c) is not int or c <= 0 for c in members)
    ):
        raise ValueError("Invalid rift membership")
    known = db.execute(
        "SELECT id FROM characters WHERE id=ANY(%s)", (list(members),)
    ).fetchall()
    if {r["id"] for r in known} != set(members):
        raise ValueError("Unknown rift member")
    select_wave(catalog, policy, seed, policy["starting_wave"])
    if not callable(authorize) or authorize(catalog, members) is not True:
        raise ValueError("Native rift entry was not authorized")
    # Serialize all membership decisions, including overlapping party rosters.
    for character_id in sorted(members):
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended('rift-character:' || %s::text,0))",
            (character_id,),
        )
        row = db.execute(
            "SELECT 1 FROM rift_instances WHERE status IN('entered','running') AND members @> %s::jsonb",
            (json.dumps([character_id]),),
        ).fetchone()
        if row:
            raise ValueError("Character already belongs to an active rift")
    return db.execute(
        "INSERT INTO rift_instances(wave_definition_id,owner_character_id,members,catalog,policy,seed,wave) VALUES(%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s) RETURNING *",
        (
            wave_id,
            owner_character_id,
            json.dumps(members),
            json.dumps(catalog),
            json.dumps(policy),
            seed,
            policy["starting_wave"],
        ),
    ).fetchone()


def _run(db, instance_id):
    row = db.execute(
        "SELECT * FROM rift_instances WHERE instance_id=%s FOR UPDATE", (instance_id,)
    ).fetchone()
    if row is None:
        raise ValueError("Unknown rift instance")
    return row


def start(db, instance_id, character_id, fight_id):
    # Admission locks session/character before the run. Preserve that order for
    # paid starts; otherwise a simultaneous activator retry could deadlock.
    observed = db.execute(
        "SELECT * FROM rift_instances WHERE instance_id=%s", (instance_id,)
    ).fetchone()
    if observed is not None and observed["status"] == "entered":
        from wakfu_server.rift_key_admission import contract, lock_owner

        if contract(observed["catalog"]) is not None:
            if character_id != observed["owner_character_id"]:
                raise ValueError("Only the rift owner may start combat")
            lock_owner(db, observed, character_id, fight_id)
    run = _run(db, instance_id)
    if character_id != run["owner_character_id"]:
        raise ValueError("Only the rift owner may start combat")
    if run["status"] == "running" and run["fight_id"] == fight_id:
        return run
    if run["status"] != "entered":
        raise ValueError("Rift already started or closed")
    participants = db.execute(
        "SELECT character_id FROM combat_fight_participants WHERE fight_id=%s AND team=0",
        (fight_id,),
    ).fetchall()
    if {r["character_id"] for r in participants} != set(run["members"]):
        raise ValueError("Fight participants do not match frozen rift members")
    from wakfu_server.rift_key_admission import consume as consume_key

    consume_key(db, run, character_id, fight_id)
    return db.execute(
        "UPDATE rift_instances SET status='running',fight_id=%s,revision=revision+1 WHERE instance_id=%s RETURNING *",
        (fight_id, instance_id),
    ).fetchone()


def record_wave(db, instance_id, wave, actor_ids, *, turn):
    """Commit one defeated original wave; exclude summons before calling.

    Caller verifies that these are exactly its frozen enemy roster and all are
    dead. The adapter must persist the generated next wave in the same combat
    checkpoint transaction; a failed spawn rolls this receipt back.
    """
    run = _run(db, instance_id)
    ids = tuple(sorted(actor_ids))
    if (
        not ids
        or len(set(ids)) != len(ids)
        or any(type(i) is not int or i >= 0 for i in ids)
    ):
        raise ValueError("Invalid defeated rift roster")
    receipt = db.execute(
        "SELECT * FROM rift_wave_receipts WHERE instance_id=%s AND wave=%s",
        (instance_id, wave),
    ).fetchone()
    if receipt:
        if receipt["actor_ids"] != list(ids):
            raise ValueError("Rift wave replay changed its original roster")
        return receipt
    if (
        run["status"] != "running"
        or wave != run["wave"]
        or type(turn) is not int
        or turn < run["last_turn"]
    ):
        raise ValueError("Stale rift wave or turn")
    bound = db.execute(
        "SELECT actor_ids FROM rift_wave_rosters WHERE instance_id=%s AND wave=%s",
        (instance_id, wave),
    ).fetchone()
    if bound is None or bound["actor_ids"] != list(ids):
        raise ValueError("Defeated actors do not match authoritative rift roster")
    expected = select_wave(run["catalog"], run["policy"], run["seed"], wave)
    if len(ids) != len(expected):
        raise ValueError("Defeated roster differs from configured wave size")
    roster = select_wave(run["catalog"], run["policy"], run["seed"], wave + 1)
    db.execute(
        "UPDATE rift_instances SET wave=wave+1,completed_waves=completed_waves+1,defeated_monsters=defeated_monsters+%s,last_turn=%s,revision=revision+1 WHERE instance_id=%s",
        (len(ids), turn, instance_id),
    )
    return db.execute(
        "INSERT INTO rift_wave_receipts(instance_id,wave,actor_ids,defeated_monsters,roster) VALUES(%s,%s,%s::jsonb,%s,%s::jsonb) RETURNING *",
        (instance_id, wave, json.dumps(ids), len(ids), json.dumps(roster)),
    ).fetchone()


def settle(db, instance_id, fight_id, *, outcome, turn, apply_rewards):
    """One terminal receipt and reward callback in the combat transaction.

    No probability or prize is invented here. callback(db, run, result) owns an
    explicit local reward policy; losing/closed fights never call it.
    """
    run = _run(db, instance_id)
    if outcome not in ("won", "lost", "closed") or type(turn) is not int or turn < 0:
        raise ValueError("Invalid rift settlement")
    old = db.execute(
        "SELECT * FROM rift_settlement_receipts WHERE instance_id=%s", (instance_id,)
    ).fetchone()
    if old:
        if old["fight_id"] != fight_id or old["outcome"] != outcome:
            raise ValueError("Rift settlement replay changed result")
        return old
    if (
        run["status"] != "running"
        or run["fight_id"] != fight_id
        or turn < run["last_turn"]
    ):
        raise ValueError("Rift fight does not own settlement")
    if outcome == "won" and turn < run["policy"]["turn_budget"]:
        raise ValueError("Survival budget has not been reached")
    result = dict(
        outcome=outcome,
        completed_waves=run["completed_waves"],
        defeated_monsters=run["defeated_monsters"],
        reached_wave=run["wave"],
        turn=turn,
    )
    if outcome == "won":
        if not callable(apply_rewards):
            raise ValueError("Rift survival requires an explicit reward authority")
        apply_rewards(db, run, result)
    db.execute(
        "UPDATE rift_instances SET status=%s,last_turn=%s,ended_at=CURRENT_TIMESTAMP,revision=revision+1 WHERE instance_id=%s",
        (outcome, turn, instance_id),
    )
    return db.execute(
        "INSERT INTO rift_settlement_receipts(instance_id,fight_id,outcome,result) VALUES(%s,%s,%s,%s::jsonb) RETURNING *",
        (instance_id, fight_id, outcome, json.dumps(result)),
    ).fetchone()


def bind_wave(db, instance_id, wave, actors):
    """Freeze actual native NPC identities/ref order with the combat checkpoint.

    actors is a sequence of (actor_id, native_species_ref), supplied from the
    accepted spawn transaction, never from a player packet.
    """
    run = _run(db, instance_id)
    actors = tuple(actors)
    ids = tuple(a[0] for a in actors)
    refs = tuple(a[1] for a in actors)
    if (
        run["status"] != "running"
        or wave != run["wave"]
        or not ids
        or len(set(ids)) != len(ids)
        or any(type(a) is not int or a >= 0 for a in ids)
        or refs != select_wave(run["catalog"], run["policy"], run["seed"], wave)
    ):
        raise ValueError("Invalid authoritative rift wave roster")
    old = db.execute(
        "SELECT * FROM rift_wave_rosters WHERE instance_id=%s AND wave=%s",
        (instance_id, wave),
    ).fetchone()
    sorted_ids = sorted(ids)
    if old:
        if old["actor_ids"] != sorted_ids or old["species_refs"] != list(refs):
            raise ValueError("Rift wave identity replay changed roster")
        return old
    return db.execute(
        "INSERT INTO rift_wave_rosters(instance_id,wave,actor_ids,species_refs) VALUES(%s,%s,%s::jsonb,%s::jsonb) RETURNING *",
        (instance_id, wave, json.dumps(sorted_ids), json.dumps(refs)),
    ).fetchone()


def persist_progress(db, fight):
    """Persist acknowledged preview receipts with the caller's checkpoint.

    Keep staged receipts in the snapshot: durable receipts make reconnects and
    accepted-action retries harmless. Never invoke this on speculative previews.
    """
    state = getattr(fight, "rift_wave_state", None)
    if state is None:
        return ()
    if not isinstance(state, dict):
        raise ValueError("Malformed rift fight state")
    run = _run(db, state["instance_id"])
    if run["fight_id"] != fight.id:
        raise ValueError("Rift checkpoint belongs to another fight")
    results = []
    for staged in state.get("staged_receipts", ()):
        receipt = record_wave(
            db,
            state["instance_id"],
            staged["completed_wave"],
            staged["actor_ids"],
            turn=staged["turn"],
        )
        next_wave = staged["completed_wave"] + 1
        next_ids = tuple(staged["next_actor_ids"])
        next_refs = tuple(staged["next_species_refs"])
        if (
            list(next_refs) != receipt["roster"]
            or len(next_ids) != len(next_refs)
            or len(set(next_ids)) != len(next_ids)
        ):
            raise ValueError("Staged next rift wave differs from frozen receipt")
        bound = db.execute(
            "SELECT actor_ids,species_refs FROM rift_wave_rosters WHERE instance_id=%s AND wave=%s",
            (state["instance_id"], next_wave),
        ).fetchone()
        if bound is not None and (
            bound["actor_ids"] != sorted(next_ids)
            or bound["species_refs"] != list(next_refs)
        ):
            raise ValueError("Staged next rift roster changed its identity")
        current = _run(db, state["instance_id"])
        # An old replay may precede several later acknowledged waves. Its bound
        # roster is immutable and already verified by the existing receipt.
        if next_wave == current["wave"] and current["status"] == "running":
            bind_wave(
                db,
                state["instance_id"],
                next_wave,
                tuple(
                    zip(
                        staged["next_actor_ids"],
                        staged["next_species_refs"],
                        strict=True,
                    )
                ),
            )
        results.append(receipt)
    # A final cleared wave has no successor to admit at the turn/capacity limit.
    terminal = state.get("last_cleared_wave") or state.get("pending_wave")
    if getattr(fight, "phase", None) == "finished" and terminal is not None:
        results.append(
            record_wave(
                db,
                state["instance_id"],
                terminal["completed_wave"],
                terminal["actor_ids"],
                turn=terminal["turn"],
            )
        )
    return tuple(results)


def close_entered(db, instance_id, character_id):
    """Cancel a not-yet-started run when a frozen member leaves.

    Caller restores all members' world positions in this same transaction; a
    partial frozen party cannot start. Running fights use combat settlement.
    """
    run = _run(db, instance_id)
    if character_id not in run["members"]:
        raise ValueError("Character does not belong to this rift")
    if run["status"] == "closed" and run["fight_id"] is None:
        return run
    if run["status"] != "entered":
        raise ValueError("Started rift requires combat settlement")
    return db.execute(
        "UPDATE rift_instances SET status='closed',ended_at=CURRENT_TIMESTAMP,revision=revision+1 WHERE instance_id=%s RETURNING *",
        (instance_id,),
    ).fetchone()


def reconcile_interrupted(db):
    """Close abandoned durable fights after canonical combat startup recovery.

    Characters keep their native interior position and may use the normal exit.
    A terminal fight without a settlement receipt grants no inferred rewards.
    """
    if db.execute("SELECT 1 FROM settings WHERE name='rift_policy'").fetchone() is None:
        return ()
    return tuple(
        db.execute(
            "UPDATE rift_instances r SET status='closed',ended_at=CURRENT_TIMESTAMP,revision=revision+1 FROM combat_fights f WHERE r.fight_id=f.id AND r.status='running' AND f.status IN('aborted','finished') AND NOT EXISTS(SELECT 1 FROM rift_settlement_receipts receipt WHERE receipt.instance_id=r.instance_id) RETURNING r.*"
        ).fetchall()
    )


def abort_bound_fight(db, fight_id):
    """Close only an explicitly aborted bound fight, alongside its abort write."""
    if db.execute("SELECT 1 FROM settings WHERE name='rift_policy'").fetchone() is None:
        return None
    return db.execute(
        "UPDATE rift_instances r SET status='closed',ended_at=CURRENT_TIMESTAMP,revision=revision+1 FROM combat_fights f WHERE r.fight_id=f.id AND f.id=%s AND f.status='aborted' AND r.status='running' RETURNING r.*",
        (fight_id,),
    ).fetchone()
