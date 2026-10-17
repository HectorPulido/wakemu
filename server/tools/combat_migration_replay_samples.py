#!/usr/bin/env python3
"""Capture native migration examples using an already exported offline catalog.

These are asserted native fixture reproductions, not observed live incidents.
Run in a fresh interpreter; no database, client, or live server is required.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import struct
import sys

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))


def _declared_combat_documents(inventory):
    """Conservatively enumerate published literal document names in the core."""
    names, source_hashes = {}, {}
    for path in sorted((SERVER / "wakfu_server" / "combat").rglob("*.py")):
        raw = path.read_bytes()
        source_name = path.relative_to(SERVER).as_posix()
        source_hashes[source_name] = hashlib.sha256(raw).hexdigest()
        for node in ast.walk(ast.parse(raw, filename=str(path))):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value in inventory
            ):
                names.setdefault(node.value, set()).add(source_name)
    return {name: sorted(paths) for name, paths in sorted(names.items())}, source_hashes


def _merge_catalog(
    source, supplement, output, additional_documents=(), complete_combat_documents=False
):
    """Copy published bytes only when their identity matches the same release."""
    manifest = json.loads((source / "catalog.json").read_bytes())
    original_documents = set(manifest["documents"])
    declared, source_hashes = _declared_combat_documents(manifest["published_hashes"])
    output.mkdir(mode=0o700)
    shutil.copytree(source / "catalog", output / "catalog")
    if supplement is not None:
        extra = json.loads((supplement / "manifest.json").read_bytes())
        if extra["revision"] != manifest["revision"]:
            raise ValueError("Supplement uses another catalog release")
        for name, expected in extra["consumed_documents"].items():
            if manifest["published_hashes"].get(name) != expected:
                raise ValueError("Supplement differs from published catalog identity")
            raw = (supplement / "documents" / name).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("Supplement document checksum differs")
            (output / "catalog" / expected).write_bytes(raw)
            manifest["documents"][name] = dict(sha256=expected, size=len(raw))
    requested = set(additional_documents)
    if complete_combat_documents:
        requested.update(set(declared) - set(manifest["documents"]))
    if requested:
        # This explicit preparation step only reads the existing published
        # release. Gameplay still runs entirely under ReplayCatalog below.
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        if (
            native_catalog.release() != manifest["revision"]
            or native_catalog.document_hashes() != manifest["published_hashes"]
        ):
            raise ValueError(
                "Additional documents require the same published release/inventory"
            )
        for name in sorted(requested):
            if name not in manifest["published_hashes"]:
                raise ValueError(
                    "Additional document is not in the published inventory"
                )
            raw = native_catalog.read_published_bytes(name)
            expected = manifest["published_hashes"][name]
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError(
                    "Additional document differs from the published inventory"
                )
            (output / "catalog" / expected).write_bytes(raw)
            manifest["documents"][name] = dict(sha256=expected, size=len(raw))
        if (
            native_catalog.release() != manifest["revision"]
            or native_catalog.document_hashes() != manifest["published_hashes"]
        ):
            raise ValueError(
                "Published release changed while exporting declared documents"
            )
    (output / "catalog.json").write_text(json.dumps(manifest, sort_keys=True))
    preparation = dict(
        schema="wakemu-combat-migration-catalog-preparation-v1",
        revision=manifest["revision"],
        published_inventory_sha256=hashlib.sha256(
            json.dumps(
                manifest["published_hashes"], sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest(),
        source_bundle_manifest_sha256=hashlib.sha256(
            (source / "catalog.json").read_bytes()
        ).hexdigest(),
        declared_combat_document_sources=declared,
        scanned_source_hashes=source_hashes,
        static_literal_overapproximation=True,
        dynamic_document_closure_proven=False,
        added_documents={
            name: manifest["documents"][name]
            for name in sorted(set(manifest["documents"]) - original_documents)
        },
        sealed_document_count=len(manifest["documents"]),
        live_replay_fallback=False,
    )
    (output / "catalog-preparation.json").write_text(
        json.dumps(preparation, indent=2) + "\n"
    )


def _capture(output):
    sys.path.insert(0, str(SERVER / "tests"))
    from test_combat_reproduction_actions import ReproductionActionTests
    from test_aniripsa_grant_summon_pipeline import AniripsaGrantSummonPipelineTests
    from wakfu_server.combat_reproduction import (
        capture_request,
        execute_case,
        record_expectation,
        bind_catalog_bundle,
        write_case,
        controlled_environment,
    )
    from wakfu_server.combat_reproduction_state import decode_state, encode_state
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_timeline_snapshot import current_wire_turn
    from wakfu_server.combat_spell_grant import granted_spells

    clocks = dict(wall_time_ns=1700000000000000000, monotonic_ns=123000000000)
    policies = dict(WAKFU_NATIVE_AREA_CALLBACKS="1", WAKFU_NATIVE_GRANTED_CAST="1")
    summaries = []

    def record(name, runtime, action, inputs, rng, assertion):
        case = capture_request(
            runtime, action, inputs, rng, clocks=clocks, policies=policies
        )
        result = execute_case(case)
        outcome = decode_state(result["result"])
        if result["status"] != "accepted":
            raise AssertionError(
                name + " did not execute successfully: " + str(outcome["error"])
            )
        assertion(outcome)
        record_expectation(case, result)
        bind_catalog_bundle(case, output)
        write_case(output / (name + ".json"), case)
        summaries.append(
            dict(
                case=name + ".json",
                source_sha256=result["source_sha256"],
                outcome_sha256=result["sha256"],
                native_assertion=assertion.__doc__,
                events=len(outcome["events"]),
                packets=len(outcome["packets"]),
                status=result["status"],
            )
        )
        rng.setstate(outcome["rng_state"])
        return outcome["runtime"]

    def spell(reference, cell):
        return dict(
            type="player_spell",
            body=struct.pack(">qqiih", 7, reference, *cell),
            owner_id=3,
            critical=False,
        )

    def require(condition, message):
        if not condition:
            raise AssertionError(message)

    with controlled_environment(clocks, policies):
        fixture = ReproductionActionTests()
        runtime, inputs = fixture.fixture()
        target_id = -7
        hp = runtime.fight.actors[target_id].hp

        def assert_damage(outcome):
            """Actual Huppermage6266 lowers enemy HP and emits native packets/events."""
            require(
                outcome["runtime"].fight.actors[target_id].hp < hp,
                "Native damage missing",
            )
            require(
                bool(outcome["packets"]) and bool(outcome["events"]),
                "Native delivery missing",
            )

        record(
            "huppermage-damage",
            runtime,
            spell((7 << 32) | 6266, runtime.fight.actors[target_id].position),
            inputs,
            random.Random(42),
            assert_damage,
        )

        from wakfu_server.combat_hp_raw import set_hp_raw_current

        runtime, inputs = fixture.fixture(7, 200, (779,))
        set_hp_raw_current(runtime.fight.actors[7], 100)

        def assert_heal(outcome):
            """Actual Eniripsa779 heals injured caster and emits native packets."""
            require(
                outcome["runtime"].fight.actors[7].hp > 100, "Native healing missing"
            )
            require(bool(outcome["packets"]), "Native healing packets missing")

        record(
            "eniripsa-native-healing",
            runtime,
            spell((7 << 32) | 779, runtime.fight.actors[7].position),
            inputs,
            random.Random(42),
            assert_heal,
        )

        from test_combat_weapon import equipped

        runtime, inputs = fixture.fixture(11, 200, ())
        character = equipped(inputs["character"], 2027)
        inputs = dict(inputs, character=character, player_characters={7: character})
        hp = runtime.fight.actors[-7].hp

        def assert_weapon(outcome):
            """Actual owned item2027 weapon lowers enemy HP and emits13509/12873."""
            require(
                outcome["runtime"].fight.actors[-7].hp < hp,
                "Native weapon damage missing",
            )
            require(outcome["packets"][0][0] == 13509, "Weapon action packet missing")
            require(
                12873 in {opcode for opcode, _ in outcome["packets"]},
                "Weapon result packet missing",
            )

        record(
            "owned-native-weapon",
            runtime,
            dict(
                type="player_weapon",
                owner_id=3,
                critical=False,
                body=struct.pack(
                    ">qqbiih", 7, 1000, 15, *runtime.fight.actors[-7].position
                ),
            ),
            inputs,
            random.Random(42),
            assert_weapon,
        )

        runtime, inputs = fixture.fixture(1, 200, (6972,))
        uid = granted_spells(runtime.fight, 7)[7009]["uid"]
        ap, wp = runtime.fight.actors[7].ap, runtime.fight.actors[7].effect_stats[4]

        def assert_armor(outcome):
            """Actual Feca7009 applies6364, grants7052 and consumes exactly2AP/1WP."""
            fight = outcome["runtime"].fight
            require(
                6364 in {s.reference for s in fight.actors[7].state_ledger.entries},
                "Armor state missing",
            )
            require(7052 in granted_spells(fight, 7), "Teleport grant missing")
            require(
                (fight.actors[7].ap, fight.actors[7].effect_stats[4])
                == (ap - 2, wp - 1),
                "Armor native cost differs",
            )

        rng = random.Random(42)
        runtime = record(
            "feca-peace-armor",
            runtime,
            spell(uid, runtime.fight.actors[7].position),
            inputs,
            rng,
            assert_armor,
        )
        for index in range(16):
            if 6364 not in {
                s.reference for s in runtime.fight.actors[7].state_ledger.entries
            }:
                break
            if runtime.awaiting_ack is not None:
                action = dict(type="ack", body=struct.pack(">i", runtime.awaiting_ack))
            elif runtime.fight.current.owner_id == 3:
                action = dict(
                    type="end_turn",
                    owner_id=3,
                    actor_id=runtime.fight.current.id,
                    turn_id=current_wire_turn(runtime.fight),
                )
            else:
                action = dict(
                    type="end_server_turn",
                    actor_id=runtime.fight.current.id,
                    turn_id=runtime.fight.turn_id,
                )

            def assert_transition(outcome):
                """Real native turn/ACK transition changes runtime and emits ordered packets."""
                require(
                    encode_state(outcome["runtime"]) != encode_state(runtime),
                    "Turn/ACK did not change state",
                )
                require(bool(outcome["packets"]), "Turn/ACK native packets missing")

            runtime = record(
                "feca-expiration-step-" + str(index),
                runtime,
                action,
                inputs,
                rng,
                assert_transition,
            )
        require(
            6364
            not in {s.reference for s in runtime.fight.actors[7].state_ledger.entries},
            "Armor never expired",
        )
        require(
            7052 not in granted_spells(runtime.fight, 7),
            "Expired teleport grant remains",
        )

        native = AniripsaGrantSummonPipelineTests()
        character, monster, fight, deck, rng = native.fixture()
        inputs = dict(
            authority_recipe="ordinary-server-runtime-v1",
            character=character,
            monsters={
                monster["id"]: dict(
                    monster, level=fight.actors[monster["id"]].effective_level
                )
            },
            deck_blob=deck,
            player_characters={7: character},
            deck_blobs={7: deck},
            map_id=character["map_id"],
            native_events=True,
            area_callbacks=True,
        )
        runtime = RuntimeMessages(fight)
        runtime.action_id = 1

        def assert_summon(outcome):
            """Actual Eniripsa7978 creates owned182 Cunejo with native986 book and QI registration."""
            from wakfu_server.combat_summon_spellbook import actor_action_book

            fight = outcome["runtime"].fight
            summons = [
                a
                for a in fight.actors.values()
                if getattr(a, "native_summon_source", None) and a.hp > 0
            ]
            require(len(summons) == 1, "Native summon was not created")
            summon = summons[0]
            require(summon.native_summon_source["ref"] == 182, "Wrong summon profile")
            require(
                summon.native_controller_id == 7 and summon.owner_id == 3,
                "Wrong summon ownership",
            )
            require(summon.position == (-8, -6, -1), "Wrong registered summon cell")
            require(
                summon.id in fight.native_summon_registrations,
                "Missing summon registration",
            )
            require(
                {r["reference"] for r in actor_action_book(summon)["actions"]} == {986},
                "Wrong summon book",
            )

        runtime = record(
            "eniripsa-native-summon",
            runtime,
            spell(7978, (-8, -6, -1)),
            inputs,
            rng,
            assert_summon,
        )
        summon_id = next(
            a.id
            for a in runtime.fight.actors.values()
            if getattr(a, "native_summon_source", None) and a.hp > 0
        )

        def advance_to(actor_id, prefix):
            nonlocal runtime
            for index in range(32):
                if (
                    runtime.awaiting_ack is None
                    and runtime.fight.current.id == actor_id
                ):
                    return
                if runtime.awaiting_ack is not None:
                    action = dict(
                        type="ack", body=struct.pack(">i", runtime.awaiting_ack)
                    )
                elif runtime.fight.current.controlled:
                    action = dict(
                        type="end_turn",
                        owner_id=runtime.fight.current.owner_id,
                        actor_id=runtime.fight.current.id,
                        turn_id=current_wire_turn(runtime.fight),
                    )
                else:
                    action = dict(
                        type="end_server_turn",
                        actor_id=runtime.fight.current.id,
                        turn_id=runtime.fight.turn_id,
                    )

                def assert_native_transition(outcome):
                    """Actual native end/ACK progresses toward a registered actor's owned turn."""
                    require(
                        encode_state(outcome["runtime"]) != encode_state(runtime),
                        "Native turn did not progress",
                    )
                    require(bool(outcome["packets"]), "Native turn packets missing")

                runtime = record(
                    prefix + "-" + str(index),
                    runtime,
                    action,
                    inputs,
                    rng,
                    assert_native_transition,
                )
            raise AssertionError("Registered actor never received its native turn")

        advance_to(summon_id, "cunejo-turn")
        set_hp_raw_current(runtime.fight.actors[7], 100)

        def assert_cunejo_heal(outcome):
            """Admitted controlled Cunejo986 uses its native owned book and heals owner100→142HP."""
            fight = outcome["runtime"].fight
            require(
                fight.actors[7].hp == 142, "Controlled summon native healing differs"
            )
            require(
                fight.actors[summon_id].hp > 0, "Controlled healer unexpectedly retired"
            )
            require(bool(outcome["packets"]), "Controlled summon delivery missing")

        runtime = record(
            "controlled-cunejo-healing",
            runtime,
            dict(
                type="player_spell",
                owner_id=3,
                critical=False,
                body=struct.pack(
                    ">qqiih", summon_id, 986, *runtime.fight.actors[7].position
                ),
            ),
            inputs,
            rng,
            assert_cunejo_heal,
        )
        advance_to(-7, "enemy-retirement-turn")
        from wakfu_server.combat_qi_fight import move_registered_actor

        move_registered_actor(runtime.fight, runtime.fight.actors[-7], (-7, -6, -1))
        set_hp_raw_current(runtime.fight.actors[summon_id], 1)

        def assert_native_retirement(outcome):
            """Actual owned NPC7962 kills preinjured Cunejo and settles death/retirement/QI release."""
            from wakfu_server.combat_summon_retirement import retired_summon_ids

            fight = outcome["runtime"].fight
            require(
                summon_id in retired_summon_ids(fight),
                "Dead native summon was not retired",
            )
            require(fight.actors[summon_id].hp == 0, "Native lethal damage missing")
            require(
                fight.actors[summon_id].native_obstacle_id == -1,
                "Retired summon kept spatial slot",
            )
            require(
                all(
                    row is None or row["identity"] != ["actor", summon_id]
                    for row in fight.native_qi_slots
                ),
                "Retired summon remains in QI",
            )
            require(bool(outcome["packets"]), "Death/retirement packets missing")

        record(
            "npc-kills-native-cunejo",
            runtime,
            dict(
                type="npc_spell",
                action=dict(
                    type="cast",
                    spellId=7962,
                    level=1,
                    targetId=summon_id,
                    target=list(runtime.fight.actors[summon_id].position),
                ),
            ),
            inputs,
            rng,
            assert_native_retirement,
        )

        # Capture actual isolated repository-dispatcher + Registry boundaries,
        # retaining their observed provider/lease/RNG tapes and mailbox state.
        from test_combat_shared_action_incident_replay import (
            SharedActionIncidentReplayTests,
        )
        from wakfu_server.combat_incident_replay import (
            bind_incident_bundle,
            write_incident,
        )

        fixture = SharedActionIncidentReplayTests()
        for kind in ("spell", "end_turn"):
            receipt = fixture.capture(kind)
            before = decode_state(receipt["before"]["graph"])
            after = decode_state(receipt["after"]["graph"])
            require(receipt["status"] == "returned", "Native Registry action failed")
            require(
                bool(after["outboxes"][3]),
                "Native Registry mailbox publication missing",
            )
            if kind == "spell":
                require(
                    after["fight"].actors[-7].hp < before["fight"].actors[-7].hp,
                    "Registry native damage missing",
                )
            else:
                require(
                    after["ack"].turn is not None and bool(after["runtime"].pending),
                    "Native collective ACK boundary missing",
                )
            bind_incident_bundle(receipt, output)
            name = "shared-" + kind + "-incident.json"
            write_incident(output / name, receipt)
            summaries.append(
                dict(
                    case=name,
                    kind="incident",
                    provider_recipe="observed-live-server-v1",
                    source_sha256=receipt["identity"]["source"]["sha256"],
                    native_assertion="Actual Registry native "
                    + kind
                    + " publishes mailbox; spell lowers HP, end-turn opens ACK with pending packets",
                    status=receipt["status"],
                )
            )

        from test_combat_spectator_summon_timeline import SpectatorSummonTimelineTests
        from test_combat_reconnect_summon_timeline import timeline_fields
        from wakfu_server.combat_recipient_reproduction import (
            capture_recipient_request,
            execute_recipient_case,
            record_recipient_expectation,
        )
        from wakfu_server.combat_additional_turn import additional_turn_insertion

        snapshots = SpectatorSummonTimelineTests()
        for role, properties, extra_turn in (
            ("spectator", (), False),
            ("owner", (), False),
            ("spectator", (114,), False),
            ("spectator", (), True),
            ("owner", (), True),
        ):
            fight, summon, shared = snapshots.fixture(
                True, not properties and not extra_turn, properties
            )
            shared.runtime.turn_deadline = None
            shared.runtime.awaiting_ack = None
            if extra_turn:
                fight.native_base_turn_order = list(fight.order)
                insertion = additional_turn_insertion(
                    fight.order,
                    fight.turn_index,
                    mode=0,
                    offset=1,
                    caster_id=100,
                    target_id=fight.current.id,
                )
                require(
                    insertion["applied"], "Native extra turn fixture did not insert"
                )
                fight.order = insertion["order"]
                fight.turn_index = insertion["insertion"]
            case = capture_recipient_request(
                fight,
                shared,
                role=role,
                actor_payloads={
                    identity: (b"stats", b"\x00\x00") for identity in fight.actors
                },
                payload_authority="test-placeholder",
                deadline_ms=1700000000000,
                session_account_id=1,
                clocks=dict(wall_time_ns=1700000000000000000, monotonic_ns=0),
                policies=policies,
            )
            result = execute_recipient_case(case)
            record_recipient_expectation(case, result)
            outcome = decode_state(result["result"])
            require(
                outcome["error"] is None,
                "Current recipient producer did not produce packets",
            )
            packets = outcome["packets"]
            recovery = next(body for opcode, body in packets if opcode == 12053)
            phase, orders, progress, index, turn = timeline_fields(recovery[15:])
            require(
                orders[0] == tuple(fight.order), "Recovered current timeline differs"
            )
            require(
                orders[0][index] == fight.current.id and (phase, turn) == (1, 13),
                "Recovered current turn differs",
            )
            require(
                progress
                == {
                    int(key): value
                    for key, value in fight.native_timeline_member_counters.items()
                },
                "Recovered counters differ",
            )
            if properties:
                require(
                    summon.id not in orders[0], "Property114 summon entered timeline"
                )
            if extra_turn:
                require(
                    orders[1] == tuple(fight.native_base_turn_order), "Base order lost"
                )
                require(
                    orders[0].count(fight.current.id) == 2,
                    "Extra current slot was normalized away",
                )
            bind_catalog_bundle(case, output)
            name = (
                "recipient-"
                + role
                + ("-114" if properties else "")
                + ("-extra-turn" if extra_turn else "")
                + ".json"
            )
            descriptor = os.open(
                output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            )
            with os.fdopen(descriptor, "w") as stream:
                json.dump(case, stream, separators=(",", ":"))
            summaries.append(
                dict(
                    case=name,
                    kind="recipient",
                    source_sha256=case["source"]["sha256"],
                    payload_authority="test-placeholder",
                    native_assertion="Snapshot producer restores exact current/base order, counters/current member; no mutation;114excluded; extra slots preserved",
                    outcome_sha256=result["sha256"],
                    qualification="typed-producer-reproduction-not-full-actor-payload-or-native-oracle",
                )
            )
    return summaries


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-bundle", type=Path, required=True)
    parser.add_argument("--supplemental-catalog", type=Path)
    parser.add_argument(
        "--additional-document",
        action="append",
        default=[],
        help="Explicitly export another document from the identical published release before offline execution",
    )
    parser.add_argument(
        "--complete-combat-documents",
        action="store_true",
        help="Batch export missing published literal document names referenced by combat source",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    _merge_catalog(
        args.catalog_bundle,
        args.supplemental_catalog,
        args.output,
        args.additional_document,
        args.complete_combat_documents,
    )
    from wakfu_server.combat_reproduction_catalog import ReplayCatalog

    with ReplayCatalog(args.output).install():
        summaries = _capture(args.output)
    index = dict(
        schema="wakemu-combat-current-native-examples-v2",
        cases=summaries,
        boundary="asserted-native-fixtures-not-live-incidents",
        qualification="current-engine-semantic-assertions-not-historical-backend-comparison",
    )
    (args.output / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps(index, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
