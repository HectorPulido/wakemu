import unittest
import json
from pathlib import Path
from itertools import count
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.spell_audit import states_catalog
from wakfu_server.combat_state_handler import NativeStateHandler, StateCarrierContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server import native_catalog


class NativeStateHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = states_catalog()

    def setUp(self):
        pc = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 5, 1)
        self.fight = Fight(
            77,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        self.fight.ready(3)
        self.packets = []
        self.children = []
        self.uids = count(200)
        self.handler = NativeStateHandler(
            self.fight,
            self.packets,
            self.catalog,
            action_id=1,
            allocate_uid=lambda: next(self.uids),
            execute_child=lambda inv: self.children.append(inv),
            context=lambda *args: StateCarrierContext(
                -1, 0, False, None, 100, False, False, False, 0, None
            ),
        )
        self.effect = dict(effect_class=304)
        self.invocation = EffectInvocation(91, 1, 7, 7, (0, 0, 0))

    def apply(self):
        return self.handler(
            self.effect, {"parameters": [3442, 20, -1]}, self.invocation
        )

    def test_native_state_retains_source_and_owned_carrier(self):
        self.assertTrue(self.apply())
        entry = self.fight.actors[7].state_ledger.entries[0]
        self.assertEqual(
            (entry.reference, entry.level, entry.caster_id, entry.uid),
            (3442, 20, 7, 200),
        )
        self.assertEqual(self.packets[0][0], 12613)
        proto = bytes.fromhex(self.fight.state_wire_payloads[200])
        fields = _identity_fields(proto)
        self.assertEqual((fields[1], fields[2]), (200, 100))
        for child in self.children:
            self.assertEqual(
                (child.base_uid, child.state_uid, child.level), (None, 200, 20)
            )

    def test_accumulation_replaces_only_original_owned_carrier(self):
        self.apply()
        self.apply()
        self.assertEqual([p[0] for p in self.packets], [12613, 13560, 12613])
        self.assertEqual(set(self.fight.state_wire_payloads), {201})
        entry = self.fight.actors[7].state_ledger.entries[0]
        self.assertEqual((entry.uid, entry.level), (201, 40))
        removal = self.packets[1][1]
        self.assertEqual(_identity_fields(removal[18:-16])[1], 200)

    def test_bad_context_rejects_before_ledger_change(self):
        self.handler.context = lambda *args: None
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.fight.actors[7].state_ledger.entries, ())
        self.assertEqual(self.packets, [])

    def test_unhandled_child_rolls_back_state_and_carrier_payload(self):
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            run_effect_transaction,
            UnsupportedEffectExecution,
        )
        from wakfu_server.combat_conditions import ConditionContext

        effects = dict(self.catalog["effects"])
        effects["91"] = dict(
            effect_class=304,
            parameters=[3442, 0, 20, 0, -1, 0],
            parameter_count=3,
            probability_base=100,
            probability_per_level=0,
            minimum_level=1,
            maximum_level=200,
            criteria="",
            children=[],
        )

        def factory(preview):
            packets = []
            dispatcher = EffectDispatcher(
                effects,
                {},
                resolve=lambda e, i: (i,),
                condition_context=lambda _: ConditionContext({}),
                probability_accepts=lambda p, i: p == 100,
                group_cells=lambda *args: (),
                actor_position=lambda uid: preview.actors[uid].position,
            )
            dispatcher.handlers[304] = NativeStateHandler(
                preview,
                packets,
                self.catalog,
                action_id=1,
                allocate_uid=lambda: 200,
                execute_child=dispatcher.execute,
                context=lambda *args: StateCarrierContext(
                    -1, 0, False, None, 100, False, False, False, 0, None
                ),
            )
            return dispatcher

        with self.assertRaisesRegex(UnsupportedEffectExecution, "No handler"):
            run_effect_transaction(self.fight, [self.invocation], factory)
        self.assertEqual(self.fight.actors[7].state_ledger.entries, ())
        self.assertEqual(self.fight.state_wire_payloads, {})

    def test_real_catalogue_applicator_consumes_all_three_parameters(self):
        from wakfu_server.combat_definitions import effect_profile
        from wakfu_server.spell_audit import catalog as effect_catalog

        effect = effect_catalog()["effects"]["167716"]
        values = effect_profile(effect, 1)
        self.assertEqual(values["parameters"], [3896, 1, -1])
        native = EffectInvocation(167716, 1, 7, 7, (0, 0, 0))
        self.assertTrue(self.handler(effect, values, native))
        event = next(e for e in self.fight.events if e["kind"] == "state_applied")
        self.assertEqual((event["state_id"], event["level"]), (3896, 1))

    def test_real_nondefault_class304_chance_uses_mode_stats_and_bounded_draw(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "protocol/native-class-captured-effect-closure.json"
        )
        with native_catalog.open(path, "rt") as source:
            definition = json.load(source)["effects"]["87531"]
        from wakfu_server.combat_definitions import effect_profile

        values = effect_profile(definition, 1)
        self.assertEqual(values["parameters"], [1733, 1, 50])
        caster, target = self.fight.actors[7], self.fight.actors[-7]
        caster.effect_stats = {77: 40}
        target.effect_stats = {78: 20}
        invocation = EffectInvocation(87531, 1, caster.id, target.id, target.position)

        self.handler.state_random = lambda limit: 60
        parameters = self.handler._parameters(definition, values, invocation)
        self.assertTrue(
            self.handler._application_chance(definition, values, invocation, parameters)
        )  # NEGATIF mode: 50 + (40 - 20)% of 50 = 60.
        self.handler.state_random = lambda limit: 61
        self.assertFalse(
            self.handler._application_chance(definition, values, invocation, parameters)
        )

        # Native f2i truncates a negative fractional resistance toward zero.
        caster.effect_stats = {77: 0}
        target.effect_stats = {78: 5}
        self.handler.state_random = lambda limit: 48
        self.assertTrue(
            self.handler._application_chance(definition, values, invocation, parameters)
        )  # 50 + trunc(-2.5) = 48, inclusive boundary.
        self.handler.state_random = lambda limit: 49
        self.assertFalse(
            self.handler._application_chance(definition, values, invocation, parameters)
        )

        from wakfu_server.combat_state_resistance_metadata import (
            native_state_resistance_mode,
        )

        self.assertEqual(native_state_resistance_mode(1472)["name"], "POSITIF")
        no_resistance = dict(parameters, reference=1472, chance_parameter=25)
        no_resistance_values = dict(values, parameters=[1472, 1, 25])
        self.handler.state_random = lambda limit: 25
        self.assertTrue(
            self.handler._application_chance(
                definition, no_resistance_values, invocation, no_resistance
            )
        )
        self.handler.state_random = lambda limit: 26
        self.assertFalse(
            self.handler._application_chance(
                definition, no_resistance_values, invocation, no_resistance
            )
        )

        unknown = dict(parameters, reference=759, chance_parameter=50)
        with self.assertRaisesRegex(ValueError, "outside proven"):
            self.handler._application_chance(definition, values, invocation, unknown)

    def test_all_published_nondefault_chance_nodes_use_their_native_resistance_mode(
        self,
    ):
        from wakfu_server.combat_definitions import effect_profile
        from wakfu_server.combat_state_resistance_metadata import (
            native_state_resistance_mode,
        )

        protocol = Path(__file__).resolve().parents[1] / "protocol"
        area_path = protocol / "native-area-effect-trees.json"
        captured_path = protocol / "native-class-captured-effect-closure.json"
        with native_catalog.open(area_path, "rt") as source:
            area_effects = json.load(source)["effects"]
        with native_catalog.open(captured_path, "rt") as source:
            captured_effects = json.load(source)["effects"]

        # These are the nine non-sentinel eWu nodes in the published class and
        # area closures. The expected modes are independently sealed in the
        # native resistance metadata catalog.
        cases = (
            (area_effects, 92058, 1863, 25, "NEGATIF", 0, 30),
            (area_effects, 194076, 4761, 25, "NEGATIF", 0, 30),
            (area_effects, 194077, 4762, 25, "NEGATIF", 0, 30),
            (area_effects, 194078, 4764, 25, "NEGATIF", 0, 30),
            (area_effects, 71640, 1492, 100, "POSITIF", 2, 100),
            (area_effects, 181598, 4348, 30, "NEGATIF", 0, 36),
            (area_effects, 182404, 4348, 80, "NEGATIF", 0, 96),
            (captured_effects, 87531, 1733, 50, "NEGATIF", 0, 60),
            (captured_effects, 87535, 1733, 75, "NEGATIF", 0, 90),
        )
        caster, target = self.fight.actors[7], self.fight.actors[-7]
        caster.effect_stats = {77: 40}
        target.effect_stats = {78: 20}

        for (
            effects,
            effect_id,
            state_id,
            raw_chance,
            mode_name,
            ordinal,
            expected,
        ) in cases:
            with self.subTest(effect_id=effect_id, state_id=state_id):
                definition = effects[str(effect_id)]
                values = effect_profile(definition, 1)
                self.assertEqual(definition["effect_class"], 304)
                self.assertEqual(values["parameters"][0], state_id)
                self.assertEqual(values["parameters"][2], raw_chance)
                mode = native_state_resistance_mode(state_id)
                self.assertEqual(
                    (mode["enum_class"], mode["name"], mode["ordinal"]),
                    ("fza", mode_name, ordinal),
                )
                invocation = EffectInvocation(
                    effect_id, 1, caster.id, target.id, target.position
                )
                parameters = self.handler._parameters(definition, values, invocation)
                self.handler.state_random = lambda limit, draw=expected: draw
                self.assertTrue(
                    self.handler._application_chance(
                        definition, values, invocation, parameters
                    )
                )
                if expected < 100:
                    self.handler.state_random = lambda limit, draw=expected + 1: draw
                    self.assertFalse(
                        self.handler._application_chance(
                            definition, values, invocation, parameters
                        )
                    )
                else:
                    self.handler.state_random = lambda limit: self.fail(
                        "100% native chance must not consume a random draw"
                    )
                    self.assertTrue(
                        self.handler._application_chance(
                            definition, values, invocation, parameters
                        )
                    )

    def _kill_native_target(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        initialize_global_pv_collections(self.fight, tuple(self.fight.actors))
        target = self.fight.actors[-7]
        with self.fight.effect_resolution():
            self.fight.apply_effect_damage(7, -7, target.hp)
            self.assertEqual(target.hp, 0)
            self.assertEqual(self.fight.phase, "active")
        self.assertEqual(self.fight.phase, "finished")
        return target

    def test_flag15_state_application_can_complete_on_registered_off_play_target(self):
        from wakfu_server.combat_global_pv_collections import global_fighter_guards

        target = self.fight.actors[-7]
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        initialize_global_pv_collections(self.fight, tuple(self.fight.actors))
        effect = {"effect_class": 304, "native_effect_flags": [15]}
        invocation = EffectInvocation(92, 1, 7, -7, target.position)
        with self.fight.effect_resolution():
            self.fight.apply_effect_damage(7, -7, target.hp)
            self.assertTrue(global_fighter_guards(self.fight, -7)["baG"])
            self.assertTrue(
                self.handler(effect, {"parameters": [3442, 20, -1]}, invocation)
            )
            self.assertEqual(target.state_ledger.entries[0].reference, 3442)
        self.assertEqual(self.fight.phase, "finished")

    def test_unflagged_state_rejects_off_play_and_flag15_still_requires_active_phase(
        self,
    ):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        target = self._kill_native_target()
        invocation = EffectInvocation(92, 1, 7, -7, target.position)
        parameters = {"parameters": [3442, 20, -1]}
        before = target.state_ledger.entries
        with self.assertRaisesRegex(ValueError, "Dynamic native corpse guard"):
            self.handler(
                {"effect_class": 304, "native_effect_flags": []},
                parameters,
                invocation,
            )
        self.assertEqual(target.state_ledger.entries, before)
        with self.assertRaisesRegex(
            ValueError, "Invalid state source, target or fight phase"
        ):
            self.handler(
                {"effect_class": 304, "native_effect_flags": [15]},
                parameters,
                invocation,
            )
        self.assertEqual(target.state_ledger.entries, before)

    def test_unregistered_off_play_status_is_not_inferred_from_numeric_hp(self):
        from wakfu_server.combat_global_pv_collections import (
            global_fighter_guards,
            initialize_global_pv_collections,
        )

        initialize_global_pv_collections(self.fight, tuple(self.fight.actors))
        target = self.fight.actors[-7]
        target.hp = (
            0  # The native PV status remains IN_PLAY; this is not a death event.
        )
        self.assertFalse(global_fighter_guards(self.fight, -7)["baG"])
        effect = {"effect_class": 304, "native_effect_flags": []}
        invocation = EffectInvocation(92, 1, 7, -7, target.position)
        with self.fight.effect_resolution():
            self.assertTrue(
                self.handler(effect, {"parameters": [3442, 20, -1]}, invocation)
            )
        self.assertEqual(target.state_ledger.entries[0].reference, 3442)

    def test_non_sentinel_chance_rejects_state_without_resistance_provenance(self):
        with self.assertRaisesRegex(ValueError, "outside proven"):
            self.handler(self.effect, {"parameters": [759, 20, 50]}, self.invocation)
        self.assertEqual(self.fight.actors[7].state_ledger.entries, ())
        self.assertEqual(self.packets, [])
