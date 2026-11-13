"""Durable relocation to the native floor for reconstructed Rii lessons.

Airyna stands on a six-cell elevated component, unsuitable for area and
line-of-sight lessons. Moving to the native dojo floor and back is a local
reconstruction; the original server's transition has not been recovered.
The caller owns the position barrier and publishes the normal map transition
bootstrap after commit. Never call while a fight or private scene is active.
"""

MAP_ID = 1388
FLOOR = {"map_id": MAP_ID, "instance_id": 0, "x": 0, "y": -16, "z": 0}
FLOOR_CELLS = (
    (0, -16, 0),
    (1, -16, 0),
    (-1, -16, 0),
    (0, -15, 0),
    (1, -15, 0),
    (-1, -15, 0),
    (0, -14, 0),
    (1, -14, 0),
    (-1, -14, 0),
)
OBJECTIVES = frozenset({10608, 10609, 10610, 10611})
POSITION = ("map_id", "instance_id", "x", "y", "z")


def pending(store, account_id, character_id):
    """Check for a saved return before paying the cost of a scene snapshot."""
    with store.connection() as db:
        return (
            db.execute(
                "SELECT 1 FROM rii_training_transits WHERE account_id=%s AND character_id=%s",
                (account_id, character_id),
            ).fetchone()
            is not None
        )


def stage(
    enter_floor,
    producer,
    return_source,
    publish_floor,
    attach_source,
    mark_failed,
    setup_is_ready,
):
    """Publish only the committed location after preparing an owned scene.

    The caller serializes the position owner and supplies authoritative actions.
    If preparing the encounter fails, a deferred return still needs a floor
    bootstrap so in-memory and client positions match durable storage.
    """
    moved = enter_floor()
    try:
        scene = producer(moved)
        if scene is None:
            raise ValueError("Training encounter could not be prepared")
    except Exception as original:
        try:
            ready = setup_is_ready(moved)
        except Exception as error:
            # A producer commit may have succeeded even if its connection
            # failed while acknowledging it. Never rewrite an unknown receipt.
            original.add_note(f"Training setup status failed: {type(error).__name__}")
            try:
                publish_floor(moved)
            except Exception as publication_error:
                original.add_note(
                    f"Training position publication failed: {type(publication_error).__name__}"
                )
            raise
        if ready:
            # Its owned group and ready receipt committed together. Recovery
            # must keep the player with that group, not create an orphan.
            try:
                publish_floor(moved)
            except Exception as error:
                original.add_note(
                    f"Training position publication failed: {type(error).__name__}"
                )
            raise
        # A new transit is already recoverable even if marking fails. Try the
        # return independently and preserve the original setup exception.
        try:
            mark_failed(moved)
        except Exception as error:
            original.add_note(f"Training failure marker failed: {type(error).__name__}")
        try:
            returned = return_source(moved)
        except Exception as error:
            original.add_note(f"Training return failed: {type(error).__name__}")
            returned = None
        try:
            if returned is None:
                publish_floor(moved)
            else:
                attach_source(returned)
        except Exception as error:
            original.add_note(
                f"Training position publication failed: {type(error).__name__}"
            )
        raise
    publish_floor(moved)
    return scene


def _validate_scene(character):
    if (character.get("map_id"), character.get("instance_id")) != (MAP_ID, 0):
        raise ValueError("Training transit requires the public Rii dojo")


def mark_setup_failed(store, account_id, generation, character):
    """Persist a failed encounter setup for recovery after reconnect."""
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        if (
            db.execute(
                "UPDATE rii_training_transits SET setup_failed=true "
                "WHERE account_id=%s AND character_id=%s RETURNING character_id",
                (account_id, character["id"]),
            ).fetchone()
            is None
        ):
            raise ValueError("Missing failed Rii training transit")


def mark_setup_ready_in_transaction(db, character, objective_id):
    """Commit encounter readiness together with its group and receipts.

    The caller owns the account/session and group locks. The server-provided
    transient marker is scoped to a stage action; ordinary tutorial encounters
    have no transit and do not touch this table.
    """
    if character.get("_rii_training_objective") != objective_id:
        return
    if (
        db.execute(
            "UPDATE rii_training_transits SET setup_failed=false "
            "WHERE account_id=%s AND character_id=%s AND lesson_objective=%s "
            "AND setup_failed=true RETURNING character_id",
            (character["account_id"], character["id"], objective_id),
        ).fetchone()
        is None
    ):
        raise ValueError("Missing or stale Rii training transit")


def setup_is_ready(store, account_id, character_id):
    """Read the durable producer-commit result without changing it."""
    with store.connection() as db:
        row = db.execute(
            "SELECT setup_failed FROM rii_training_transits WHERE account_id=%s AND character_id=%s",
            (account_id, character_id),
        ).fetchone()
    if row is None or type(row["setup_failed"]) is not bool:
        raise ValueError("Missing Rii training setup status")
    return not row["setup_failed"]


def _reject_fight(db, character_id):
    if db.execute(
        "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=%s AND f.status IN ('placement','active') "
        "AND NOT EXISTS (SELECT 1 FROM combat_pve_withdrawals w "
        "WHERE w.fight_id=p.fight_id AND w.character_id=p.character_id "
        "AND w.account_id=p.account_id) LIMIT 1",
        (character_id,),
    ).fetchone():
        raise ValueError("Training transit is unavailable during combat")


def enter(store, account_id, generation, character, objective_id, *, available):
    """Atomically move the owned player to the dojo floor and remember return.

    `available` is a server-side position-registry predicate. The destination
    and saved source must both be free before moving; source is validated by
    the normal store transition, session generation and account lock.
    """
    if objective_id not in OBJECTIVES or type(objective_id) is not int:
        raise ValueError("Unknown Rii training lesson")
    _validate_scene(character)
    if not callable(available):
        raise ValueError("Missing training scene occupancy authority")
    source = {key: character[key] for key in POSITION}
    from wakfu_server.combat_geometry import published_geometry

    geometry = published_geometry(MAP_ID)
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        _reject_fight(db, character["id"])
        # Serialize reservations across accounts. Ordinary world movement is
        # not subject to this advisory lock, so the live occupancy predicate
        # is still required and cannot promise a global movement lock.
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            ("rii-training-arena:1388:0",),
        )
        pending = db.execute(
            "SELECT * FROM rii_training_transits WHERE character_id=%s FOR UPDATE",
            (character["id"],),
        ).fetchone()
        current = store.character(account_id, character["id"], db)
        if any(current[key] != source[key] for key in POSITION):
            raise ValueError("Training transit origin changed")
        if pending is not None:
            # Resume only the same owner's unfinished lesson on its floor.
            # Re-arm the setup receipt so a newly published group and its
            # readiness commit together, including after a World restart.
            if pending["account_id"] != account_id or current["z"] != 0:
                raise ValueError("A Rii training return is already pending")
            if pending["lesson_objective"] != objective_id:
                from .storage import load_locked

                state = load_locked(db, character["id"])
                if pending["lesson_objective"] not in state["objectives"]:
                    raise ValueError("A Rii training return is already pending")
            db.execute(
                "UPDATE rii_training_transits SET setup_failed=true, lesson_objective=%s "
                "WHERE character_id=%s AND account_id=%s",
                (objective_id, character["id"], account_id),
            )
            return current
        reservations = db.execute(
            "SELECT source_x,source_y,source_z,floor_x,floor_y,floor_z "
            "FROM rii_training_transits"
        ).fetchall()
        sources = {
            (row["source_x"], row["source_y"], row["source_z"]) for row in reservations
        }
        reserved = {
            (row["floor_x"], row["floor_y"], row["floor_z"]) for row in reservations
        }
        if tuple(source[key] for key in ("x", "y", "z")) in sources:
            raise ValueError("Rii training return position is reserved")
        floor = next(
            (
                dict(FLOOR, x=x, y=y, z=z)
                for x, y, z in FLOOR_CELLS
                if (x, y, z) in geometry.cells
                and (x, y, z) not in reserved
                and available(dict(FLOOR, x=x, y=y, z=z))
            ),
            None,
        )
        if floor is None:
            raise ValueError("Rii training floor is occupied")
        db.execute(
            "INSERT INTO rii_training_transits(character_id,account_id,source_map,source_instance,"
            "source_x,source_y,source_z,floor_x,floor_y,floor_z,lesson_objective) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                character["id"],
                account_id,
                *(source[key] for key in POSITION),
                *(floor[key] for key in ("x", "y", "z")),
                objective_id,
            ),
        )
        return store.transition_map_in_transaction(
            db, account_id, generation, character["id"], current, floor
        )


def return_to_source(
    store, account_id, generation, character, *, available, only_completed=False
):
    """Return one pending transit once outside combat; otherwise do nothing.

    A player who has independently left the dojo is never teleported back.
    Return data is retained if the saved destination is temporarily occupied.
    """
    if not callable(available):
        raise ValueError("Missing training scene occupancy authority")
    if type(only_completed) is not bool:
        raise ValueError("Invalid training recovery policy")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            ("rii-training-arena:1388:0",),
        )
        row = db.execute(
            "SELECT * FROM rii_training_transits WHERE character_id=%s AND account_id=%s FOR UPDATE",
            (character["id"], account_id),
        ).fetchone()
        if row is None:
            return None
        current = store.character(account_id, character["id"], db)
        if any(current[key] != character[key] for key in POSITION):
            raise ValueError("Training return position changed")
        if (current["map_id"], current["instance_id"]) != (MAP_ID, 0):
            db.execute(
                "DELETE FROM rii_training_transits WHERE character_id=%s",
                (character["id"],),
            )
            return None
        if only_completed and not row["setup_failed"]:
            from .storage import load_locked

            state = load_locked(db, character["id"])
            if row["lesson_objective"] not in state["objectives"]:
                return None
        _reject_fight(db, character["id"])
        source = {
            "map_id": row["source_map"],
            "instance_id": row["source_instance"],
            "x": row["source_x"],
            "y": row["source_y"],
            "z": row["source_z"],
        }
        if not available(source):
            return None
        saved = store.transition_map_in_transaction(
            db, account_id, generation, character["id"], current, source
        )
        db.execute(
            "DELETE FROM rii_training_transits WHERE character_id=%s",
            (character["id"],),
        )
        return saved
