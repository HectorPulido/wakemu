"""Private integration controls exercising the real eXt handler candidate."""
import importlib.util
import unittest
import struct
from pathlib import Path
from types import SimpleNamespace
from copy import deepcopy
from dataclasses import replace
from wakfu_server.combat_random_earth_damage import (
    NativeRandomEarthDamageHandler,
    initialized_handler_type,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation, run_effect_transaction
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_damage_handler import DamageExecutionContext
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.fight_checkpoint_store import snapshot
from test_combat_damage_handler import DamageHandlerTests

from wakfu_server import combat_damage_handler as module

CandidateDamage = initialized_handler_type(module.NativeDamageHandler)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        fixture = DamageHandlerTests()
        fixture.setUp()
        self.fight, self.packets = fixture.fight, fixture.packets
        self.effect = dict(fixture.effect, effect_class=636, parameters=[50, 0, 150, 0])
        self.effect["target_masks"] = [None] * 7
        self.invocation = EffectInvocation(69207, 100, 7, -7, (1, 0, 0))
        self.events, self.draws = [], []
        self.counts = {}
        self.ids = iter(range(100, 200))
        self.child_gate = lambda source, invocation: True

    def handler(self, fight=None):
        fight = self.fight if fight is None else fight
        outer = self

        class Events:
            def phase(self, effect, invocation, **data):
                outer.events.append(
                    (
                        effect["effect_class"],
                        data["uid"],
                        data["channel"],
                        invocation.reference,
                        data["runner_modifier"].owner,
                    )
                )

        events = Events()

        def child(source):
            return CandidateDamage(
                fight,
                self.packets,
                action_id=1,
                allocate_uid=lambda: source.uid,
                rng=lambda: 0.99,
                context=lambda *args: module.DamageExecutionContext(
                    False, True, False, True, 11, False
                ),
            )

        def rng():
            self.draws.append("sample")
            return 0.99

        return NativeRandomEarthDamageHandler(
            fight=fight,
            allocate_uid=lambda: next(self.ids),
            rng=rng,
            actor_authority=SimpleNamespace(property_counts=lambda f, a: self.counts),
            child_factory=child,
            child_execution_gate=lambda s, i: self.child_gate(s, i),
            parent_events=events,
            damage_events=events,
            parent_context=lambda *args: StatExecutionContext(
                True, True, None, False, b""
            ),
        )

    def test_real_damage_child_packet_and_distinct_parent_lifecycle(self):
        original = deepcopy(self.effect)
        handler = self.handler()
        self.assertTrue(handler(self.effect, {}, self.invocation))
        self.assertEqual(self.effect, original)
        self.assertEqual(self.draws, ["sample"])
        self.assertEqual(
            [
                (family, channel, owner)
                for family, uid, channel, ref, owner in self.events
            ],
            [
                (636, 1, "Qe"),
                (636, 2, "Qe"),
                (3, 1, "eXt"),
                (3, 2, "eXt"),
                (3, 3, "eXt"),
                (3, 4, "eXt"),
                (636, 3, "Qe"),
                (636, 4, "Qe"),
            ],
        )
        self.assertEqual(
            {uid for family, uid, *rest in self.events if family == 636}, {100}
        )
        self.assertEqual(
            {uid for family, uid, *rest in self.events if family == 3}, {101}
        )
        self.assertEqual(
            {ref for family, uid, channel, ref, owner in self.events}, {69207}
        )
        self.assertEqual(len(self.packets), 1)
        self.assertEqual(struct.unpack_from(">i", self.packets[0][1], 13)[0], 3)
        self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], 149)
        self.assertEqual(
            self.fight.actors[-7].hp, 16
        )  # 149 minus15barrier20armor30virtual.
        self.assertEqual(handler.prepared, {})

    def test_minimize_priority_and_maximize_keep_real_packet_amount(self):
        for counts, expected in [({106: 1, 107: 1}, 50), ({107: 1}, 150)]:
            with self.subTest(counts=counts):
                self.setUp()
                self.counts = counts
                self.handler()(self.effect, {}, self.invocation)
                self.assertEqual(self.draws, [])
                self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], expected)

    def test_parent_context_forcing_is_not_applied_twice_to_child(self):
        from wakfu_server.combat_value_transfer import transfer_value_context

        self.fight.actors[7].effect_stats[23] = 100  # Earth mastery doubles forcedbase.
        inv = replace(
            self.invocation, native_context_hex=transfer_value_context(b"", 70).hex()
        )
        self.handler()(self.effect, {}, inv)
        self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], 140)

    def test_missing_pb_authority_rejects_without_damage_or_packet(self):
        self.counts = None
        before = snapshot(self.fight)
        handler = self.handler()
        with self.assertRaisesRegex(ValueError, "Complete native PB"):
            handler(self.effect, {}, self.invocation)
        self.assertEqual(snapshot(self.fight), before)
        self.assertEqual(self.packets, [])
        self.assertEqual(handler.prepared, {})

    def test_child_bbh_gate_runs_after_calculation_before_application(self):
        before = snapshot(self.fight)
        seen = []

        def gate(source, invocation):
            seen.append(list(self.events))
            return False

        self.child_gate = gate
        self.assertTrue(self.handler()(self.effect, {}, self.invocation))
        self.assertEqual(snapshot(self.fight), before)
        self.assertEqual(self.packets, [])
        self.assertEqual([family for family, *rest in seen[0]], [636, 636, 3])
        self.assertEqual(
            [(family, channel) for family, uid, channel, ref, owner in self.events],
            [(636, 1), (636, 2), (3, 1), (636, 3), (636, 4)],
        )

    def test_child_definition_bridge_keeps_strict_original_pk_identity(self):
        from wakfu_server.combat_random_earth_damage import InitializedEarthChild
        from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
        from test_combat_forced_retirement import ForcedRetirementTests

        retention = ForcedRetirementTests().fixture()[4]
        original = dict(
            self.effect,
            variant=0,
            minimum_level=0,
            maximum_level=32767,
            native_execution_mode=2,
        )
        retention.metadata = {"effects": {"69207": dict(original, definition_type=2)}}
        parent = replace(self.invocation, native_running_uid=100)
        runner = NativeRunnerAmount(100, 636, rng=lambda: 0.99, value=149)
        source = InitializedEarthChild.from_parent(
            original, parent, uid=101, runner=runner
        )
        child = replace(parent, native_running_uid=101)
        # Existing strict retained guard rejects the projected runner family.
        with self.assertRaisesRegex(ValueError, "identity differs"):
            retention.definition(source.effect, child)
        self.assertEqual(
            source.definition(retention, source.effect, child)["effect_class"], 636
        )
        identifiers = source.identifiers(retention, source.effect, child)
        self.assertEqual(identifiers["effect_action_id"], 3)
        self.assertEqual(identifiers["native_container"]["type"], 11)
        forged = dict(source.effect, parameters=[0, 0, 0, 0])
        with self.assertRaisesRegex(ValueError, "differs from actual"):
            source.definition(retention, forged, child)
        with self.assertRaisesRegex(ValueError, "differs from actual"):
            source.definition(retention, source.effect, replace(child, reference=69208))
        unsealed = object.__new__(InitializedEarthChild)
        with self.assertRaisesRegex(ValueError, "differs from actual"):
            unsealed.verify(source.effect, child)

    def test_real_transaction_failure_keeps_source_identity_and_damage_unchanged(self):
        before, target = snapshot(self.fight), self.fight.actors[-7]

        def factory(preview):
            handler = self.handler(preview)

            def execute(invocation):
                handler(self.effect, {}, self.invocation)
                raise ValueError("after real initialized child damage")

            return SimpleNamespace(execute=execute)

        with self.assertRaisesRegex(ValueError, "initialized child damage"):
            run_effect_transaction(self.fight, [self.invocation], factory)
        self.assertEqual(snapshot(self.fight), before)
        self.assertIs(self.fight.actors[-7], target)


"""Private factory checks with real event replay, bounded fixture metadata.

The PK metadata row is a controlled unit fixture, not an admission receipt.
Effect operands/flags/timing are the exact sealed native69207 record.
"""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from dataclasses import replace
from copy import deepcopy
from unittest.mock import patch
from test_combat_ordinary_damage_events import OrdinaryDamageEventsTests
from wakfu_server.combat_damage_handler import DamageExecutionContext
from wakfu_server.combat_effect_runtime import NativeRuntimeContexts
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields

SEALED_NATIVE_METADATA = {
    "152544": {
        "definition_dispellable": False,
        "definition_type": 2,
        "effect_class": 25,
        "event_caster_code": 0,
        "event_execution_count": -1,
        "event_execution_count_per_level": 0.0,
        "event_global_subscription": False,
        "event_priority": 0,
        "event_reverse_subscription": False,
        "event_suppresses_level_one": False,
        "event_target_code": 0,
        "maximum_level": 32767,
        "minimum_level": 0,
        "owner_on_caster": False,
        "parameters": [1000.0, 0.0, 0.0, 0.0],
        "subscription": False,
        "variant": 0,
    },
    "308265": {
        "definition_dispellable": False,
        "definition_type": 2,
        "effect_class": 330,
        "event_caster_code": 2,
        "event_execution_count": 1,
        "event_execution_count_per_level": 0.0,
        "event_global_subscription": False,
        "event_priority": 0,
        "event_reverse_subscription": True,
        "event_suppresses_level_one": False,
        "event_target_code": 2,
        "maximum_level": 32767,
        "minimum_level": 0,
        "owner_on_caster": False,
        "parameters": [],
        "subscription": True,
        "variant": 0,
    },
    "308266": {
        "definition_dispellable": False,
        "definition_type": 2,
        "effect_class": 330,
        "event_caster_code": 0,
        "event_execution_count": -1,
        "event_execution_count_per_level": 0.0,
        "event_global_subscription": False,
        "event_priority": 0,
        "event_reverse_subscription": False,
        "event_suppresses_level_one": False,
        "event_target_code": 0,
        "maximum_level": 32767,
        "minimum_level": 0,
        "owner_on_caster": False,
        "parameters": [],
        "subscription": False,
        "variant": 0,
    },
    "308267": {
        "definition_dispellable": False,
        "definition_type": 2,
        "effect_class": 400,
        "event_caster_code": 0,
        "event_execution_count": -1,
        "event_execution_count_per_level": 0.0,
        "event_global_subscription": False,
        "event_priority": 0,
        "event_reverse_subscription": False,
        "event_suppresses_level_one": False,
        "event_target_code": 0,
        "maximum_level": 32767,
        "minimum_level": 0,
        "owner_on_caster": False,
        "parameters": [],
        "subscription": False,
        "variant": 0,
    },
    "359836": {
        "definition_dispellable": False,
        "definition_type": 2,
        "effect_class": 400,
        "event_caster_code": 2,
        "event_execution_count": -1,
        "event_execution_count_per_level": 0.0,
        "event_global_subscription": False,
        "event_priority": 0,
        "event_reverse_subscription": True,
        "event_suppresses_level_one": False,
        "event_target_code": 2,
        "maximum_level": 32767,
        "minimum_level": 0,
        "owner_on_caster": False,
        "parameters": [],
        "subscription": True,
        "variant": 0,
    },
    "98920": {
        "definition_dispellable": None,
        "definition_type": 1,
        "effect_class": 1,
        "event_caster_code": 0,
        "event_execution_count": -1,
        "event_execution_count_per_level": 0.0,
        "event_global_subscription": False,
        "event_priority": 0,
        "event_reverse_subscription": False,
        "event_suppresses_level_one": False,
        "event_target_code": 0,
        "maximum_level": 32767,
        "minimum_level": 0,
        "owner_on_caster": False,
        "parameters": [10000.0, 0.0],
        "subscription": False,
        "variant": 0,
    },
    "69207": {
        "definition_dispellable": False,
        "definition_type": 2,
        "effect_class": 636,
        "event_caster_code": 0,
        "event_execution_count": -1,
        "event_execution_count_per_level": 0.0,
        "event_global_subscription": False,
        "event_priority": 0,
        "event_reverse_subscription": False,
        "event_suppresses_level_one": False,
        "event_target_code": 0,
        "maximum_level": 32767,
        "minimum_level": 0,
        "owner_on_caster": False,
        "parameters": [50.0, 0.0, 150.0, 0.0],
        "subscription": False,
        "variant": 0,
    },
}

from wakfu_server import combat_effect_runtime as runtime


class RealRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OrdinaryDamageEventsTests.setUpClass()
        cls.native_effect = {
            "application_flag": "NONE",
            "area_class": "anD",
            "area_native": "point",
            "children": [],
            "criteria": "",
            "effect_class": 636,
            "maximum_level": 32767,
            "minimum_level": 0,
            "native_definition_class": "eVy",
            "native_effect_flags": [17],
            "native_execution_mode": 2,
            "native_hmi_actions": {
                "rzc": [],
                "rzd": [],
                "rze": [],
                "rzf": [],
                "rzg": [],
                "rzh": [],
            },
            "native_localization_enabled": True,
            "native_target_selector": {"class": "fcE", "mask": 1},
            "native_timing_definition": {
                "clock_on_caster": False,
                "clock_on_target": True,
                "esr": False,
                "ryE": 0,
                "ryF": 0.0,
                "ryG": False,
                "ryH": 0,
                "ryI": 0.0,
            },
            "parameter_count": 2,
            "parameters": [50.0, 0.0, 150.0, 0.0],
            "probability_base": 100.0,
            "probability_per_level": 0.0,
            "removal_flag": "NONE",
            "target_masks": [None, None, None, None, None, None, None],
            "variant": 0,
        }

    def setUp(self):
        fixture = OrdinaryDamageEventsTests()
        import test_combat_event_replay as native_fixture

        # Enrich only this NEW test's detached fixture, using exact sealed
        # eVn.cyc coefficients. Original fixture/class assertions stay intact.
        copied_fixture = deepcopy(native_fixture.NativeEventReplayTests.fixture)
        for reference, row in copied_fixture["retained_metadata"]["effects"].items():
            row["event_execution_count_per_level"] = SEALED_NATIVE_METADATA[reference][
                "event_execution_count_per_level"
            ]
        with patch.object(
            native_fixture.NativeEventReplayTests, "fixture", copied_fixture
        ):
            fixture.setUp()
        fixture.f.fixture = copied_fixture
        from wakfu_server.combat_summon import RegisteredSummonAuthority

        fixture.adapter.actor_authority = RegisteredSummonAuthority(
            fixture.adapter.actor_authority
        )
        self.fixture = fixture
        self.fight = fixture.fight
        effects = deepcopy(fixture.f.effects)
        effects["69207"] = deepcopy(self.native_effect)
        metadata = deepcopy(fixture.f.fixture["retained_metadata"])
        row = deepcopy(SEALED_NATIVE_METADATA["69207"])
        metadata["effects"]["69207"] = row
        factory = runtime.NativeEffectRuntimeFactory(
            effects=effects,
            state_catalog={"effects": {}, "states": []},
            characteristic_registry={"effects": {"400": {"runner": "eXE"}}},
            action_id=1,
            contexts=fixture.adapter.contexts(),
            summon_authority=fixture.adapter.actor_authority,
        )
        with patch(
            "wakfu_server.combat_retained_runtime.native_retained_metadata",
            return_value=metadata,
        ):
            self.dispatcher, self.packets = factory(
                self.fight, dict(spell_id=6266, evaluation_level=1)
            )
        self.inv = EffectInvocation(69207, 1, 7, -7, (1, 0, 0))
        self.seen = []

    def execute(self, invocation=None):
        original = type(self.dispatcher.replay_event).__call__

        def capture(replay, source, **kwargs):
            self.seen.append(
                (
                    source.channel,
                    source.uid,
                    source.effect_action_id,
                    source.generic_effect,
                    source.value,
                    source.runner_modifier.owner,
                )
            )
            return original(replay, source, **kwargs)

        with patch.object(type(self.dispatcher.replay_event), "__call__", capture):
            return self.dispatcher.execute(
                self.inv if invocation is None else invocation
            )

    def test_registered_factory_uses_real_events_original_pk_and_separate_child(self):
        self.assertTrue(self.execute())
        self.assertEqual(
            [row[0] for row in self.seen],
            [10, 1, 20, 2, 10, 1, 20, 2, 30, 3, 40, 4, 30, 3, 40, 4],
        )
        parent = [r for r in self.seen if r[2] == 636]
        child = [r for r in self.seen if r[2] == 3]
        self.assertEqual({r[1] for r in parent}, {901})
        self.assertEqual({r[1] for r in child}, {902})
        self.assertEqual({r[3] for r in self.seen}, {69207})
        self.assertEqual({r[5] for r in parent}, {"Qe"})
        self.assertEqual({r[5] for r in child}, {"eXt"})
        self.assertEqual(len(self.packets), 1)  # parent mu(true): only eXt wire.
        amount = _identity_fields(self.packets[0][1][19:])[4]
        self.assertTrue(50 <= amount < 150)
        self.assertEqual(self.fight.actors[-7].hp, 12000 - amount)

    def test_child_probability_callback_runs_after_real_child_calculation(self):
        decisions = []

        def probability(probability, invocation):
            decisions.append((probability, invocation.native_running_uid))
            return len(decisions) == 1

        self.dispatcher.probability_accepts = probability
        self.assertTrue(self.execute())
        self.assertEqual(decisions, [(100.0, 901), (100.0, 902)])
        self.assertEqual([r[0] for r in self.seen if r[2] == 3], [10, 1])
        self.assertEqual(self.packets, [])
        self.assertEqual(self.fight.actors[-7].hp, 12000)

    def test_real_registered_target_pb75_blocks_child_after_calculation(self):
        target = self.fight.actors[-7]
        # Current PB authority, not a targeting boolean inferred from HP.
        counts = dict(
            self.fixture.adapter.actor_authority.property_counts(self.fight, target)
        )
        counts[75] = -1
        target.native_fight_property_counts = counts
        self.assertTrue(self.execute())
        self.assertEqual([r[0] for r in self.seen if r[2] == 3], [10, 1])
        self.assertEqual(self.packets, [])
        self.assertEqual(target.hp, 12000)

    def test_actual_cancelled_parent_has_only_real_l1_no_child(self):
        from wakfu_server.combat_effects import _integer

        context = b"".join(
            _integer(k, v)
            for k, v in (
                (1, 0),
                (2, 0),
                (4, -1),
                (5, 1),
                (6, 0),
                (7, 0),
                (8, 1),
                (9, 0),
            )
        )
        self.assertFalse(
            self.execute(replace(self.inv, native_context_hex=context.hex()))
        )
        self.assertEqual([r[0] for r in self.seen], [10, 1])
        self.assertTrue(all(r[2] == 636 for r in self.seen))
        self.assertEqual(self.packets, [])
        self.assertEqual(self.fight.actors[-7].hp, 12000)

    def test_actual_cancelled_child_context_has_native_flag_identity(self):
        from wakfu_server.combat_effects import _integer
        from wakfu_server.combat_random_earth_damage import native_child_context

        invocation = replace(self.inv, native_context_hex=_integer(8, 1).hex())
        self.assertEqual(native_child_context(invocation), (False, False, True))
        with self.assertRaisesRegex(ValueError, "Duplicate native"):
            native_child_context(
                replace(
                    invocation,
                    native_context_hex=(_integer(8, 1) + _integer(8, 0)).hex(),
                )
            )

    def test_actual_probability_bypass_context_preserves_child_bypass(self):
        from wakfu_server.combat_random_group import probability_bypass_context
        from wakfu_server.combat_effects import _integer

        context = b"".join(
            _integer(k, v)
            for k, v in (
                (1, 0),
                (2, 0),
                (4, -1),
                (5, 1),
                (6, 0),
                (7, 0),
                (8, 0),
                (9, 0),
            )
        )
        self.dispatcher.probability_accepts = lambda *args: self.fail(
            "native bypass ignored"
        )
        self.assertTrue(
            self.execute(
                replace(
                    self.inv,
                    native_context_hex=probability_bypass_context(context).hex(),
                )
            )
        )
        self.assertEqual(len(self.packets), 1)
