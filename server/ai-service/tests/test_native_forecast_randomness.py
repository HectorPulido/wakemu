"""Common NPC forecast samples preserve native formula and source authority."""
from copy import deepcopy
import hashlib
import json
import random
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import patch

from wakfu_ai.native.native_oracle import NativeOracle


class NativeForecastRandomnessTests(unittest.TestCase):
    def setUp(self):
        self.oracle = NativeOracle.__new__(NativeOracle)
        self.oracle.characters = {10: {}}
        self.actor = SimpleNamespace(
            id=-7, turn_count=3, ap=6, mp=3, hp=20, direction=3, position=(0, 0, 0)
        )
        self.fight = SimpleNamespace(
            id=177,
            turn_id=7,
            current=self.actor,
            actors={-7: self.actor},
            events=[],
            sequence=53,
        )
        self.action = dict(
            type="cast", spellId=5768, level=5, targetId=10, target=[3, 0, 0]
        )

    def samples(self, action=None):
        rng = self.oracle._rng(self.fight, action or self.action)
        return [rng.random() for _ in range(4)]

    def cast_event(self, target=10, **changes):
        return dict(
            kind="npc_cast",
            turn_id=7,
            actor_id=-7,
            spell_id=5768,
            target_id=target,
            **changes
        )

    def test_repeated_preview_is_deterministic_and_does_not_change_source(self):
        before = deepcopy(vars(self.fight))
        self.assertEqual(self.samples(), self.samples())
        self.assertEqual(vars(self.fight), before)

    def test_empty_padding_movement_facing_hp_and_costs_do_not_reroll_actor_target(
        self,
    ):
        expected = self.samples()
        self.fight.events.extend([self.cast_event(None), dict(kind="movement")])
        self.fight.sequence += 2
        self.actor.ap, self.actor.mp, self.actor.hp, self.actor.direction = 3, 0, 12, 7
        self.actor.position = (1, 0, 0)
        self.action["target"] = [4, 0, 0]
        self.assertEqual(self.samples(), expected)

    def test_repeated_same_target_cast_and_next_turn_change_samples(self):
        expected = self.samples()
        self.fight.events.append(self.cast_event())
        self.assertNotEqual(self.samples(), expected)
        self.fight.events.clear()
        self.fight.turn_id += 1
        self.assertNotEqual(self.samples(), expected)
        self.fight.turn_id -= 1
        self.actor.turn_count += 1
        self.assertNotEqual(self.samples(), expected)

    def test_other_spell_actor_target_or_previous_turn_does_not_increment_ordinal(self):
        expected = self.samples()
        for field, value in [
            ("spell_id", 999),
            ("actor_id", -8),
            ("target_id", 11),
            ("turn_id", 6),
        ]:
            event = self.cast_event()
            event[field] = value
            self.fight.events.append(event)
        self.assertEqual(self.samples(), expected)

    def test_ground_repetitions_vary_without_rerolling_occupied_stream(self):
        ground = dict(self.action, targetId=None, target=[2, 0, 0])
        baseline, occupied = self.samples(ground), self.samples()
        self.fight.events.append(self.cast_event(None))
        self.assertNotEqual(self.samples(ground), baseline)
        self.assertEqual(self.samples(), occupied)
        self.assertNotEqual(
            self.samples(dict(ground, target=[1, 0, 0])), self.samples(ground)
        )

    def test_same_draw_does_not_hide_native_mastery_damage_changes(self):
        from wakfu_server.combat_damage_healing import damage_amount

        context = dict(
            critical=False,
            single_target=False,
            area=False,
            melee=True,
            berserk=False,
            front=True,
        )

        def amount(stats):
            return damage_amount(
                10,
                2,
                stats,
                {},
                arithmetic_context=context,
                coefficient_mask=3,
                rng=self.oracle._rng(self.fight, self.action).random,
            )

        self.assertGreater(amount({20: 100}), amount({20: 0}))

    def test_player_move_and_boundary_forecasts_retain_state_key_seed_contract(self):
        fake = ModuleType("wakfu_server.combat_tactical_ai")
        fake.state_key = lambda fight: "complete-source-state"
        with patch.dict("sys.modules", {"wakfu_server.combat_tactical_ai": fake}):
            for action in (
                dict(type="move", path=[[1, 0, 0]]),
                dict(boundary="start", actorId=-7),
                self.action,
            ):
                if action is self.action:
                    self.oracle.characters[-7] = {}
                encoded = json.dumps(
                    dict(state=fake.state_key(self.fight), action=action),
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
                expected = random.Random(
                    int(hashlib.sha256(encoded).hexdigest(), 16)
                ).random()
                self.assertEqual(
                    self.oracle._rng(self.fight, action).random(), expected
                )


class NativeForecastPaddingIntegrationTests(unittest.TestCase):
    def test_white_gobball_empty_cast_does_not_improve_following_occupied_damage(self):
        from validate_monster_spell_activation import fixture
        from wakfu_server.combat_geometry_snapshot import source_snapshot
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        fight, character, monsters, deck = fixture(39, 4, (-5, -7, -1))
        runtime = RuntimeMessages(fight)
        oracle = NativeOracle(
            runtime,
            characters={7: character},
            monsters=monsters,
            decks={7: deck},
            excluded_decks={7: frozenset()},
            viewer_id=7,
            flags={},
        )
        occupied = dict(
            type="cast", spellId=5768, level=4, targetId=7, target=[-5, -7, -1]
        )
        empty = dict(occupied, targetId=None, target=[-9, -8, -1])
        before = source_snapshot(fight)
        direct, direct_packets, direct_tx = oracle.preview(runtime, occupied)
        self.assertEqual(source_snapshot(fight), before)
        empty_runtime, empty_packets, empty_tx = oracle.preview(runtime, empty)
        self.assertEqual(source_snapshot(fight), before)
        self.assertTrue(direct_packets)
        self.assertTrue(empty_packets)
        self.assertIsNone(empty_tx.plan["target_id"])
        self.assertEqual(empty_runtime.fight.actors[7].hp, fight.actors[7].hp)
        self.assertEqual(empty_runtime.fight.actors[-200].ap, fight.actors[-200].ap - 3)
        self.assertFalse(any(event["kind"] == "damage" for event in empty_tx.events))
        empty_before = source_snapshot(empty_runtime.fight)
        padded, padded_packets, padded_tx = oracle.preview(empty_runtime, occupied)
        self.assertEqual(source_snapshot(empty_runtime.fight), empty_before)
        self.assertEqual(source_snapshot(fight), before)
        self.assertTrue(padded_packets)
        self.assertEqual(direct_tx.plan["target_id"], 7)
        self.assertEqual(padded_tx.plan["target_id"], 7)
        direct_damage = fight.actors[7].hp - direct.fight.actors[7].hp
        padded_damage = fight.actors[7].hp - padded.fight.actors[7].hp
        self.assertGreater(direct_damage, 0)
        self.assertEqual(padded_damage, direct_damage)
        for transaction in (direct_tx, padded_tx):
            self.assertTrue(
                any(
                    event["kind"] == "damage" and event["target_id"] == 7
                    for event in transaction.events
                )
            )


if __name__ == "__main__":
    unittest.main()
