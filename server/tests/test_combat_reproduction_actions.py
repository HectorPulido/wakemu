"""Offline adapters execute the real runtime against installed native fixtures."""
import copy
import os
import random
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_reproduction_actions import AUTHORITY_RECIPE, execute
from wakfu_server.spells import encode_deck
import test_combat_spell_transaction as native_fixture


class ReproductionActionTests(unittest.TestCase):
    def test_actual_malformed_cast_replays_before_any_rng_binding(self):
        from wakfu_server.combat_input_observation import (
            observe_combat_inputs,
            replay_combat_inputs,
        )
        from wakfu_server.combat_reproduction_actions import prepare_context

        runtime, inputs = self.fixture()
        private = copy.deepcopy(runtime)
        action = dict(type="player_spell", owner_id=3, body=b"malformed", critical=None)
        rng = random.Random(17)
        context = prepare_context(runtime, action, inputs, rng, lambda: 1.0)
        with self.assertRaises(ValueError) as actual:
            with observe_combat_inputs() as observed:
                execute(
                    runtime, action, inputs, rng, lambda: 1.0, prepared_context=context
                )
        snapshot = observed.snapshot()
        self.assertEqual(snapshot["rng_streams"], [])
        context = prepare_context(private, action, inputs, rng, lambda: 1.0)
        with self.assertRaises(ValueError) as replayed:
            with replay_combat_inputs(snapshot):
                execute(
                    private, action, inputs, rng, lambda: 1.0, prepared_context=context
                )
        self.assertEqual(type(replayed.exception), type(actual.exception))
        self.assertEqual(str(replayed.exception), str(actual.exception))

    def test_valid_native_cast_with_missing_rng_tape_is_infrastructure_error(self):
        from wakfu_server.combat_input_observation import (
            InputReplayMismatch,
            replay_combat_inputs,
        )
        from wakfu_server.combat_reproduction_actions import prepare_context

        runtime, inputs = self.fixture()
        target = runtime.fight.actors[-7].position
        action = dict(
            type="player_spell",
            owner_id=3,
            body=struct.pack(">qqiih", 7, (7 << 32) | 6266, *target),
            critical=None,
        )
        rng = random.Random(17)
        context = prepare_context(runtime, action, inputs, rng, lambda: 1.0)
        empty = dict(
            schema="wakemu-combat-observed-inputs-v1",
            events=[],
            rng_streams=[],
            incomplete=[],
        )
        with self.assertRaises(InputReplayMismatch):
            with replay_combat_inputs(empty):
                execute(
                    runtime, action, inputs, rng, lambda: 1.0, prepared_context=context
                )

    def test_native_spell_tape_preserves_internal_and_external_rng_ownership(self):
        from wakfu_server.combat_input_observation import (
            observe_combat_inputs,
            replay_combat_inputs,
        )
        from wakfu_server.combat_reproduction_actions import prepare_context
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_los import authoritative_visible

        for external in (False, True):
            with self.subTest(external=external), patch.dict(
                os.environ, {"WAKFU_NATIVE_AREA_CALLBACKS": "1"}
            ):
                runtime, inputs = self.fixture()
                private = copy.deepcopy(runtime)
                target = runtime.fight.actors[-7].position
                action = dict(
                    type="player_spell",
                    body=struct.pack(">qqiih", 7, (7 << 32) | 6266, *target),
                    owner_id=3,
                    critical=None,
                )
                fallback = random.Random(88)
                serialize, _ = prepare_context(
                    runtime, action, inputs, fallback, lambda: 123.0
                )
                with observe_combat_inputs() as observed:
                    transaction = prepare_server_spell(
                        action["body"],
                        inputs["character"],
                        inputs["monsters"],
                        runtime.fight,
                        action["owner_id"],
                        inputs["deck_blob"],
                        action_id=runtime.action_id + 1,
                        critical=None,
                        rng=random.Random(17) if external else None,
                        player_characters=inputs["player_characters"],
                        deck_blobs=inputs["deck_blobs"],
                        line_of_sight=lambda origin, target, state: authoritative_visible(
                            inputs["map_id"],
                            origin,
                            target,
                            state,
                            blocking_footprints={
                                actor.id: {actor.position[:2]}
                                for actor in state.actors.values()
                                if actor.hp > 0
                            },
                        ),
                    )
                    packets = commit_spell_transaction(
                        runtime, transaction, stats_serializer=serialize
                    )
                context = prepare_context(
                    private, action, inputs, fallback, lambda: 123.0
                )
                with replay_combat_inputs(observed.snapshot()) as receipt:
                    result = execute(
                        private,
                        action,
                        inputs,
                        fallback,
                        lambda: 123.0,
                        prepared_context=context,
                    )
                self.assertTrue(receipt.ownership_known)
                self.assertEqual(result["packets"], packets)
                self.assertEqual(result["plan"], transaction.plan)
                self.assertEqual(result["events"], transaction.events)
                self.assertEqual(
                    private.fight.actors[-7].hp, runtime.fight.actors[-7].hp
                )

    def fixture(self, breed=15, level=20, spells=(6266,)):
        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            breed, level, native_qi=True, target_distance=1
        )
        monster = dict(monster, level=fight.actors[monster["id"]].effective_level)
        deck = encode_deck(spells)
        inputs = dict(
            authority_recipe=AUTHORITY_RECIPE,
            character=character,
            monsters={monster["id"]: monster},
            deck_blob=deck,
            player_characters={character["id"]: character},
            deck_blobs={character["id"]: deck},
            map_id=character["map_id"],
            native_events=True,
            area_callbacks=True,
        )
        from wakfu_server.combat_server_spell import prepare_server_initialization

        fight, _ = prepare_server_initialization(
            character,
            inputs["monsters"],
            fight,
            character["account_id"],
            deck,
            action_id=1,
            rng=random.Random(17),
            fight_start=True,
            player_characters=inputs["player_characters"],
            deck_blobs=inputs["deck_blobs"],
        )
        runtime = RuntimeMessages(fight)
        runtime.action_id = 1  # Same initialization reservation as prepare_ready.
        return runtime, inputs

    def replay(self, runtime, action, inputs, seed=1):
        with patch.dict(os.environ, {"WAKFU_NATIVE_AREA_CALLBACKS": "1"}):
            return execute(runtime, action, inputs, random.Random(seed), lambda: 123.0)

    def test_unknown_action_and_recipe_fail_before_runtime_mutation(self):
        runtime, inputs = self.fixture()
        before = copy.deepcopy(vars(runtime))
        for action, sources in (
            ({"type": "ready"}, inputs),
            ({"type": "ack", "body": b"", "module": "os"}, inputs),
            ({"type": "ack", "body": b""}, dict(inputs, authority_recipe="unknown")),
            ({"type": "ack", "body": b""}, dict(inputs, deck_blobs={})),
        ):
            with self.assertRaises(ValueError):
                self.replay(runtime, action, sources)
            self.assertEqual(runtime.action_id, before["action_id"])
            self.assertEqual(runtime.fight.events, before["fight"].events)
            self.assertIsNone(runtime.stats_serializer)

    def test_real_spell_preparation_and_packet_delivery_repeat_exactly(self):
        from wakfu_server.combat_input_observation import observe_combat_inputs

        runtime, inputs = self.fixture()
        target = runtime.fight.actors[-7].position
        action = dict(
            type="player_spell",
            body=struct.pack(">qqiih", 7, (7 << 32) | 6266, *target),
            owner_id=3,
            critical=None,
        )
        second = copy.deepcopy(runtime)
        before_hp = runtime.fight.actors[-7].hp
        with observe_combat_inputs() as observed:
            first = self.replay(runtime, action, inputs)
        repeated = self.replay(second, action, inputs)
        self.assertLess(runtime.fight.actors[-7].hp, before_hp)
        self.assertEqual(first["packets"], repeated["packets"])
        self.assertEqual(first["events"], repeated["events"])
        self.assertEqual(first["plan"], repeated["plan"])
        self.assertEqual(runtime.native_action_id, second.native_action_id)
        self.assertEqual(runtime.action_id, 2)
        rng_events = [
            event for event in observed.snapshot()["events"] if event["kind"] == "rng"
        ]
        labels = [event["label"] for event in rng_events]
        self.assertIn("player_spell.before_critical", labels)
        critical_index = labels.index("player_spell.before_critical")
        self.assertEqual(labels[critical_index + 1], "server_runtime")
        self.assertIs(rng_events[critical_index]["external"], True)
        self.assertIs(rng_events[critical_index + 1]["external"], True)
        self.assertEqual(
            rng_events[critical_index]["stream_id"],
            rng_events[critical_index + 1]["stream_id"],
        )

    def test_real_weapon_executes_owned_item_and_current_snapshot(self):
        from test_combat_weapon import equipped

        runtime, inputs = self.fixture(11, 200, ())
        character = equipped(inputs["character"], 2027)
        inputs = dict(inputs, character=character, player_characters={7: character})
        target = runtime.fight.actors[-7].position
        before_hp = runtime.fight.actors[-7].hp
        result = self.replay(
            runtime,
            dict(
                type="player_weapon",
                body=struct.pack(">qqbiih", 7, 1000, 15, *target),
                owner_id=3,
                critical=False,
            ),
            inputs,
        )
        self.assertLess(runtime.fight.actors[-7].hp, before_hp)
        self.assertEqual(result["packets"][0][0], 13509)
        self.assertIn(12873, [opcode for opcode, _ in result["packets"]])

    def test_real_move_preserves_native_registration_and_emits_packets(self):
        from wakfu_server.combat_qi_fight import current_registry

        runtime, inputs = self.fixture()
        actor = runtime.fight.actors[7]
        origin = actor.position
        destination = next(
            cell
            for cell in sorted(runtime.fight.walkable)
            if cell != runtime.fight.actors[-7].position
            and abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) == 1
            and cell[2] == origin[2]
            and (runtime.fight.edges is None or (origin, cell) in runtime.fight.edges)
        )
        old_mp = actor.mp
        # Reproduction graph capture omits this callable service; the adapter
        # must restore it from the explicit ordinary authority recipe.
        runtime.fight.native_rail_movement_authority = None
        result = self.replay(
            runtime,
            dict(type="move", owner_id=3, body=struct.pack(">qiih", 7, *destination)),
            inputs,
        )
        self.assertEqual(runtime.fight.actors[7].position, destination)
        self.assertLess(runtime.fight.actors[7].mp, old_mp)
        registry = current_registry(runtime.fight)
        row = next(
            row for row in registry.slots if row and row["identity"] == ["actor", 7]
        )
        self.assertEqual(tuple(row["position"]), destination[:2])
        self.assertIn(13624, [opcode for opcode, _ in result["packets"]])

    def test_real_end_turn_then_ack_releases_pending_packets(self):
        from wakfu_server.combat_timeline_snapshot import current_wire_turn

        runtime, inputs = self.fixture()
        previous = runtime.fight.turn_id
        ended = self.replay(
            runtime,
            dict(
                type="end_turn",
                owner_id=3,
                actor_id=7,
                turn_id=current_wire_turn(runtime.fight),
            ),
            inputs,
        )
        self.assertEqual(runtime.awaiting_ack, previous)
        self.assertTrue(runtime.pending)
        self.assertIn(12502, [opcode for opcode, _ in ended["packets"]])
        result = self.replay(
            runtime, dict(type="ack", body=struct.pack(">i", previous)), inputs
        )
        self.assertIsNone(runtime.awaiting_ack)
        self.assertFalse(runtime.pending)
        self.assertTrue(result["packets"])
        self.assertEqual(runtime.clock(), 123.0)

    def test_malformed_spell_uses_real_decoder_and_leaves_resources(self):
        runtime, inputs = self.fixture()
        before = runtime.fight.actors[7].ap
        with self.assertRaises(ValueError):
            self.replay(
                runtime,
                dict(type="player_spell", owner_id=3, body=b"bad", critical=False),
                inputs,
            )
        self.assertEqual(runtime.fight.actors[7].ap, before)
        self.assertEqual(runtime.action_id, 1)

    def test_real_npc_spell_uses_native_book_and_target_validation(self):
        from wakfu_server.combat_timeline_snapshot import current_wire_turn

        runtime, inputs = self.fixture()
        previous = runtime.fight.turn_id
        self.replay(
            runtime,
            dict(
                type="end_turn",
                owner_id=3,
                actor_id=7,
                turn_id=current_wire_turn(runtime.fight),
            ),
            inputs,
        )
        self.replay(runtime, dict(type="ack", body=struct.pack(">i", previous)), inputs)
        self.assertEqual(runtime.fight.current.id, -7)
        before_hp = runtime.fight.actors[7].hp
        action = dict(
            type="npc_spell",
            action=dict(
                type="cast",
                spellId=7962,
                level=1,
                targetId=7,
                target=list(runtime.fight.actors[7].position),
            ),
        )
        result = self.replay(runtime, action, inputs)
        self.assertLess(runtime.fight.actors[7].hp, before_hp)
        self.assertEqual(result["transaction"].plan["actor_id"], -7)
        self.assertTrue(result["packets"])
