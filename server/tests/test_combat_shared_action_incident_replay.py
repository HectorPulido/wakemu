"""Actual dispatcher actions replay Registry publication from captured evidence.

The fixed repository dispatcher functions are compiled in isolation so no world
listener starts. Combat operations, providers, serializers and Registry paths
are their real implementations; diagnostic persistence alone is intercepted.
"""
import ast
import copy
import os
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_incident_replay import LIVE_RECIPE, replay_shared_incident
from wakfu_server.combat_reproduction import controlled_environment
from wakfu_server.combat_reproduction_state import decode_state, encode_state
from wakfu_server.combat_shared import Batch, Session, Transition
from wakfu_server.combat_session_adapter import CombatSessionAdapter
import test_combat_incident_dispatch_integration as dispatch
import test_combat_reproduction_actions as native


CLOCKS = {"wall_time_ns": 1700000000000000000, "monotonic_ns": 123000000000}
POLICIES = {"WAKFU_NATIVE_AREA_CALLBACKS": "1", "WAKFU_NATIVE_GRANTED_CAST": "0"}


class SharedActionIncidentReplayTests(unittest.TestCase):
    def fixture(self, kind):
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        equipped_weapon = kind in {"weapon", "unarmed_equipped"}
        runtime, inputs = native.ReproductionActionTests().fixture(
            breed=11 if equipped_weapon else 15,
            level=200 if equipped_weapon else 20,
            spells=() if equipped_weapon else (6266,),
        )
        if kind in {"unarmed", "unarmed_equipped"}:
            # Preserve existing authoritative WP while providing the complete
            # descriptor consumed by the real unarmed producer's serializer.
            inputs = dict(
                inputs,
                monsters={
                    identity: dict(
                        monster,
                        wp=runtime.fight.actors[identity].effect_stats[4],
                        max_wp=runtime.fight.actors[identity].effect_maxima[4],
                    )
                    for identity, monster in inputs["monsters"].items()
                },
            )
        character = inputs["character"]
        if equipped_weapon:
            from test_combat_weapon import equipped

            character = equipped(character, 2027)
        builds = copy.deepcopy(character.get("builds", {}))
        builds.setdefault(0, {})["deck"] = inputs["deck_blob"].hex()
        character = dict(character, builds=builds)

        class Store:
            def __init__(self):
                self.character_reads = []

            def character(self, owner, identity):
                self.character_reads.append((owner, identity))
                if (owner, identity) != (3, 7):
                    raise ValueError("Unexpected fixture owner")
                return character

            def current_character_session(self, owner, generation, identity):
                return (owner, generation, identity) == (3, "native-shared-fixture", 7)

        store = Store()
        adapter = CombatSessionAdapter(store)
        session = Session(3, 7, "native-shared-fixture", 1134, 0)

        def bind_initialized(fight, owner, ready, **providers):
            # Initialization already used real class/fight-start producers.
            # Capture the actual ready_transition provider closures without
            # repeating initialization or altering its lifecycle receipts.
            fields = (
                "stats_serializer",
                "runtime_stats_serializer",
                "turn_end_provider",
                "turn_start_provider",
                "expiration_runtime_factory",
            )
            result = RuntimeMessages(
                fight,
                **{field: providers[field] for field in fields},
                clock=lambda: CLOCKS["monotonic_ns"] / 1e9
            )
            result.action_id = runtime.action_id
            return fight, result, ()

        with patch(
            "wakfu_server.combat_ready.prepare_ready", side_effect=bind_initialized
        ):
            transition = adapter.ready_transition(
                session,
                runtime.fight,
                runtime,
                True,
                inputs["monsters"],
                fight_start=True,
                area_callbacks=True,
            )
        runtime = transition.runtime
        shared = adapter.registry.register(runtime.fight, session, runtime=runtime)
        namespace = dict(
            __name__="local_game_server",
            os=os,
            STORE=store,
            COMBAT_TEST=True,
            character=character,
            fight=shared.fight,
            COMBAT_SESSIONS=adapter,
            combat_session=session,
            TEST_MONSTERS_BY_ID=inputs["monsters"],
            COMBAT_TEST_CRITICAL_BRANCH="auto",
            record=lambda **fields: None,
            Transition=Transition,
            action_results={},
            movement_result={},
        )
        # Retain real local provider qualnames required by the trusted recipe.
        functions = [
            copy.deepcopy(dispatch.dispatcher_function(name))
            for name in ("current_combat_stats", "area_movement_provider")
        ]
        wrapper = ast.FunctionDef(
            name="session",
            args=ast.arguments(
                posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
            ),
            body=[
                *functions,
                ast.Return(
                    ast.Tuple(
                        elts=[
                            ast.Name(id=node.name, ctx=ast.Load()) for node in functions
                        ],
                        ctx=ast.Load(),
                    )
                ),
            ],
            decorator_list=[],
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[])),
                str(dispatch.SOURCE),
                "exec",
            ),
            namespace,
        )
        (
            namespace["current_combat_stats"],
            namespace["area_movement_provider"],
        ) = namespace["session"]()
        namespace[
            "shared_action_incident"
        ] = dispatch.IncidentDispatchIntegrationTests().helper(
            combat_session=session,
            COMBAT_SESSIONS=adapter,
            TEST_MONSTERS_BY_ID=inputs["monsters"],
            COMBAT_TEST_CRITICAL_BRANCH="auto",
        )
        return adapter, shared, session, namespace

    def capture(self, kind):
        from wakfu_server.combat_cast import decode_cast
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_weapon import (
            prepare_server_weapon,
            decode_request as decode_weapon,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_death import death_messages
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.breed_resources import live_wp

        with controlled_environment(CLOCKS, POLICIES):
            adapter, shared, session, namespace = self.fixture(kind)
            target = shared.fight.actors[-7].position
            if kind in ("spell", "invalid_uid"):
                # A malformed logical UID reaches the actual Registry boundary;
                # a truncated wire body is rejected by the outer dispatcher
                # decoder before any Registry incident exists.
                uid = 0 if kind == "invalid_uid" else (7 << 32) | 6266
                body = struct.pack(">qqiih", 7, uid, *target)
                namespace.update(body=body, cast_request=decode_cast(body))
                function, opcode = "shared_cast", 13260
            elif kind in {"weapon", "unarmed", "unarmed_equipped"}:
                body = struct.pack(
                    ">qqbiih", 7, 1000 if kind == "weapon" else -1, 15, *target
                )
                namespace.update(body=body, request=decode_weapon(body))
                function, opcode = "shared_weapon", 12889
            elif kind == "move":
                actor = shared.fight.actors[7]
                origin = actor.position
                destination = next(
                    cell
                    for cell in sorted(shared.fight.walkable)
                    if cell != target
                    and abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) == 1
                    and cell[2] == origin[2]
                    and (
                        shared.fight.edges is None
                        or (origin, cell) in shared.fight.edges
                    )
                )
                body = struct.pack(">qiih", 7, *destination)
                namespace.update(body=body, movement_actor_id=7)
                function, opcode = "shared_move", 12161
            elif kind == "end_turn":
                turn = current_wire_turn(shared.fight)
                body = struct.pack(">qh", 7, turn)
                namespace.update(body=body, actor_id=7, actor_turn=turn)
                function, opcode = "shared_end_turn", 12403
            else:
                raise AssertionError("Unknown fixture action")
            namespace.update(
                prepare_server_spell=prepare_server_spell,
                prepare_server_weapon=prepare_server_weapon,
                commit_spell_transaction=commit_spell_transaction,
                authoritative_visible=authoritative_visible,
                death_messages=death_messages,
                apply_client=apply_client,
                live_wp=live_wp,
                secrets=__import__("secrets"),
            )
            tree = ast.Module(
                body=[copy.deepcopy(dispatch.dispatcher_function(function))],
                type_ignores=[],
            )
            exec(
                compile(ast.fix_missing_locations(tree), str(dispatch.SOURCE), "exec"),
                namespace,
            )
            error = None
            character_reads_before = tuple(namespace["STORE"].character_reads)
            with patch.dict(
                os.environ,
                {
                    "WAKFU_COMBAT_INCIDENT_DIR": "/private/unused",
                    "WAKFU_COMBAT_INCIDENT_MODE": "all",
                    "WAKFU_COMBAT_START_EVENTS": "1",
                },
            ), patch("wakfu_server.combat_incident_capture._enqueue") as enqueue:
                try:
                    adapter.registry.execute(
                        shared.fight.id,
                        session,
                        7,
                        namespace[function],
                        incident_request=dict(opcode=opcode, body=body),
                    )
                except ValueError as failure:
                    error = failure
            self.assertEqual(
                enqueue.call_count,
                1,
                "Outer and inner scopes must produce one shared receipt",
            )
            receipt = enqueue.call_args.args[1]
            if kind == "end_turn":
                self.assertEqual(
                    tuple(namespace["STORE"].character_reads),
                    character_reads_before,
                    "Capturing end-turn must not add a diagnostic Store.character read",
                )
            receipt[
                "origin"
            ] = "actual-native-dispatcher-fixture-not-live-client-incident"
            self.assertEqual(len(receipt["operations"]), 1)
            self.assertEqual(
                decode_state(receipt["request"])["wire_request"],
                dict(opcode=opcode, body=body),
            )
            if kind in {"invalid_uid", "unarmed_equipped"}:
                self.assertIsNotNone(error)
                self.assertEqual(receipt["status"], "raised")
            else:
                self.assertIsNone(error, str(error))
                self.assertEqual(receipt["status"], "returned")
            return receipt

    def assert_exact_replay(self, receipt):
        unchanged = copy.deepcopy(receipt)
        first = replay_shared_incident(receipt, provider_recipe=LIVE_RECIPE)
        repeated = replay_shared_incident(receipt, provider_recipe=LIVE_RECIPE)
        self.assertTrue(first["operation_matches"], first["differences"])
        self.assertTrue(first["mailbox_matches"])
        self.assertEqual(first["actual_sha256"], repeated["actual_sha256"])
        self.assertEqual(first["expected_sha256"], first["actual_sha256"])
        self.assertEqual(receipt, unchanged)
        self.assertFalse(first["bootstrap_qualified"])
        self.assertFalse(first["dispatch_qualified"])
        return first

    def test_player_spell_outer_receipt_replays_actual_effect_and_mailbox(self):
        receipt = self.capture("spell")
        self.assert_exact_replay(receipt)
        self.assertTrue(decode_state(receipt["operation_packets"]))
        observed = decode_state(receipt["after"]["graph"])
        self.assertTrue(observed["outboxes"][3])

    def test_malformed_spell_uid_rejection_replays_without_rng_or_publication(self):
        receipt = self.capture("invalid_uid")
        self.assert_exact_replay(receipt)
        self.assertEqual(decode_state(receipt["observations"])["rng_streams"], [])
        self.assertEqual(decode_state(receipt["after"]["graph"])["outboxes"][3], ())

    def test_movement_replays_actual_area_provider_and_registered_position(self):
        receipt = self.capture("move")
        self.assert_exact_replay(receipt)
        before = decode_state(receipt["before"]["graph"])
        after = decode_state(receipt["after"]["graph"])
        self.assertNotEqual(
            before["fight"].actors[7].position, after["fight"].actors[7].position
        )
        self.assertLess(after["fight"].actors[7].mp, before["fight"].actors[7].mp)

    def test_end_turn_replays_actual_frozen_ready_providers_and_ack_barrier(self):
        receipt = self.capture("end_turn")
        self.assert_exact_replay(receipt)
        operation = decode_state(receipt["operations"][0])
        self.assertNotIn("character", operation["inputs"])
        self.assertNotIn("player_characters", operation["inputs"])
        facts = [
            row
            for row in decode_state(receipt["observations"])["events"]
            if row["kind"] in {"authority", "fact"}
        ]
        self.assertNotIn("combat.player_sources", [row["label"] for row in facts])
        self.assertEqual(facts[0]["label"], "server_runtime.authority")
        after = decode_state(receipt["after"]["graph"])
        self.assertIsNotNone(after["ack"].turn)
        self.assertTrue(after["runtime"].pending)

    def test_weapon_replays_actual_owned_item_and_damage(self):
        receipt = self.capture("weapon")
        self.assert_exact_replay(receipt)
        before = decode_state(receipt["before"]["graph"])
        after = decode_state(receipt["after"]["graph"])
        self.assertLess(after["fight"].actors[-7].hp, before["fight"].actors[-7].hp)

    def test_unarmed_replays_actual_native_item_and_observed_uid_without_new_draw(self):
        receipt = self.capture("unarmed")
        operation = decode_state(receipt["operations"][0])
        self.assertEqual(operation["action"]["type"], "player_unarmed")
        observations = decode_state(receipt["observations"])
        uids = [
            row["value"]
            for row in observations["events"]
            if row["label"] == "shared_weapon.unarmed_effect_uid"
        ]
        self.assertEqual(len(uids), 1)
        self.assertTrue(0 < uids[0] <= 2**60)
        with patch(
            "secrets.randbelow",
            side_effect=AssertionError("Replay requested a new native effect UID"),
        ):
            self.assert_exact_replay(receipt)
        before = decode_state(receipt["before"]["graph"])
        after = decode_state(receipt["after"]["graph"])
        self.assertLess(after["fight"].actors[-7].hp, before["fight"].actors[-7].hp)
        self.assertTrue(
            any(
                event["kind"] == "melee" and event["item_reference"] == 2145
                for event in after["fight"].events
            )
        )

    def test_unarmed_equipped_slot_rejection_precedes_uid_selection(self):
        receipt = self.capture("unarmed_equipped")
        result = self.assert_exact_replay(receipt)
        self.assertEqual(result["status"], "raised")
        observations = decode_state(receipt["observations"])
        self.assertNotIn(
            "shared_weapon.unarmed_effect_uid",
            [row["label"] for row in observations["events"]],
        )
        self.assertEqual(observations["rng_streams"], [])
        self.assertEqual(decode_state(receipt["after"]["graph"])["outboxes"][3], ())

    def test_ordinary_unarmed_recipe_requires_observed_uid_and_runs_real_transaction(
        self,
    ):
        import random
        from wakfu_server.combat_reproduction_actions import (
            AUTHORITY_RECIPE,
            prepare_context,
            execute,
        )
        from wakfu_server.combat_input_observation import (
            InputReplayMismatch,
            replay_combat_inputs,
        )

        receipt = self.capture("unarmed")
        operation = decode_state(receipt["operations"][0])
        observations = decode_state(receipt["observations"])
        uid = next(
            row["value"]
            for row in observations["events"]
            if row["label"] == "shared_weapon.unarmed_effect_uid"
        )
        inputs = dict(
            operation["inputs"],
            authority_recipe=AUTHORITY_RECIPE,
            unarmed_effect_uid=uid,
        )
        action = operation["action"]
        runtime = decode_state(receipt["before"]["graph"])["runtime"]
        rng = random.Random(0)
        with controlled_environment(CLOCKS, POLICIES):
            context = prepare_context(runtime, action, inputs, rng, lambda: 123.0)
            with replay_combat_inputs(observations):
                result = execute(
                    runtime,
                    action,
                    inputs,
                    rng,
                    lambda: 123.0,
                    prepared_context=context,
                )
        self.assertEqual(result["packets"], decode_state(receipt["operation_packets"]))
        self.assertEqual(result["plan"]["item_reference"], 2145)
        missing = dict(inputs)
        missing.pop("unarmed_effect_uid")
        runtime = decode_state(receipt["before"]["graph"])["runtime"]
        context = prepare_context(runtime, action, missing, rng, lambda: 123.0)
        before_ap = runtime.fight.actors[7].ap
        with self.assertRaises(InputReplayMismatch):
            execute(
                runtime, action, missing, rng, lambda: 123.0, prepared_context=context
            )
        self.assertEqual(runtime.fight.actors[7].ap, before_ap)

    def test_tampered_operation_and_mailbox_are_detected(self):
        receipt = self.capture("spell")
        operation = copy.deepcopy(receipt)
        packets = decode_state(operation["operation_packets"])
        operation["operation_packets"] = encode_state(
            ((packets[0][0], packets[0][1] + b"tampered"), *packets[1:])
        )
        self.assertFalse(
            replay_shared_incident(operation, provider_recipe=LIVE_RECIPE)[
                "operation_matches"
            ]
        )
        mailbox = copy.deepcopy(receipt)
        graph = decode_state(mailbox["after"]["graph"])
        batches = graph["outboxes"][3]
        first = batches[0]
        graph["outboxes"][3] = (Batch(first.sequence + 1, first.packets), *batches[1:])
        mailbox["after"]["graph"] = encode_state(graph)
        result = replay_shared_incident(mailbox, provider_recipe=LIVE_RECIPE)
        self.assertFalse(result["mailbox_matches"])
        self.assertTrue(result["differences"])
