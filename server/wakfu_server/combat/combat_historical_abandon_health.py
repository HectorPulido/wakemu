"""Offline, proof-qualified repair of an already authenticated abandon return.

This is an administrative migration helper, never a session recovery fallback.
The operator reviews and pins the proof before a quiesced deployment window.
"""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path


SCHEMA = "wakemu.historical-abandon-health.v1"


def plain(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def digest(value):
    return hashlib.sha256(
        json.dumps(plain(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def instant(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Evidence timestamps must have a timezone")
    return result


def compact(record):
    keys = (
        "time",
        "server_boot_id",
        "request_id",
        "connection_id",
        "request_opcode",
        "event",
        "account_id",
        "character_id",
        "actor_id",
        "fight_id",
        "reason",
        "status",
        "rejections",
    )
    result = {key: record[key] for key in keys if key in record}
    for name in ("state_before", "state_after"):
        if name not in record:
            continue
        state = record[name]
        character = state.get("character")
        fight = state.get("fight")
        result[name] = {
            "character": None
            if character is None
            else {key: character[key] for key in ("id", "hp", "max_hp")},
            "fight": None
            if fight is None
            else {key: fight[key] for key in ("id", "phase")},
        }
    return result


def capture(db, character_id, *, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    character = db.execute(
        "SELECT id,account_id,breed,level,hp,max_hp,hp_damage,health_dead,deleted_at "
        "FROM characters WHERE id=%s" + suffix,
        (character_id,),
    ).fetchone()
    if character is None:
        raise ValueError("Repair character does not exist")
    regeneration = db.execute(
        "SELECT * FROM character_regeneration WHERE character_id=%s" + suffix,
        (character_id,),
    ).fetchone()
    exits = list(
        db.execute(
            "SELECT * FROM fight_health_exits WHERE character_id=%s "
            "ORDER BY created_at,fight_id" + suffix,
            (character_id,),
        )
    )
    # A proof prepared before migration194 may lack its new nullable column.
    for row in exits:
        row.setdefault("abandon_return_acknowledged_at", None)
    memberships = list(
        db.execute(
            "SELECT p.*,f.status,f.created_at AS fight_created_at,f.fight_kind "
            "FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
            "WHERE p.character_id=%s ORDER BY f.created_at,p.fight_id"
            + (" FOR UPDATE OF p,f" if lock else ""),
            (character_id,),
        )
    )
    identities = [row["fight_id"] for row in memberships]
    footprints = {}
    for table in ("fight_checkpoints", "fight_rewards", "fight_health_exits"):
        footprints[table] = list(
            db.execute(
                "SELECT fight_id FROM "
                + table
                + " WHERE fight_id=ANY(%s) ORDER BY fight_id",
                (identities,),
            )
        )
    return plain(
        dict(
            character=character,
            regeneration=regeneration,
            exits=exits,
            memberships=memberships,
            footprints=footprints,
        )
    )


def request(records, identity, opcode, status):
    rows = [row for row in records if row.get("request_id") == identity]
    starts = [row for row in rows if row.get("event") == "request_started"]
    ends = [row for row in rows if row.get("event") == "request_finished"]
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError("Evidence requires one complete original request")
    start, end = starts[0], ends[0]
    if (
        start.get("request_opcode") != opcode
        or end.get("request_opcode") != opcode
        or end.get("status") != status
        or start.get("connection_id") != end.get("connection_id")
        or not start.get("connection_id")
        or not start.get("server_boot_id")
        or start.get("server_boot_id") != end.get("server_boot_id")
        or instant(start["time"]) > instant(end["time"])
    ):
        raise ValueError("Original request identity or outcome differs")
    if status == "completed" and end.get("rejections") != []:
        raise ValueError("Original request was not successfully handled")
    return start, end, rows


def dead_world(state, identity, maximum):
    return state.get("fight") is None and state.get("character") == {
        "id": identity,
        "hp": 0,
        "max_hp": maximum,
    }


def qualify(proof, guards):
    if proof.get("schema") != SCHEMA:
        raise ValueError("Unknown historical repair proof")
    identity, owner, fight_id = (
        proof[key] for key in ("character_id", "account_id", "fight_id")
    )
    if any(
        type(value) is not int or value <= 0 for value in (identity, owner, fight_id)
    ):
        raise ValueError("Invalid explicit repair identity")
    character = guards["character"]
    if (
        character["id"] != identity
        or character["account_id"] != owner
        or character["deleted_at"] is not None
    ):
        raise ValueError("Historical repair belongs to another character owner")
    receipts = [row for row in guards["exits"] if row["fight_id"] == fight_id]
    members = [row for row in guards["memberships"] if row["fight_id"] == fight_id]
    if len(receipts) != 1 or len(members) != 1:
        raise ValueError("Original abort membership or receipt is missing")
    receipt, member = receipts[0], members[0]
    if (
        receipt["reason"] != "abort"
        or member["status"] != "aborted"
        or member["fight_kind"] != "pve"
        or member["account_id"] != owner
        or receipt["character_id"] != identity
        or member["character_id"] != identity
        or not isinstance(proof["original_generation"], str)
        or not proof["original_generation"]
        or receipt["generation"] != member["session_generation"]
        or receipt["generation"] != proof["original_generation"]
        or instant(member["fight_created_at"]) > instant(receipt["created_at"])
        or receipt["return_acknowledged_at"] is not None
        or receipt["abandon_return_acknowledged_at"] is not None
    ):
        raise ValueError("Original authenticated abort provenance differs")
    if (
        character["hp"] != 0
        or character["health_dead"] is not True
        or character["hp_damage"] != character["max_hp"]
    ):
        raise ValueError("Repair requires the unchanged canonical dead casualty")
    baseline = guards["regeneration"]
    if (
        baseline is None
        or baseline["character_id"] != identity
        or baseline["initial_hp"] != 0
        or baseline["coefficient"] != 0
        or baseline["initial_damage"] != character["hp_damage"]
        or instant(baseline["started_at"]) != instant(baseline["last_at"])
    ):
        raise ValueError("Dead regeneration baseline changed")
    if any(
        row["fight_id"] != fight_id
        and instant(row["created_at"]) >= instant(receipt["created_at"])
        for row in guards["exits"]
    ):
        raise ValueError("A later health exit superseded this return")
    if any(row["status"] in ("placement", "active") for row in guards["memberships"]):
        raise ValueError("Character has an active fight")

    records = proof["witness"]
    start, end, ack_rows = request(records, proof["ack_request_id"], 12925, "completed")
    maximum = character["max_hp"]
    before = start.get("state_before", {})
    if (
        before.get("character") != {"id": identity, "hp": 0, "max_hp": maximum}
        or before.get("fight") != {"id": fight_id, "phase": "finished"}
        or not dead_world(end.get("state_after", {}), identity, maximum)
        or instant(receipt["created_at"]) > instant(start["time"])
        or proof["ack_time"] != start["time"]
    ):
        raise ValueError("Original ACK did not return this finished dead character")
    connection, boot = start["connection_id"], start["server_boot_id"]
    authenticated = any(
        row.get("event") == "character_selected"
        and row.get("account_id") == owner
        and row.get("connection_id") == connection
        and row.get("server_boot_id") == boot
        and instant(row["time"]) < instant(start["time"])
        for row in records
    )
    owned_ack = any(row.get("account_id") == owner for row in ack_rows)
    if not authenticated or not owned_ack:
        raise ValueError(
            "Missing original authenticated loaded-world ownership evidence"
        )
    abandon = [
        row
        for row in records
        if row.get("event") == "shared_pve_abandoned_waiting_return"
        and row.get("connection_id") == connection
        and row.get("server_boot_id") == boot
        and row.get("actor_id") == identity
        and row.get("fight_id") == fight_id
        and instant(receipt["created_at"])
        <= instant(row["time"])
        < instant(start["time"])
    ]
    if len(abandon) != 1:
        raise ValueError("Missing original abandonment-to-ACK transition")
    request(records, abandon[0]["request_id"], 13952, "completed")
    movement = [
        row
        for row in records
        if row.get("event") == "request_finished"
        and row.get("request_opcode") == 13331
        and row.get("status") == "completed"
        and row.get("rejections") == []
        and row.get("connection_id") == connection
        and row.get("server_boot_id") == boot
        and instant(row["time"]) > instant(end["time"])
        and dead_world(row.get("state_before", {}), identity, maximum)
        and dead_world(row.get("state_after", {}), identity, maximum)
    ]
    if not movement:
        raise ValueError("Original ACK lacks its subsequent world movement")
    relogins = [
        row
        for row in records
        if row.get("event") == "character_selected"
        and row.get("character_id") == identity
        and row.get("account_id") == owner
        and instant(row["time"]) > instant(end["time"])
    ]
    reset_proven = False
    for selected in relogins:
        relog_start, relog_end, _ = request(
            records, selected["request_id"], 23664, "completed"
        )
        if (
            selected.get("connection_id") == relog_start["connection_id"]
            and selected.get("server_boot_id") == relog_start["server_boot_id"]
            and instant(baseline["started_at"]) > instant(end["time"])
            and instant(relog_start["time"])
            <= instant(baseline["started_at"])
            <= instant(selected["time"])
            and dead_world(relog_end.get("state_after", {}), identity, maximum)
        ):
            reset_proven = True
    if not reset_proven:
        raise ValueError("Later dead baseline lacks its original authenticated relogin")

    failed = proof["failed_allocations"]
    expected = {
        row["fight_id"]
        for row in guards["memberships"]
        if instant(row["fight_created_at"]) > instant(receipt["created_at"])
    }
    if (
        len(failed) != len({row["fight_id"] for row in failed})
        or len(failed) != len({row["request_id"] for row in failed})
        or expected != {row["fight_id"] for row in failed}
    ):
        raise ValueError("Unlisted newer fight allocation")
    for allocation in failed:
        failed_id = allocation["fight_id"]
        current = next(
            row for row in guards["memberships"] if row["fight_id"] == failed_id
        )
        failed_start, failed_end, rows = request(
            records, allocation["request_id"], 13130, "rejected"
        )
        rejects = [
            row
            for row in rows
            if row.get("event") == "combat_test_attack_rejected"
            and row.get("actor_id") == identity
            and row.get("reason") == "Invalid actor team or resources"
        ]
        failed_authenticated = any(
            row.get("event") == "character_selected"
            and row.get("account_id") == owner
            and row.get("connection_id") == failed_start["connection_id"]
            and row.get("server_boot_id") == failed_start["server_boot_id"]
            and instant(row["time"]) < instant(failed_start["time"])
            for row in records
        )
        if (
            not failed_authenticated
            or current["status"] != "aborted"
            or current["account_id"] != owner
            or not instant(failed_start["time"])
            <= instant(current["fight_created_at"])
            <= instant(failed_end["time"])
            or not dead_world(failed_start.get("state_before", {}), identity, maximum)
            or not dead_world(failed_end.get("state_after", {}), identity, maximum)
            or len(rejects) != 1
            or failed_end.get("rejections")
            != [
                {
                    "event": "combat_test_attack_rejected",
                    "reason": "Invalid actor team or resources",
                }
            ]
            or any(
                row.get("event")
                in ("combat_effect", "combat_commit_stage", "combat_test_started")
                for row in rows
            )
            or any(
                any(row["fight_id"] == failed_id for row in values)
                for values in guards["footprints"].values()
            )
        ):
            raise ValueError("Newer allocation was not a proven rejected constructor")
    return receipt


def prepare(
    db,
    records,
    *,
    account_id,
    character_id,
    fight_id,
    ack_request_id,
    failed_allocations,
    sources
):
    guards = capture(db, character_id)
    receipt = next(
        (row for row in guards["exits"] if row["fight_id"] == fight_id), None
    )
    if receipt is None:
        raise ValueError("Original health exit is missing")
    witness = [
        compact(row)
        for row in records
        if row.get("event")
        in (
            "request_started",
            "request_finished",
            "position_batch_timing",
            "character_selected",
            "shared_pve_abandoned_waiting_return",
            "combat_test_attack_rejected",
            "combat_effect",
            "combat_commit_stage",
            "combat_test_started",
        )
    ]
    start, _, _ = request(witness, ack_request_id, 12925, "completed")
    proof = dict(
        schema=SCHEMA,
        account_id=account_id,
        character_id=character_id,
        fight_id=fight_id,
        original_generation=receipt["generation"],
        ack_request_id=ack_request_id,
        ack_time=start["time"],
        failed_allocations=failed_allocations,
        sources=sources,
        witness=witness,
        guards=guards,
    )
    qualify(proof, guards)
    return proof


def non_health_guards(guards, *, acknowledged_fight=None):
    exits = [dict(row) for row in guards["exits"]]
    if acknowledged_fight is not None:
        for row in exits:
            if row["fight_id"] == acknowledged_fight:
                row["abandon_return_acknowledged_at"] = None
    return dict(
        character={
            key: value
            for key, value in guards["character"].items()
            if key not in ("hp", "hp_damage", "health_dead")
        },
        exits=exits,
        memberships=guards["memberships"],
        footprints=guards["footprints"],
    )


def repair(db, proof, *, backup, skip_already_alive=False):
    from psycopg.pq import TransactionStatus
    from wakfu_server import health, health_policy

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Historical repair requires one explicit transaction")
    qualify(proof, proof["guards"])
    owner, identity, fight_id = (
        proof[key] for key in ("account_id", "character_id", "fight_id")
    )
    db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (owner,)).fetchone()
    # Serialize with ordinary writers; this deliberately does not impersonate
    # an expired session or weaken normal session/generation checks.
    db.execute(
        "SELECT account_id FROM sessions WHERE account_id=%s FOR UPDATE", (owner,)
    ).fetchall()
    current = capture(db, identity, lock=True)
    original = next(
        (row for row in current["exits"] if row["fight_id"] == fight_id), None
    )
    if original is not None and original["abandon_return_acknowledged_at"] is not None:
        expected = dict(
            next(row for row in proof["guards"]["exits"] if row["fight_id"] == fight_id)
        )
        expected["abandon_return_acknowledged_at"] = original[
            "abandon_return_acknowledged_at"
        ]
        if (
            current["character"]["account_id"] != owner
            or current["character"]["deleted_at"] is not None
            or original != expected
            or instant(original["abandon_return_acknowledged_at"])
            != instant(proof["ack_time"])
            or non_health_guards(current, acknowledged_fight=fight_id)
            != non_health_guards(proof["guards"])
        ):
            raise ValueError("Different historical acknowledgement already exists")
        return dict(
            outcome="already_acknowledged",
            applied=False,
            already_acknowledged=True,
            ack_written=False,
            health_written=False,
            regeneration_written=False,
            proof_sha256=digest(proof),
        )
    character = current["character"]
    if skip_already_alive and character["health_dead"] is False and character["hp"] > 0:
        if (
            non_health_guards(current) != non_health_guards(proof["guards"])
            or health_policy.visible(character["max_hp"], character["hp_damage"], False)
            != character["hp"]
        ):
            raise ValueError(
                "Living character has different ownership or fight history"
            )
        # Current canonical living health makes this administrative repair
        # unnecessary. This branch never infers a Phoenix event or marks an ACK.
        return dict(
            outcome="already_alive",
            applied=False,
            already_acknowledged=False,
            character_id=identity,
            fight_id=fight_id,
            hp=character["hp"],
            ack_written=False,
            health_written=False,
            regeneration_written=False,
            proof_sha256=digest(proof),
        )
    if current != proof["guards"]:
        raise ValueError(
            "Repair proof is stale; health, ownership, baseline or fight history changed"
        )
    qualify(proof, current)
    if backup is None:
        raise ValueError("Repair requires an exclusive pre-mutation backup")
    with Path(backup).open("x") as stream:
        os.chmod(backup, 0o600)
        json.dump(dict(proof_sha256=digest(proof), before=current), stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    damage, dead = health_policy.recover_finished_return(
        character["max_hp"], character["hp_damage"], True
    )
    hp = health_policy.apply_damage(db, character, damage, dead)
    now = db.execute("SELECT CURRENT_TIMESTAMP AS value").fetchone()["value"]
    coefficient = health.exploration_coefficient(character["max_hp"], hp)
    regeneration = db.execute(
        "UPDATE character_regeneration SET initial_hp=%s,started_at=%s,coefficient=%s,last_at=%s "
        "WHERE character_id=%s",
        (hp, now, coefficient, now, identity),
    )
    if regeneration.rowcount != 1:
        raise ValueError("Historical regeneration compare-and-set failed")
    result = db.execute(
        "UPDATE fight_health_exits SET abandon_return_acknowledged_at=%s "
        "WHERE fight_id=%s AND character_id=%s AND reason='abort' AND generation=%s "
        "AND created_at=%s AND abandon_return_acknowledged_at IS NULL",
        (
            instant(proof["ack_time"]),
            fight_id,
            identity,
            proof["original_generation"],
            original["created_at"],
        ),
    )
    if result.rowcount != 1:
        raise ValueError("Historical acknowledgement compare-and-set failed")
    return dict(
        outcome="repaired",
        applied=True,
        already_acknowledged=False,
        ack_written=True,
        health_written=True,
        regeneration_written=True,
        character_id=identity,
        fight_id=fight_id,
        hp=hp,
        coefficient=coefficient,
        proof_sha256=digest(proof),
        backup=str(backup),
    )
