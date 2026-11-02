"""Reviewed run-scoped challenge ballots and native exclusive optional votes.

The native action has no nonce: another accepted action spends another earned
unit while voting is open. A frozen winner never spends another unit. Original
server repetition and cleanup rules are unavailable; this is an explicit
reconstruction, not a claimed recovered server program.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct
from psycopg.types.json import Jsonb


def digest(record):
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@lru_cache(maxsize=1)
def rules():
    return json.loads(
        Path(__file__).with_name("dungeon_optional_vote_rules.json").read_text()
    )["rules"]


def rule_for(config):
    binding = config["topology"].get("optional_vote_access")
    if binding is None:
        return None
    matches = [r for r in rules() if r["key"] == binding.get("rule_key")]
    if len(matches) != 1:
        raise ValueError("Optional vote contract is unknown")
    rule = matches[0]
    from wakfu_server import native_catalog

    if (
        rule["route_key"] != config["route"]["key"]
        or rule["map_id"] != config["topology"]["asset_map_id"]
        or binding.get("rule_sha256") != digest(rule)
        or binding.get("plan_sha256") != config["compiled_plan"]["document_sha256"]
        or rule["native_revision"] != native_catalog.release()
        or not rule["urn_approaches"]
        or rule["urn_approach_status"] != "PROVED_ORIGINAL_bEG_dST_VA_NATIVE_HEIGHT"
    ):
        raise ValueError("Optional vote native evidence or pinned contract changed")
    return rule


def context(db, instance_id):
    from wakfu_server import dungeon_runtime

    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s", (instance_id,)
    ).fetchone()
    if run is None:
        return None
    _, config = dungeon_runtime.configuration_for_instance(db, instance_id)
    if config["topology"].get("_optional_access_denied_reason"):
        raise ValueError("Optional access contract is unavailable")
    rule = rule_for(config)
    return None if rule is None else (run, config, rule)


def _freeze_challenge(db, fight_id):
    encounter = db.execute(
        "SELECT * FROM dungeon_room_encounters WHERE fight_id=%s", (fight_id,)
    ).fetchone()
    if encounter is None or encounter.get("encounter_scope", "main") != "main":
        return None
    selected = context(db, encounter["instance_id"])
    if selected is None:
        return None
    run, config, rule = selected
    if encounter["room_order"] not in range(1, rule["required_checkpoint"] + 1):
        return None
    members = db.execute(
        "SELECT character_id FROM dungeon_instance_members WHERE instance_id=%s AND status='active' ORDER BY character_id",
        (run["instance_id"],),
    ).fetchall()
    return dict(
        schema=1,
        instance_id=run["instance_id"],
        fight_id=fight_id,
        room_order=encounter["room_order"],
        player_team=encounter["player_team"],
        rule_sha256=digest(rule),
        catalog_hash=run["catalog_hash"],
        minimum_wp=rule["wp_minimum"],
        characters={
            str(m["character_id"]): dict(failed=False, turns={}, minimum_wp=None)
            for m in members
        },
    )


def freeze_challenge(db, fight_id):
    from psycopg import Error as OptionalEvidenceDatabaseError

    try:
        # A failed optional read cannot abort ordinary fight admission.
        with db.transaction():
            return _freeze_challenge(db, fight_id)
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OptionalEvidenceDatabaseError,
    ):
        return None


def _observe_turn(fight, actor_id):
    """Observe the final owned end boundary; never change resources or events."""
    record = getattr(fight, "native_optional_ballot_challenge", None)
    if record is None or str(actor_id) not in record["characters"]:
        return
    actor = fight.actors.get(actor_id)
    state = record["characters"][str(actor_id)]
    if actor is None or actor.team != record["player_team"]:
        state["failed"] = True
        return
    wp = (actor.effect_stats or {}).get(4)
    key = str(fight.turn_id)
    if type(wp) is not int:
        state["failed"] = True
        return
    previous = state["turns"].get(key)
    if previous is not None:
        if previous != wp:
            state["failed"] = True
        return
    state["turns"][key] = wp
    state["minimum_wp"] = (
        wp if state["minimum_wp"] is None else min(wp, state["minimum_wp"])
    )
    state["failed"] = state["failed"] or wp < record["minimum_wp"]


def observe_turn(fight, actor_id):
    try:
        _observe_turn(fight, actor_id)
    except (ValueError, TypeError, KeyError, AttributeError):
        record = getattr(fight, "native_optional_ballot_challenge", None)
        if isinstance(record, dict):
            record["qualification_failed"] = True
        else:
            fight.native_optional_ballot_challenge = dict(
                schema=1, qualification_failed=True
            )


def _ensure_gate(db, run, rule, *, pending):
    db.execute(
        "INSERT INTO dungeon_optional_gate_choices(instance_id,contract_key,asset_map_id,source_object_id,required_checkpoint,catalog_hash,rule_sha256,threshold,publication_pending) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(instance_id) DO NOTHING",
        (
            run["instance_id"],
            rule["key"],
            rule["map_id"],
            rule["urn_object"],
            rule["required_checkpoint"],
            run["catalog_hash"],
            digest(rule),
            rule["threshold"],
            pending,
        ),
    )


def queue_checkpoint(db, run, encounter, fight):
    """Publish council access independently of individual ballot qualification."""
    if fight.winner != encounter["player_team"]:
        return
    selected = context(db, run["instance_id"])
    if selected is None:
        return
    current, config, rule = selected
    if encounter["room_order"] != rule["required_checkpoint"]:
        return
    from wakfu_server.dungeon_optional_checkpoint import require_checkpoint

    require_checkpoint(
        db,
        current,
        rule["required_checkpoint"],
        expected_hash=config["compiled_plan"]["document_sha256"],
    )
    _ensure_gate(db, current, rule, pending=True)


def record_victory(db, run, encounter, fight):
    record = getattr(fight, "native_optional_ballot_challenge", None)
    if record is None or record.get("qualification_failed"):
        return
    selected = context(db, run["instance_id"])
    if selected is None:
        raise ValueError("Challenge lost its pinned optional contract")
    _, config, rule = selected
    if any(
        record[k] != v
        for k, v in (
            ("instance_id", run["instance_id"]),
            ("fight_id", fight.id),
            ("room_order", encounter["room_order"]),
            ("player_team", encounter["player_team"]),
            ("rule_sha256", digest(rule)),
            ("catalog_hash", run["catalog_hash"]),
        )
    ):
        raise ValueError("Optional challenge belongs to another fight or contract")
    if fight.winner != encounter["player_team"]:
        return
    participants = db.execute(
        "SELECT character_id FROM combat_fight_participants WHERE fight_id=%s AND team=%s",
        (fight.id, encounter["player_team"]),
    ).fetchall()
    for participant in participants:
        cid = participant["character_id"]
        state = record["characters"].get(str(cid))
        if state is None or state["failed"]:
            continue
        # No end boundary is a valid vacuous challenge, not a required extra turn.
        observed = {str(key) for key in state["turns"]}
        delivered = {
            key.split(":", 1)[0]
            for key in getattr(fight, "native_turn_event_deliveries", {})
            if key.endswith(":" + str(cid) + ":end")
        }
        actor = fight.actors.get(cid)
        if (
            observed != delivered
            or actor is None
            or type((actor.effect_stats or {}).get(4)) is not int
        ):
            continue
        old = db.execute(
            "SELECT * FROM dungeon_optional_ballot_entitlements WHERE instance_id=%s AND character_id=%s AND room_order=%s",
            (run["instance_id"], cid, encounter["room_order"]),
        ).fetchone()
        if old is not None:
            if old["fight_id"] != fight.id or old["rule_sha256"] != digest(rule):
                raise ValueError("Conflicting challenge victory replay")
            continue
        db.execute(
            "INSERT INTO dungeon_optional_ballot_entitlements(instance_id,character_id,room_order,fight_id,chest_id,rule_sha256,observation) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (
                run["instance_id"],
                cid,
                encounter["room_order"],
                fight.id,
                rule["ballot_chests"][str(encounter["room_order"])],
                digest(rule),
                Jsonb(state),
            ),
        )


def _require_member(db, run, character, generation):
    member = db.execute(
        "SELECT 1 FROM dungeon_instance_members m JOIN dungeon_instances i USING(instance_id) WHERE m.instance_id=%s AND m.party_id=%s AND m.character_id=%s AND m.session_generation=%s AND m.status='active' AND i.status='active'",
        (run["instance_id"], run["party_id"], character["id"], generation),
    ).fetchone()
    if member is None:
        raise ValueError("Optional source requires current owned instance membership")


def reward_scope(db, character, provider, *, generation):
    """Return a qualifying run claim, without touching historic global claims."""
    if not character.get("instance_id") or not scene_enabled(character["map_id"]):
        return None
    selected = context(db, character["instance_id"])
    if selected is None:
        return None
    run, config, rule = selected
    _require_member(db, run, character, generation)
    if provider["policy_id"] != rule["ballot_policy"]:
        return None
    if provider["object_id"] not in rule["ballot_chests"].values():
        raise ValueError("Ballot chest is outside its native room binding")
    row = db.execute(
        "SELECT * FROM dungeon_optional_ballot_entitlements WHERE instance_id=%s AND character_id=%s AND chest_id=%s FOR UPDATE",
        (run["instance_id"], character["id"], provider["object_id"]),
    ).fetchone()
    if row is None or row["rule_sha256"] != digest(rule):
        raise ValueError("Ballot requires its owned successful fight challenge")
    return row


def claim_scope(db, scope, attempt, products):
    expected = context(db, scope["instance_id"])[2]
    if products != {expected["ballot_reference"]: expected["ballot_quantity"]}:
        raise ValueError("Native challenge ballot effect changed")
    result = db.execute(
        "UPDATE dungeon_optional_ballot_entitlements SET granted_units=1,claim_attempt=%s WHERE instance_id=%s AND character_id=%s AND room_order=%s AND granted_units=0",
        (attempt, scope["instance_id"], scope["character_id"], scope["room_order"]),
    )
    if result.rowcount != 1:
        raise ValueError("Ballot claim changed during settlement")


def choose(db, store, run, config, character, body, *, create_encounter):
    """Caller holds main-run, session and owning-character locks, in that order."""
    if type(body) is not bytes or len(body) != 12:
        raise ValueError("Invalid native urn action")
    object_id, action, parameter = struct.unpack(">qHH", body)
    rule = rule_for(config)
    if rule is None or object_id != rule["urn_object"] or parameter != 0:
        raise ValueError("Unknown native optional urn")
    branches = [
        name for name, b in rule["branches"].items() if b["wire_action"] == action
    ]
    if (
        len(branches) != 1
        or character["map_id"] != rule["map_id"]
        or character.get("instance_id") != run["instance_id"]
    ):
        raise ValueError("Urn action belongs to another owned instance")
    if [character[k] for k in ("x", "y", "z")] not in rule["urn_approaches"]:
        raise ValueError("Urn requires its original native approach cell")
    from wakfu_server.dungeon_optional_checkpoint import require_checkpoint

    require_checkpoint(
        db,
        run,
        rule["required_checkpoint"],
        expected_hash=config["compiled_plan"]["document_sha256"],
    )
    _ensure_gate(db, run, rule, pending=True)
    gate = db.execute(
        "SELECT * FROM dungeon_optional_gate_choices WHERE instance_id=%s FOR UPDATE",
        (run["instance_id"],),
    ).fetchone()
    if any(
        gate[k] != v
        for k, v in (
            ("contract_key", rule["key"]),
            ("catalog_hash", run["catalog_hash"]),
            ("rule_sha256", digest(rule)),
        )
    ):
        raise ValueError("Urn receipt differs from its immutable contract")
    if gate["winner"] is not None:
        return dict(
            winner=gate["winner"],
            consumed=0,
            packets=[],
            replay=True,
            instance_id=run["instance_id"],
        )
    entitlement = db.execute(
        "SELECT * FROM dungeon_optional_ballot_entitlements WHERE instance_id=%s AND character_id=%s AND granted_units>spent_units ORDER BY room_order LIMIT 1 FOR UPDATE",
        (run["instance_id"], character["id"]),
    ).fetchone()
    if entitlement is None or entitlement["rule_sha256"] != digest(rule):
        raise ValueError("No earned run-scoped ballot remains")
    from wakfu_server.dungeon_entry_payment import consume

    payment = consume(db, (character["id"],), rule["ballot_reference"], 1)
    if (
        len(payment) != 1
        or payment[0].get("quest_item")
        or payment[0].get("account_quest_item")
    ):
        raise ValueError("Native vote needs one owned ordinary ballot unit")
    source = payment[0]
    branch = branches[0]
    column = branch + "_votes"
    revision = gate["revision"] + 1
    count = gate[column] + 1
    winner = branch if count >= gate["threshold"] else None
    spent = db.execute(
        "UPDATE dungeon_optional_ballot_entitlements SET spent_units=spent_units+1 WHERE instance_id=%s AND character_id=%s AND room_order=%s AND spent_units<granted_units",
        (run["instance_id"], character["id"], entitlement["room_order"]),
    )
    if spent.rowcount != 1:
        raise ValueError("Ballot unit was already spent")
    # Column comes exclusively from the immutable two-branch enum above.
    db.execute(
        "UPDATE dungeon_optional_gate_choices SET "
        + column
        + "=%s,winner=%s,winner_account_id=%s,winner_character_id=%s,revision=%s,publication_pending=publication_pending OR %s WHERE instance_id=%s",
        (
            count,
            winner,
            character["account_id"] if winner else None,
            character["id"] if winner else None,
            revision,
            bool(winner),
            run["instance_id"],
        ),
    )
    db.execute(
        "INSERT INTO dungeon_optional_vote_receipts(instance_id,character_id,account_id,entitlement_room_order,source_uid,source_reference,wire_action,choice,gate_revision,consumed_units) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,1)",
        (
            run["instance_id"],
            character["id"],
            character["account_id"],
            entitlement["room_order"],
            source["uid"],
            rule["ballot_reference"],
            action,
            branch,
            revision,
        ),
    )
    if winner == "archimonster":
        create_encounter(db, run, config, rule, character)
    return dict(
        winner=winner,
        consumed=1,
        packets=[(12470, struct.pack(">qh", source["uid"], -1))],
        replay=False,
        instance_id=run["instance_id"],
    )


def gate_view(db, run, config):
    rule = rule_for(config)
    if rule is None:
        return None
    from wakfu_server.dungeon_optional_checkpoint import require_checkpoint

    try:
        require_checkpoint(
            db,
            run,
            rule["required_checkpoint"],
            expected_hash=config["compiled_plan"]["document_sha256"],
        )
    except ValueError:
        return dict(checkpoint=False, winner=None)
    gate = db.execute(
        "SELECT * FROM dungeon_optional_gate_choices WHERE instance_id=%s",
        (run["instance_id"],),
    ).fetchone()
    if gate is not None and (
        gate["rule_sha256"] != digest(rule)
        or gate["catalog_hash"] != run["catalog_hash"]
    ):
        raise ValueError("Optional gate receipt changed after qualification")
    return dict(checkpoint=True, winner=None if gate is None else gate["winner"])


def require_paid_gate(db, character, provider, *, generation):
    if not scene_enabled(character["map_id"]):
        return
    selected = context(db, character.get("instance_id", 0))
    if selected is None:
        return
    run, config, rule = selected
    if provider["object_id"] != rule["branches"]["treasure"]["paid_object"]:
        return
    _require_member(db, run, character, generation)
    if (
        provider["policy_id"] != rule["branches"]["treasure"]["paid_policy"]
        or gate_view(db, run, config)["winner"] != "treasure"
    ):
        raise ValueError("Native paid treasure requires its exclusive winning vote")


def create_archimonster(db, groups, run, config, rule, character):
    branch = rule["branches"]["archimonster"]
    access = next(
        row
        for row in config["topology"]["optional_room_policy"]["optional_rooms"]
        if row["source_order"] == branch["optional_source_order"]
    )
    room = next(
        row for row in config["topology"]["rooms"] if row["order"] == access["order"]
    )
    from wakfu_server.dungeon_optional_group import create

    return create(
        db,
        groups,
        run,
        config,
        character,
        room_order=access["order"],
        source_order=access["source_order"],
        anchor=room["anchor"],
        activation=dict(
            source_uid=None,
            source_reference=None,
            action_id=branch["native_action"],
            activation_method="native_vote",
            vote_gate_instance_id=run["instance_id"],
        ),
        rule_sha256=digest(rule),
    )


def handles(map_id, body):
    if type(body) is not bytes or len(body) != 12:
        return False
    identity, action, parameter = struct.unpack(">qHH", body)
    return any(r["map_id"] == map_id and r["urn_object"] == identity for r in rules())


def cast_vote(
    store,
    groups,
    account_id,
    generation,
    character_id,
    body,
    *,
    positions=None,
    in_fight=False
):
    from contextlib import ExitStack
    from wakfu_server.inventory_owner import lock_inventory_character
    from wakfu_server.simple_item_actions import _idle
    from psycopg.errors import LockNotAvailable

    if in_fight is not False:
        raise ValueError("Vote outside combat")
    try:
        with ExitStack() as ownership, store.connection() as db:
            owner = db.execute(
                "SELECT instance_id FROM characters WHERE id=%s AND account_id=%s",
                (character_id, account_id),
            ).fetchone()
            if owner is None:
                raise ValueError("Optional vote owner is absent")
            run = db.execute(
                "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
                (owner["instance_id"],),
            ).fetchone()
            if run is None:
                raise ValueError("Optional vote requires an owned dungeon run")
            if positions is not None:
                from wakfu_server.position_buffer import PositionOwnerBusy

                try:
                    ownership.enter_context(
                        positions.account_barrier(account_id, blocking=False)
                    )
                except PositionOwnerBusy as error:
                    raise ValueError(
                        "Dungeon position is busy; retry this vote"
                    ) from error
                positions.flush(account_id=account_id)
            for sql in (
                "SELECT id FROM accounts WHERE id=%s FOR UPDATE NOWAIT",
                "SELECT account_id FROM sessions WHERE account_id=%s FOR UPDATE NOWAIT",
            ):
                db.execute(sql, (account_id,)).fetchone()
            db.execute(
                "SELECT id FROM characters WHERE id=%s FOR UPDATE NOWAIT",
                (character_id,),
            ).fetchone()
            lock_inventory_character(store, db, account_id, generation, character_id)
            character = store.character(account_id, character_id, db)
            _idle(db, character_id, store.now())
            if character.get("instance_id") != run["instance_id"]:
                raise ValueError("Vote actor changed instance")
            member = db.execute(
                "SELECT 1 FROM dungeon_instance_members m JOIN dungeon_instances i USING(instance_id) WHERE m.instance_id=%s AND m.party_id=%s AND m.character_id=%s AND m.status='active' AND m.session_generation=%s AND i.status='active'",
                (run["instance_id"], run["party_id"], character_id, generation),
            ).fetchone()
            if member is None:
                raise ValueError("Vote requires active owned instance membership")
            from wakfu_server import dungeon_runtime

            _, config = dungeon_runtime.configuration_for_instance(
                db, run["instance_id"]
            )
            result = choose(
                db,
                store,
                run,
                config,
                character,
                body,
                create_encounter=lambda sql, main, cfg, rule, actor: create_archimonster(
                    sql, groups, main, cfg, rule, actor
                ),
            )
            return dict(result, character=store.character(account_id, character_id, db))
    except LockNotAvailable as error:
        raise ValueError("Optional vote owner is busy; retry") from error


def project_configuration(db, run, config):
    from psycopg import Error as OptionalEvidenceDatabaseError

    try:
        # Missing or contradictory optional evidence closes only that access.
        # The four required main encounters retain their pinned configuration.
        with db.transaction():
            rule = rule_for(config)
            if rule is None:
                return config
            state = gate_view(db, run, config)
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OptionalEvidenceDatabaseError,
    ):
        topology = dict(config["topology"])
        topology.pop("optional_vote_access", None)
        topology.pop("_optional_vote_state", None)
        topology[
            "_optional_access_denied_reason"
        ] = "Pinned optional native evidence is unavailable"
        return dict(config, topology=topology)
    state["rule_sha256"] = digest(rule)
    state["instance_id"] = run["instance_id"]
    state["catalog_hash"] = run["catalog_hash"]
    return dict(config, topology=dict(config["topology"], _optional_vote_state=state))


def scene_enabled(map_id):
    return any(r["map_id"] == map_id for r in rules())


def publish_pending(store, groups, *, instance_id, publish):
    from wakfu_server import (
        dungeon_optional_encounters,
        dungeon_runtime,
        dungeon_object_states,
    )

    with store.connection() as db:
        row = db.execute(
            "SELECT c.* FROM dungeon_optional_gate_choices c JOIN dungeon_instances i USING(instance_id) WHERE c.instance_id=%s AND c.publication_pending AND i.status='active'",
            (instance_id,),
        ).fetchone()
        if row is None:
            return False
        _, config = dungeon_runtime.configuration_for_instance(db, instance_id)
        rule = rule_for(config)
        from wakfu_server.dungeon_optional_vote_geometry import gate_packets

        packets = list(gate_packets(config["topology"]))
        from wakfu_server.generic_transports import source

        packets.extend(
            dungeon_object_states.state_packet(
                source(rule["map_id"], r["source_id"]),
                map_id=rule["map_id"],
                instance_id=instance_id,
                visible=True,
                usable=True,
            )
            for r in rule["transports"]
        )
    if row["winner"] == "archimonster":
        if not dungeon_optional_encounters.publish_pending(
            store, groups, instance_id=instance_id, publish=publish
        ):
            # An already-acknowledged group is not a failed gate publication.
            with store.connection() as db:
                pending = db.execute(
                    "SELECT published FROM dungeon_optional_publication_outbox WHERE instance_id=%s",
                    (instance_id,),
                ).fetchone()
            if pending is None or not pending["published"]:
                return False
    for opcode, payload in packets:
        if publish(rule["map_id"], instance_id, opcode, payload) is False:
            return False
    with store.connection() as db:
        db.execute(
            "UPDATE dungeon_optional_gate_choices SET publication_pending=false WHERE instance_id=%s AND revision=%s",
            (instance_id, row["revision"]),
        )
    return True
