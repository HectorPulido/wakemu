"""Atomic native rift exits, fenced against queued position writes."""
from contextlib import ExitStack
import struct


def _exit(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    allowed_accounts,
    source_allowed,
    fighting,
    relocation=None,
):
    if relocation is None:
        if not isinstance(body, (bytes, bytearray, memoryview)) or len(body) != 17:
            raise ValueError("Invalid native rift exit request")
        identity, _, flag, mode = struct.unpack(">qiBi", body)
        if flag != 0 or mode != 2:
            raise ValueError("Unsupported native rift exit mode")
    elif body is not None:
        raise ValueError("Administrative relocation is not a native exit request")
    from wakfu_server import generic_transports, player_parties, rift_runtime

    with store.connection() as db:
        preliminary = db.execute(
            "SELECT instance_id FROM characters WHERE id=%s AND account_id=%s",
            (character_id, account_id),
        ).fetchone()
        if preliminary is None:
            raise ValueError("Unknown rift exit character")
        preliminary_run = db.execute(
            "SELECT members FROM rift_instances WHERE instance_id=%s",
            (preliminary["instance_id"],),
        ).fetchone()
        if preliminary_run is None:
            return None
        player_parties._lock_members(db, preliminary_run["members"])
        store.lock_character(db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db)
        if relocation is not None and any(
            character[key] != relocation["source"][key]
            for key in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Rift relocation origin is desynchronized")
        run = rift_runtime._run(db, character["instance_id"])
        from wakfu_server.characters.hero_instance_membership import rift_company

        company = rift_company(db, account_id, character_id, run["instance_id"])
        company_owned = (
            db.execute(
                "SELECT 1 FROM characters WHERE id=ANY(%s) AND account_id=%s LIMIT 1",
                (run["members"], account_id),
            ).fetchone()
            is not None
        )
        if (
            character_id not in run["members"]
            and not (
                run["status"] in ("won", "lost", "closed")
                and company_owned
                and character_id in company
            )
        ) or character["map_id"] != run["catalog"]["map_id"]:
            raise ValueError("Character is outside its owned rift")
        if run["status"] == "running" and not (
            fighting is not None
            and any(fighting(identity) for identity in run["members"])
        ):
            # The canonical fight outcome wins over a retained active checkpoint.
            # Repair only an already-aborted binding; never infer defeat, settle
            # rewards, or abort another fight to authorize this departure.
            interrupted = db.execute(
                "SELECT 1 FROM combat_fights f WHERE f.id=%s AND f.status='aborted' "
                "AND NOT EXISTS(SELECT 1 FROM rift_settlement_receipts receipt WHERE receipt.instance_id=%s) "
                "AND NOT EXISTS(SELECT 1 FROM combat_fight_participants p JOIN combat_fights active_fight ON active_fight.id=p.fight_id "
                "WHERE p.character_id=ANY(%s) AND active_fight.status IN('placement','active'))",
                (run["fight_id"], run["instance_id"], list(run["members"])),
            ).fetchone()
            if interrupted is not None:
                repaired = rift_runtime.abort_bound_fight(db, run["fight_id"])
                if repaired is not None:
                    run = repaired
        departed_company = False
        if run["status"] == "running":
            # Other accounts keep the encounter and its immutable reward roster.
            # Only this account's completely returned company may leave early.
            departing_ids = company | {character_id}
            returned = db.execute(
                "SELECT character_id FROM combat_pve_withdrawals "
                "WHERE fight_id=%s AND account_id=%s AND character_id=ANY(%s) "
                "AND returned_at IS NOT NULL AND health_returned_at IS NOT NULL",
                (run["fight_id"], account_id, sorted(departing_ids)),
            ).fetchall()
            departed_company = {
                row["character_id"] for row in returned
            } == departing_ids
        if (run["status"] == "running" and not departed_company) or (
            fighting is not None and fighting(character_id)
        ):
            raise ValueError("Cannot leave a running rift fight")
        if relocation is None:
            sources = [
                o
                for o in run["catalog"]["objects"]
                if o["id"] == identity
                and o["type"] == "Teleporter"
                and o["map_id"] == character["map_id"]
            ]
            if len(sources) != 1:
                raise ValueError("Not the native exit of this rift")
            # Native exit criteria/cost/altitude remain authoritative.
            result = generic_transports.resolve(
                dict(character, instance_id=0),
                body,
                source_allowed=lambda unused, source: source_allowed(character, source),
            )
        else:
            # Console authorization belongs to its existing caller. This is
            # explicit administrative travel, never a fabricated portal click.
            result = dict(
                destination=relocation["destination"], direction=character["direction"]
            )
        if result["destination"]["map_id"] == character["map_id"]:
            raise ValueError("Rift exit does not leave its interior")
        ids = (
            run["members"]
            if run["status"] == "entered"
            else sorted(company | {character_id})
        )
        if (
            relocation is None
            and run["status"] == "entered"
            and run["owner_character_id"] != character_id
        ):
            raise ValueError("Only the owner may cancel an unstarted rift")
        rows = db.execute(
            "SELECT c.*,s.generation,s.character_id AS selected_character_id,s.expires_at "
            "FROM characters c LEFT JOIN sessions s ON s.account_id=c.account_id "
            "WHERE c.id=ANY(%s) ORDER BY c.id FOR UPDATE OF c",
            (ids,),
        ).fetchall()
        if {r["id"] for r in rows} != set(ids) or any(
            r["account_id"] not in allowed_accounts
            or r["instance_id"] != run["instance_id"]
            or (fighting is not None and fighting(r["id"]))
            for r in rows
        ):
            raise ValueError("Rift exit membership changed or entered combat")
        if db.execute(
            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
            "WHERE p.character_id=ANY(%s) AND f.status IN('placement','active') "
            "AND NOT EXISTS(SELECT 1 FROM combat_pve_withdrawals w "
            "WHERE w.fight_id=p.fight_id AND w.character_id=p.character_id "
            "AND w.account_id=p.account_id AND w.returned_at IS NOT NULL "
            "AND w.health_returned_at IS NOT NULL) LIMIT 1",
            (list(ids),),
        ).fetchone():
            raise ValueError("Rift member has a durable active fight")
        if run["status"] == "entered":
            rift_runtime.close_entered(db, run["instance_id"], character_id)
        destination = result["destination"]
        for row in rows:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (
                    destination["map_id"],
                    destination["x"],
                    destination["y"],
                    destination["z"],
                    row["id"],
                ),
            )
        active = tuple(
            r
            for r in rows
            if r["generation"] is not None
            and r["selected_character_id"] == r["id"]
            and r["expires_at"] > store.now()
        )
        return dict(
            members=active,
            moved_members=tuple(rows),
            destination=destination,
            direction=result["direction"],
            run=run,
        )


def leave(
    store,
    positions,
    account_id,
    generation,
    character_id,
    body,
    *,
    source_allowed,
    fighting,
):
    """Commit every affected position before queueing native map hydration."""
    return _leave(
        store,
        positions,
        account_id,
        generation,
        character_id,
        body,
        source_allowed=source_allowed,
        fighting=fighting,
    )


def _leave(
    store,
    positions,
    account_id,
    generation,
    character_id,
    body,
    *,
    source_allowed,
    fighting,
    relocation=None,
):
    from wakfu_server.rift_transition_delivery import queue

    if (
        relocation is None and (not callable(source_allowed) or not callable(fighting))
    ) or (fighting is not None and not callable(fighting)):
        raise ValueError("Rift exit requires native approach and combat authorities")
    with store.connection() as db:
        members = db.execute(
            "SELECT c.id,c.account_id FROM characters c WHERE c.id=%s OR c.id IN("
            "SELECT jsonb_array_elements_text(r.members)::bigint FROM rift_instances r "
            "JOIN characters owner ON owner.instance_id=r.instance_id WHERE owner.id=%s)",
            (character_id, character_id),
        ).fetchall()
    accounts = sorted({r["account_id"] for r in members})
    with ExitStack() as barriers:
        for account in accounts:
            barriers.enter_context(positions.account_barrier(account))
        for account in accounts:
            positions.flush(account_id=account)
        result = _exit(
            store,
            account_id,
            generation,
            character_id,
            body,
            allowed_accounts=set(accounts),
            source_allowed=source_allowed,
            fighting=fighting,
            relocation=relocation,
        )
        if result is None:
            return None
        for row in result["members"]:
            positions.release(row["account_id"], row["generation"], row["id"])
        queue(result["members"], result["destination"])
        return result


def relocate(
    store,
    positions,
    account_id,
    generation,
    character_id,
    source,
    destination,
    *,
    fighting=None,
):
    """Reuse native departure custody for an authorized console relocation.

    The caller authorizes the command. Native floor, selected ownership, full
    source CAS, frozen cohort and durable combat checks still apply. Entered
    cancellation moves every member; terminal travel moves only this company.
    No completed roster, earned result or reward receipt is rewritten.
    """
    from wakfu_server.combat_geometry import published_geometry

    if positions is None:
        raise ValueError("Rift relocation requires its position authority")
    keys = ("map_id", "instance_id", "x", "y", "z")
    if (
        any(
            type(location) is not dict
            or any(type(location.get(key)) is not int for key in keys)
            for location in (source, destination)
        )
        or destination["instance_id"] != 0
    ):
        raise ValueError("Rift relocation requires a typed exterior destination")
    if (
        tuple(destination[key] for key in ("x", "y", "z"))
        not in published_geometry(destination["map_id"]).cells
    ):
        raise ValueError("Rift relocation destination is not native walkable floor")
    return _leave(
        store,
        positions,
        account_id,
        generation,
        character_id,
        None,
        source_allowed=None,
        # Running status and the complete cohort's persisted combat membership
        # are checked under the same run/owner locks as native departure.
        fighting=fighting,
        relocation=dict(source=dict(source), destination=dict(destination)),
    )
