"""Exact executor unit boundaries; no real monster qualification is claimed."""
from types import SimpleNamespace
import unittest

from native_triggered_spell_observation import TriggeredSpellObservations


import json
from pathlib import Path
from random import Random
from wakfu_server.combat_triggered_spell_handler import NativeTriggeredSpellHandler
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_execution_context import constructed_execution_context
from wakfu_server.combat_state_ledger import StateLedger


class TriggerGameplayTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(
            id=7, position=(0, 0, 0), hp=100, state_ledger=StateLedger(7)
        )
        fight = SimpleNamespace(
            id=18, phase="active", actors={7: actor}, owned_stat_effects={}
        )
        handler = NativeTriggeredSpellHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=lambda: 55,
            context=lambda *args: StatExecutionContext(True, True, None, False, None),
            authority=lambda *args: SimpleNamespace(targeting={"is_eGj": True}),
            rng=Random(1).random,
            executor=lambda *args: None,
        )
        effect = json.loads(
            (
                Path(__file__).parent
                / "fixtures/native_triggered_spell_observation398362.json"
            ).read_text()
        )["effect"]
        invocation = EffectInvocation(
            398362,
            245,
            7,
            7,
            (0, 0, 0),
            native_context_hex=constructed_execution_context().payload().hex(),
        )
        return handler, effect, invocation, actor

    def execute(self, mutation):
        handler, effect, invocation, actor = self.fixture()
        actor.effect_stats = {1: 100, 2: 10, 3: 5, 4: 6, 97: 0}
        handler.fight.native_effect_areas = {}
        handler.executor = lambda *args: mutation(handler.fight, actor)
        observer = TriggeredSpellObservations()
        with observer.observe(handler):
            handler(effect, {}, invocation)
        return observer.delivery_receipts(handler.packets)[0]

    def test_new_registered_actor_is_gameplay(self):
        row = self.execute(
            lambda fight, actor: fight.actors.update(
                {-8: SimpleNamespace(position=(1, 0, 0))}
            )
        )
        self.assertTrue(row["effectful_gameplay"])
        self.assertEqual(row["added_actor_ids"], [-8])

    def test_new_native_area_is_gameplay(self):
        row = self.execute(
            lambda fight, actor: fight.native_effect_areas.update(
                {
                    90: dict(
                        reference=566,
                        level=1,
                        cell=(0, 0, 0),
                        owner_id=7,
                        native_cells_xy=((0, 0),),
                        direction=0,
                    )
                }
            )
        )
        self.assertTrue(row["effectful_gameplay"])
        self.assertEqual(row["native_area_changes"][0]["area_uid"], 90)

    def test_resource_gain_and_armor_are_gameplay(self):
        row = self.execute(
            lambda fight, actor: actor.effect_stats.update({3: 6, 97: 10})
        )
        self.assertTrue(row["effectful_gameplay"])
        self.assertEqual(
            {v["stat"] for v in row["gameplay_actor_changes"][0]["statistics"]}, {3, 97}
        )

    def test_actual_position_change_is_gameplay(self):
        row = self.execute(lambda fight, actor: setattr(actor, "position", (1, 0, 0)))
        self.assertTrue(row["effectful_gameplay"])
        self.assertEqual(row["gameplay_actor_changes"][0]["position_after"], (1, 0, 0))

    def test_possible_cast_payment_alone_is_not_gameplay(self):
        row = self.execute(
            lambda fight, actor: actor.effect_stats.update({2: 6, 3: 4, 4: 5})
        )
        self.assertFalse(row["effectful_gameplay"])
        self.assertEqual(len(row["excluded_possible_caster_resource_payments"]), 3)

    def test_counters_metadata_and_empty_executor_are_not_gameplay(self):
        def metadata(fight, actor):
            actor.turn_count = 8
            fight.native_effect_uid_next = 999
            fight.native_effect_areas[90] = {"diagnostic_counter": 1}

        row = self.execute(metadata)
        self.assertFalse(row["effectful_gameplay"])
        self.assertFalse(row["effectful_state_or_hp"])

    def test_copied_native_book_change_is_gameplay(self):
        handler, effect, invocation, actor = self.fixture()
        actor.native_summon_action_book = {
            "actions": [{"reference": 4230, "level": 1, "uid": 1}]
        }
        handler.executor = lambda *args: actor.native_summon_action_book.update(
            actions=[{"reference": 4230, "level": 2, "uid": 2}]
        )
        observer = TriggeredSpellObservations()
        with observer.observe(handler):
            handler(effect, {}, invocation)
        row = observer.delivery_receipts(handler.packets)[0]
        self.assertTrue(row["effectful_gameplay"])
        self.assertEqual(
            row["gameplay_actor_changes"][0]["copied_book_after"], [(4230, 2)]
        )

    def test_copied_book_uid_only_change_is_not_gameplay(self):
        handler, effect, invocation, actor = self.fixture()
        actor.native_summon_action_book = {
            "actions": [{"reference": 4230, "level": 1, "uid": 1}]
        }
        handler.executor = lambda *args: actor.native_summon_action_book["actions"][
            0
        ].update(uid=2)
        observer = TriggeredSpellObservations()
        with observer.observe(handler):
            handler(effect, {}, invocation)
        self.assertFalse(
            observer.delivery_receipts(handler.packets)[0]["effectful_gameplay"]
        )
