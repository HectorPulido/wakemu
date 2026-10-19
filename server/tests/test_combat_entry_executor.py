"""Native entry contracts, route exclusions and private failure boundaries."""
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from dataclasses import FrozenInstanceError
from functools import wraps
import os
from random import Random
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_entry_executor import (
    ENTRY_ROUTES,
    entry_route,
    execute_entry_roots,
)
from wakfu_server.combat_normal_execution_origin import normal_execution_origin
from wakfu_server.combat_geometry_snapshot import source_snapshot


class EntryPolicyTests(unittest.TestCase):
    def test_route_contracts_are_immutable_and_summons_keep_entry_authority(self):
        with self.assertRaises(TypeError):
            ENTRY_ROUTES["npc"] = ENTRY_ROUTES["player"]
        with self.assertRaises(FrozenInstanceError):
            ENTRY_ROUTES["npc"].paid_player_events = True
        actor = SimpleNamespace(native_summon_source={"caster_id": -7})
        self.assertEqual(entry_route(actor, "player"), "summon.player")
        self.assertEqual(entry_route(actor, "npc"), "summon.npc")
        self.assertEqual(entry_route(actor, "weapon"), "weapon")
        with self.assertRaises(ValueError):
            entry_route(actor, "unknown")

    def run_roots(self, route):
        trace = []

        @contextmanager
        def active(preview, spell, **kwargs):
            trace.append(("active.enter", spell, kwargs))
            try:
                yield
            finally:
                trace.append("active.exit")

        @contextmanager
        def resolution():
            trace.append("resolution.enter")
            try:
                yield
            finally:
                trace.append("resolution.exit")

        @contextmanager
        def events(dispatcher, plan):
            trace.append("cast.enter")
            try:
                yield
            finally:
                trace.append("cast.exit")

        caster = SimpleNamespace(id=7)
        preview = SimpleNamespace(
            actors={7: caster, -7: SimpleNamespace(position=(1, 0, 0))},
            effect_resolution=resolution,
        )
        plan = dict(
            actor_id=7,
            spell_id=6266,
            evaluation_level=12,
            target_id=-7,
            target=(1, 0, 0),
        )
        dispatcher = SimpleNamespace(
            effects={
                str(ref): dict(
                    area_class="anD", native_target_selector={"class": "fcE", "mask": 3}
                )
                for ref in (2, 1)
            }
        )
        dispatcher.execute = (
            lambda invocation: trace.append(("root", invocation)) or invocation
        )
        with patch(
            "wakfu_server.combat_cost_payment_events.replay_paid_spell_costs",
            side_effect=lambda *args: trace.append("paid"),
        ), patch(
            "wakfu_server.combat_breeze_payment_events.replay_paid_breeze_costs",
            side_effect=lambda *args: trace.append("breeze"),
        ), patch(
            "wakfu_server.combat_direct_target.native_direct_target_policies",
            return_value={"1": (None, False), "2": (None, False)},
        ):
            outcomes = execute_entry_roots(
                preview,
                plan,
                caster,
                dispatcher,
                (2, 1),
                route=route,
                execution_origin=normal_execution_origin(plan),
                active_scope=active,
                event_scope=events,
            )
        return trace, outcomes

    def test_player_and_controlled_summon_replay_payments_before_ordered_roots(self):
        for route in ("player", "summon.player"):
            with self.subTest(route=route):
                trace, outcomes = self.run_roots(route)
                self.assertEqual(
                    trace[:5],
                    [
                        ("active.enter", 6266, {"level": 12}),
                        "resolution.enter",
                        "cast.enter",
                        "paid",
                        "breeze",
                    ],
                )
                self.assertEqual([i.reference for i in outcomes], [2, 1])
                self.assertTrue(all(i.native_explicit_target for i in outcomes))
                self.assertTrue(all(i.native_context_hex for i in outcomes))
                self.assertEqual(
                    trace[-3:], ["cast.exit", "resolution.exit", "active.exit"]
                )

    def test_owned_payment_runs_once_after_live_cast_scope_before_reactions_and_roots(
        self,
    ):
        trace = []
        caster = SimpleNamespace(id=7, ap=6)
        preview = SimpleNamespace(actors={7: caster}, effect_resolution=nullcontext)
        plan = dict(
            actor_id=7,
            spell_id=6266,
            evaluation_level=12,
            target_id=7,
            target=(0, 0, 0),
        )
        dispatcher = SimpleNamespace(
            effects={"1": {}},
            execute=lambda invocation: trace.append(("root", caster.ap)) or invocation,
        )

        @contextmanager
        def events(_dispatcher, _plan):
            trace.append(("cast.enter", caster.ap))
            caster.ap += 1  # Native1024 changes the live balance before payment.
            try:
                yield
            finally:
                trace.append(("cast.exit", caster.ap))

        calls = []

        def pay_resources():
            calls.append(caster.ap)
            trace.append(("pay", caster.ap))
            caster.ap -= 4

        with patch(
            "wakfu_server.combat_cost_payment_events.replay_paid_spell_costs",
            side_effect=lambda *args: trace.append(("paid-reaction", caster.ap)),
        ), patch(
            "wakfu_server.combat_breeze_payment_events.replay_paid_breeze_costs",
            side_effect=lambda *args: trace.append(("breeze-reaction", caster.ap)),
        ), patch(
            "wakfu_server.combat_direct_target.native_direct_target_policies",
            return_value={},
        ):
            execute_entry_roots(
                preview,
                plan,
                caster,
                dispatcher,
                (1,),
                route="player",
                execution_origin=normal_execution_origin(plan),
                active_scope=lambda *args, **kwargs: nullcontext(),
                event_scope=events,
                pay_resources=pay_resources,
            )

        self.assertEqual(calls, [7])
        self.assertEqual(
            trace,
            [
                ("cast.enter", 6),
                ("pay", 7),
                ("paid-reaction", 3),
                ("breeze-reaction", 3),
                ("root", 3),
                ("cast.exit", 3),
            ],
        )

    def test_insufficient_post_1024_owned_payment_never_replays_or_dispatches(self):
        trace = []
        caster = SimpleNamespace(id=7, ap=2)
        preview = SimpleNamespace(actors={7: caster}, effect_resolution=nullcontext)
        plan = dict(
            actor_id=7,
            spell_id=6266,
            evaluation_level=12,
            target_id=7,
            target=(0, 0, 0),
        )

        def fail_payment():
            trace.append("payment")
            raise ValueError("insufficient live PA")

        dispatcher = SimpleNamespace(
            effects={"1": {}}, execute=lambda *_: self.fail("root dispatched")
        )
        with patch(
            "wakfu_server.combat_cost_payment_events.replay_paid_spell_costs",
            side_effect=lambda *args: trace.append("reaction"),
        ), patch(
            "wakfu_server.combat_breeze_payment_events.replay_paid_breeze_costs",
            side_effect=lambda *args: trace.append("breeze"),
        ), patch(
            "wakfu_server.combat_direct_target.native_direct_target_policies",
            return_value={},
        ):
            with self.assertRaisesRegex(ValueError, "insufficient live PA"):
                execute_entry_roots(
                    preview,
                    plan,
                    caster,
                    dispatcher,
                    (1,),
                    route="player",
                    execution_origin=normal_execution_origin(plan),
                    active_scope=lambda *args, **kwargs: nullcontext(),
                    event_scope=lambda *args: nullcontext(),
                    pay_resources=fail_payment,
                )
        self.assertEqual(trace, ["payment"])

    def test_npc_and_native_summon_cannot_replay_player_payment_or_cast_events(self):
        for route in ("npc", "summon.npc"):
            with self.subTest(route=route):
                trace, outcomes = self.run_roots(route)
                self.assertEqual(
                    trace[:2], [("active.enter", 6266, {}), "resolution.enter"]
                )
                self.assertNotIn("paid", trace)
                self.assertNotIn("breeze", trace)
                self.assertNotIn("cast.enter", trace)
                self.assertTrue(all(i.native_context_hex for i in outcomes))
                self.assertFalse(any(i.native_explicit_target for i in outcomes))
                self.assertEqual([i.reference for i in outcomes], [2, 1])

    def test_weapon_has_no_active_spell_cast_events_or_normal_spell_context(self):
        trace, outcomes = self.run_roots("weapon")
        self.assertEqual(trace[0], "resolution.enter")
        self.assertEqual(trace[-1], "resolution.exit")
        self.assertEqual(len(trace), 4)
        self.assertTrue(all(i.native_context_hex is None for i in outcomes))
        self.assertFalse(any(i.native_explicit_target for i in outcomes))

    def test_unknown_route_rejects_before_dispatch(self):
        dispatcher = SimpleNamespace(
            execute=lambda *args: self.fail("dispatched invalid route")
        )
        with self.assertRaises(ValueError):
            execute_entry_roots(None, {}, None, dispatcher, (1,), route="invalid")

    def test_weapon_reads_native_level_source_for_each_ordered_root(self):
        rule = {"item_level": 12}
        caster = SimpleNamespace(id=7)
        preview = SimpleNamespace(effect_resolution=nullcontext)

        def execute(invocation):
            rule["item_level"] += 1
            return invocation

        outcomes = execute_entry_roots(
            preview,
            dict(evaluation_level=0, target_id=-7, target=(99, 99, 0)),
            caster,
            SimpleNamespace(execute=execute),
            (2, 1),
            route="weapon",
            native_level_source=lambda: rule["item_level"],
            native_cell=(1, 0, 0),
        )
        self.assertEqual([root.level for root in outcomes], [12, 13])
        self.assertTrue(all(root.cell == (1, 0, 0) for root in outcomes))

    def test_player_point_target_guard_does_not_lookup_ineligible_missing_root(self):
        caster = SimpleNamespace(id=7, position=(0, 0, 0))
        preview = SimpleNamespace(
            actors={7: caster, -7: SimpleNamespace(position=(2, 0, 0))},
            effect_resolution=nullcontext,
        )
        dispatcher = SimpleNamespace(effects={}, execute=lambda invocation: invocation)
        for target in (7, None, -99, -7):
            with self.subTest(target=target), patch(
                "wakfu_server.combat_cost_payment_events.replay_paid_spell_costs"
            ), patch(
                "wakfu_server.combat_breeze_payment_events.replay_paid_breeze_costs"
            ), patch(
                "wakfu_server.combat_direct_target.native_direct_target_policies",
                return_value={},
            ):
                plan = dict(
                    actor_id=7,
                    spell_id=6266,
                    evaluation_level=1,
                    target_id=target,
                    target=(1, 0, 0),
                )
                outcomes = execute_entry_roots(
                    preview,
                    plan,
                    caster,
                    dispatcher,
                    (999999,),
                    route="player",
                    execution_origin=normal_execution_origin(plan),
                    active_scope=lambda *args, **kwargs: nullcontext(),
                    event_scope=lambda *args: nullcontext(),
                )
                self.assertFalse(outcomes[0].native_explicit_target)


class PlayerEntryContractTests(unittest.TestCase):
    def setUp(self):
        import test_combat_spell_transaction as fixtures

        self.native = fixtures.SpellTransactionTests()
        self.native.setUp()
        self.addCleanup(self.native.doCleanups)
        self.native.cast_authority()

    def test_native_player_roots_cost_once_packets_exact_and_source_private(self):
        before = source_snapshot(self.native.fight)
        results = {}
        results["current"] = self.native.execute()
        new = results["current"]
        self.assertEqual(source_snapshot(self.native.fight), before)
        self.assertEqual(new.fight.actors[7].ap, 2)
        self.assertLess(new.fight.actors[-7].hp, 20)
        self.assertEqual(
            [opcode for opcode, _ in new.packets], [13494, 13420, 12588, 12678, 12613]
        )

    def test_invalid_owner_never_enters_shared_root_dispatch(self):
        from wakfu_server.combat_spell_transaction import prepare_spell_transaction
        from wakfu_server.spells import encode_deck

        before = source_snapshot(self.native.fight)
        with patch(
            "wakfu_server.combat_spell_transaction.execute_entry_roots"
        ) as execute:
            with self.assertRaises(ValueError):
                prepare_spell_transaction(
                    self.native.body,
                    self.native.character,
                    self.native.fight,
                    4,
                    encode_deck([6266]),
                    wp_current=6,
                    action_id=1,
                    line_of_sight=lambda *args: True,
                    runtime_factory=self.native.factory,
                    conditional_context=self.native.cast_authority(),
                )
            execute.assert_not_called()
            self.assertEqual(source_snapshot(self.native.fight), before)

    def test_player_payment_reaction_precedes_reading_plan_roots(self):
        results = {}

        def payment_reaction(dispatcher, plan):
            plan["effect_ids"] = ()

        with patch(
            "wakfu_server.combat_cost_payment_events.replay_paid_spell_costs",
            side_effect=payment_reaction,
        ):
            results["current"] = self.native.execute()
        new = results["current"]
        self.assertEqual(new.outcomes, ())
        self.assertEqual(new.fight.actors[-7].hp, 20)

    def test_late_root_failure_keeps_costs_hp_and_packets_private(self):
        from wakfu_server.combat_effect_dispatch import UnsupportedEffectExecution

        before = source_snapshot(self.native.fight)

        def unsupported(preview, plan):
            dispatcher, packets = self.native.factory(preview, plan)
            dispatcher.handlers.clear()
            return (dispatcher, packets)

        with self.assertRaises(UnsupportedEffectExecution):
            self.native.execute(unsupported)
        self.assertEqual(source_snapshot(self.native.fight), before)

    def test_validated_npc_keeps_pre_factory_spell_and_level(self):
        from wakfu_server.combat_npc_spell import prepare_validated_npc_spell

        self.native.fight.actors[7].effect_stats[4] = 6
        admitted = self.native.execute().plan
        original_level = admitted["evaluation_level"]
        results = {}

        def mutate_after_validation(preview, plan):
            plan["spell_id"] = 9999
            plan["evaluation_level"] = 123
            return (SimpleNamespace(execute=lambda invocation: invocation), [])

        results["current"] = prepare_validated_npc_spell(
            self.native.fight,
            deepcopy(admitted),
            dict(costs=admitted["costs"], roots=admitted["effect_ids"]),
            self.native.character,
            factory=mutate_after_validation,
            action_id=1,
        )
        new = results["current"]
        self.assertTrue(new.outcomes)
        self.assertTrue(all((root.level == original_level for root in new.outcomes)))
        self.assertEqual(new.plan["evaluation_level"], 123)


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class NativeEntryContractTests(unittest.TestCase):
    def test_weapon_factory_cannot_replace_native_item_level_or_cell(self):
        import test_combat_weapon as fixture
        from wakfu_server.combat_weapon import prepare_server_weapon
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.spells import encode_deck

        character, monster, fight = fixture.weapon_fixture(11, 200)
        character = fixture.equipped(character, 2027)
        fight.actors[-7].position = (1, 0, 0)
        results = {}

        def mutating_runtime(*args, **kwargs):
            factory, adapter = server_runtime(*args, **kwargs)

            @wraps(factory)
            def mutate(preview, plan):
                dispatcher, packets = factory(preview, plan)
                plan["evaluation_level"] = 0
                plan["target"] = (99, 99, 0)
                return (dispatcher, packets)

            return (mutate, adapter)

        with patch(
            "wakfu_server.combat_server_spell.server_runtime",
            side_effect=mutating_runtime,
        ):
            results["current"] = prepare_server_weapon(
                struct.pack(">qqbiih", 7, 1000, 15, 1, 0, 0),
                character,
                {-7: monster},
                fight,
                3,
                encode_deck((), ()),
                action_id=1,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=Random(1),
            )
        new = results["current"]
        self.assertLess(new.fight.actors[-7].hp, fight.actors[-7].hp)

    def test_native_weapon_cost_damage_rng_and_order_preserve_native_contract(self):
        import test_combat_weapon as fixture
        from wakfu_server.combat_weapon import prepare_server_weapon
        from wakfu_server.spells import encode_deck

        character, monster, fight = fixture.weapon_fixture(11, 200)
        character = fixture.equipped(character, 2027)
        fight.actors[-7].position = (1, 0, 0)
        before = source_snapshot(fight)
        results, states = ({}, {})
        rng = Random(1)
        results["current"] = prepare_server_weapon(
            struct.pack(">qqbiih", 7, 1000, 15, 1, 0, 0),
            character,
            {-7: monster},
            fight,
            3,
            encode_deck((), ()),
            action_id=1,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        states["current"] = rng.getstate()
        new = results["current"]
        self.assertEqual(source_snapshot(fight), before)
        repeat_rng = Random(1)
        repeated = prepare_server_weapon(
            struct.pack(">qqbiih", 7, 1000, 15, 1, 0, 0),
            character,
            {-7: monster},
            fight,
            3,
            encode_deck((), ()),
            action_id=1,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=repeat_rng,
        )
        self.assertEqual(states["current"], repeat_rng.getstate())
        self.assertEqual(
            (new.plan, new.outcomes, new.events, new.packets),
            (repeated.plan, repeated.outcomes, repeated.events, repeated.packets),
        )
        self.assertEqual(source_snapshot(new.fight), source_snapshot(repeated.fight))
        self.assertLess(new.fight.actors[-7].hp, fight.actors[-7].hp)
        self.assertEqual(
            new.fight.actors[7].ap, fight.actors[7].ap - new.plan["costs"]["ap"]
        )
        self.assertEqual([op for op, _ in new.packets[:3]], [13494, 13420, 13509])
        self.assertEqual(new.plan["native_retained_container"]["type"], 12)

    def test_actual_owned_npc_spatial_attack_preserves_native_contract(self):
        import test_combat_spatial_pilot_new_attack as fixture
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.spells import default_deck

        fixture.SpatialPilotNewAttackTests.setUpClass()
        template = fixture.SpatialPilotNewAttackTests.template
        fight = template.fight
        before = source_snapshot(fight)
        results = {}
        results["current"] = prepare_npc_spell(
            fight,
            dict(
                type="cast",
                spellId=5868,
                level=42,
                target=list(template.pc.position),
                targetId=template.pc.id,
            ),
            template.character,
            {template.monster["id"]: template.monster},
            default_deck(template.character),
            action_id=11,
            rng=Random(7),
        )
        new = results["current"]
        self.assertEqual(source_snapshot(fight), before)
        self.assertNotEqual(
            new.fight.actors[template.pc.id].position, template.pc.position
        )
        self.assertEqual(new.fight.actors[template.npc.id].ap, template.npc.ap - 2)
        self.assertEqual(
            [op for op, _ in new.packets[:4]], [13494, 13420, 12588, 12678]
        )
        self.assertTrue(any((event["kind"] == "npc_cast" for event in new.events)))
