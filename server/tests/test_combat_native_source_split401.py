"""Pure native differential and actual calculated source continuation regressions."""
import json
from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace
import unittest
from wakfu_server.combat_source_split import (
    split_plan,
    split_actual_source,
    bind_calculated_damage_clone,
    calculated_source_clone_gate,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_event_replay import NativeEventSource
from wakfu_server.combat_final_modifier import final_modifier_source
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
from wakfu_server.combat_runner_target import bind_runner_target
from wakfu_server.combat_random_earth_damage import dispatcher_child_gate

HERE = Path(__file__).parent / "fixtures/next_central_recovery"


class NativeSplitTests(unittest.TestCase):
    def test_144_actual_native_branches_and_clone_uid_context(self):
        rows = [
            json.loads(s)
            for s in (HERE / "native-oracle.jsonl").read_text().splitlines()
        ]
        self.assertEqual(len(rows), 144)
        for row in rows:
            with self.subTest(row=row):
                plan = split_plan(
                    row["value"],
                    row["ratio"],
                    row["cap"],
                    source_family=row["source_family"],
                    target_current_hp=row["target_current_hp"],
                )
                self.assertEqual(plan.remainder, row["original_after"])
                self.assertEqual(plan.action == "redirect", row["original_redirected"])
                if plan.action == "clone":
                    self.assertEqual(plan.amount, row["clone_value"])
                    self.assertEqual(
                        row["calls"], ["bbn", "allocate_uid", "bbq", "bbJ"]
                    )
                    self.assertEqual(row["clone_uid"], row["clone_base_uid"])
                    self.assertNotIn(row["clone_uid"], (101, 88))
                    self.assertTrue(row["clone_target_rebound"])
                    self.assertTrue(row["clone_caster_rebound"])
                    self.assertFalse(row["clone_bfD"])
                    self.assertTrue(row["clone_context_first"])
                    self.assertTrue(row["clone_context_second"])
                    self.assertTrue(row["clone_context_trigger_null"])
                else:
                    self.assertEqual(row["calls"], [])

    def test_fresh_subscription_uses_inherited_deferred_wire(self):
        from wakfu_server.combat_subscription_runners import (
            deferred_payload,
            DEFERRED_RUNNERS,
        )

        self.assertEqual(DEFERRED_RUNNERS[401], "eZh")
        kwargs = dict(
            uid=101,
            base_uid=101,
            generic_effect=800,
            caster_id=7,
            target_id=-8,
            cell=(1, 0, 0),
            timing_payload=b"",
            container_type=11,
            container_id=(800 << 16) | 1,
        )
        # Both constructors only use inherited fresh eZR serialization.
        self.assertEqual(
            deferred_payload(family=401, **kwargs),
            deferred_payload(family=400, **kwargs),
        )

    def test_negative_one_cap_uses_current_hp_not_maximum(self):
        plan = split_plan(100, 100, -1, source_family=1, target_current_hp=29)
        self.assertEqual((plan.amount, plan.remainder), (29, 71))

    def test_int_multiplication_overflow_precedes_division(self):
        self.assertEqual(split_plan(2**31 - 1, 100, 0, source_family=1).amount, -1)

    def test_bool_and_missing_operands_are_not_native_ints(self):
        with self.assertRaises(ValueError):
            split_plan(True, 50, 0, source_family=1)

    def setUp(self):
        actors = [
            Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True),
            Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1),
            Actor(-8, 1, (2, 0, 0), 100, 6, 3, 4, 1),
        ]
        self.fight = Fight(
            77,
            actors,
            {a.position for a in actors},
            {0: {actors[0].position}, 1: {a.position for a in actors[1:]}},
        )
        self.fight.ready(3)
        for a in actors:
            a.effect_stats = {92: 0, 97: 0, 100: 0}
            a.effect_maxima = {92: 0}
            a.effect_frozen = frozenset()
            a.physical_radius = 0
        self.packets = []
        self.next_uid = 100
        self.calculations = 0
        self.events = []
        self.original_runner = None

        def allocate():
            self.next_uid += 1
            return self.next_uid

        def context(*args):
            self.calculations += 1
            return DamageExecutionContext(False, True, False, True, 11, False)

        self.handler = NativeDamageHandler(
            self.fight,
            self.packets,
            action_id=1,
            allocate_uid=allocate,
            rng=lambda: 0.99,
            context=context,
        )
        self.handler.calculated_clone_gate = lambda *a: True
        self.effect = dict(
            effect_class=1,
            parameters=[100, 0],
            native_effect_flags=[],
            native_localization_enabled=True,
        )
        self.invocation = EffectInvocation(339483, 1, 7, -7, (1, 0, 0))

    def source(self, inv, data):
        return NativeEventSource(
            data["uid"],
            inv.reference,
            data["value"],
            inv.caster_id,
            inv.target_id,
            inv.cell,
            (0,),
            2,
            inv.target_id,
            None,
            False,
            False,
            False,
            True,
            effect_action_id=1,
            runner_modifier=data["runner_modifier"],
        )

    def attach(self, ratio=50, cap=0, caster_code=0):
        test = self

        class Events:
            def phase(_, effect, inv, **data):
                test.events.append((data["uid"], data["channel"], inv))
                if data["channel"] == 2 and inv.target_id == -7:
                    test.original_runner = data["runner_modifier"]
                    with final_modifier_source(test.source(inv, data)):
                        witness = replace(
                            inv,
                            target_id=-8,
                            native_trigger_context={"uid": data["uid"]},
                        )
                        split_actual_source(
                            test.fight, witness, ratio, cap, caster_code=caster_code
                        )

        self.handler.event_lifecycle = Events()

    def test_actual_damage_clone_reuses_calculated_source_no_C_or_L1(self):
        self.attach()
        self.assertTrue(self.handler(self.effect, {}, self.invocation))
        self.assertEqual(self.calculations, 1)
        self.assertEqual((self.fight.actors[-7].hp, self.fight.actors[-8].hp), (50, 50))
        fields = [
            _identity_fields(p[19:]) for opcode, p in self.packets if opcode == 12613
        ]
        self.assertEqual(len(fields), 2)
        clone, original = fields
        self.assertEqual((clone[1], clone[2]), (102, 102))
        self.assertEqual((original[1], original[2]), (101, 101))
        self.assertEqual((clone[4], original[4]), (50, 50))
        self.assertEqual([c for uid, c, inv in self.events if uid == 102], [2, 3, 4])
        clone_inv = next(inv for uid, c, inv in self.events if uid == 102)
        self.assertEqual(clone_inv.cell, self.invocation.cell)
        self.assertIsNone(clone_inv.native_trigger_context)
        actual_row = next(
            json.loads(s)
            for s in (HERE / "native-oracle.jsonl").read_text().splitlines()
            if "clone_context_hex" in s
        )
        self.assertEqual(clone_inv.native_context_hex, actual_row["clone_context_hex"])

    def test_whole_redirect_uses_actual_original_uid_and_target(self):
        self.attach(100)
        self.handler(self.effect, {}, self.invocation)
        self.assertEqual((self.fight.actors[-7].hp, self.fight.actors[-8].hp), (100, 0))
        self.assertEqual(self.next_uid, 101)
        self.assertEqual(len(self.packets), 1)

    def test_missing_clone_authority_does_not_reduce_original_amount(self):
        self.handler.calculated_clone_gate = None
        self.attach()
        with self.assertRaisesRegex(ValueError, "clone continuation"):
            self.handler(self.effect, {}, self.invocation)
        self.assertEqual(self.original_runner.value, 100)
        self.assertEqual(self.fight.actors[-8].hp, 100)

    def test_real_clone_gate_context_bypasses_criteria_and_probability(self):
        calls = []
        dispatcher = SimpleNamespace(
            _active_activation=None,
            group_retention=None,
            condition_context=lambda inv: calls.append("context"),
            probability_accepts=lambda *a: (_ for _ in ()).throw(
                AssertionError("probability")
            ),
        )
        self.effect.update(minimum_level=0, maximum_level=32767, criteria="unavailable")
        self.handler.calculated_clone_gate = calculated_source_clone_gate(
            native_eligibility=lambda *a: True
        )
        self.attach()
        self.handler(self.effect, {}, self.invocation)
        self.assertEqual((self.fight.actors[-7].hp, self.fight.actors[-8].hp), (50, 50))
        self.assertEqual(calls, [])

    def test_manager_caster_without_actual_Qf_binding_is_withheld(self):
        self.attach(caster_code=2)
        with self.assertRaisesRegex(ValueError, "manager PV"):
            self.handler(self.effect, {}, self.invocation)
        self.assertEqual(self.original_runner.value, 100)

    def test_clone_uid_reuse_rejects_before_original_amount_mutation(self):
        self.handler.allocate_uid = lambda: 101
        self.attach()
        with self.assertRaisesRegex(ValueError, "fresh allocated"):
            self.handler(self.effect, {}, self.invocation)
        self.assertEqual(self.original_runner.value, 100)
        self.assertEqual(self.fight.actors[-8].hp, 100)

    def test_native_rejected_clone_keeps_original_remainder_and_cleans_prepared(self):
        self.handler.calculated_clone_gate = lambda *a: False
        self.attach()
        self.handler(self.effect, {}, self.invocation)
        self.assertEqual(
            (self.fight.actors[-7].hp, self.fight.actors[-8].hp), (50, 100)
        )
        self.assertEqual(len(self.packets), 1)
        self.assertFalse(self.handler.prepared)
        self.assertFalse(self.handler.runner_modifiers)

    def test_clone_preserves_actual_source_container_and_anchor(self):
        container = {
            "present": True,
            "type": 11,
            "id": (800 << 16) | 1,
            "spell_id": 800,
            "level": 1,
        }
        self.invocation = replace(self.invocation, native_retained_container=container)
        self.attach()
        self.handler(self.effect, {}, self.invocation)
        clone_inv = next(inv for uid, channel, inv in self.events if uid == 102)
        self.assertIs(clone_inv.native_retained_container, container)
        self.assertEqual(clone_inv.cell, (1, 0, 0))
        self.assertEqual(clone_inv.target_id, -8)

    def test_current_hp_cap_changes_actual_clone_and_original_packets(self):
        self.fight.actors[-8].hp = 29
        self.attach(100, -1)
        self.handler(self.effect, {}, self.invocation)
        self.assertEqual((self.fight.actors[-7].hp, self.fight.actors[-8].hp), (29, 0))
        amounts = [_identity_fields(p[19:])[4] for opcode, p in self.packets]
        self.assertEqual(amounts, [29, 71])

    def test_zero_split_does_not_clone_or_modify_actual_source(self):
        self.attach(0)
        self.handler(self.effect, {}, self.invocation)
        self.assertEqual((self.fight.actors[-7].hp, self.fight.actors[-8].hp), (0, 100))
        self.assertEqual(self.next_uid, 101)


if __name__ == "__main__":
    unittest.main()
