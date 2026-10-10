"""Factory carry binding with explicit original constructor PS fixture.

These fixtures do not prove the normal server caller's execution-context origin.
"""
import unittest
from random import Random
from dataclasses import replace
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_ordinary_authority import ordinary_cast_authority
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
import test_combat_displacement as fixtures


class CarryRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NativeDisplacementTests.setUpClass()

    def test_actual_factory_binding_carry_then_throw_and_missing_ps_rejection(self):
        f = fixtures.NativeDisplacementTests()
        f.setUp()
        preview = f.preview
        preview.native_effect_areas = {}
        for actor in preview.actors.values():
            actor.native_los_height = 0
        combined = dict(f.effects)
        combined.update(f.fixture.states["effects"])
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        combined.update(
            native_catalog.load(DATA_ROOT / "granted-spell-effect-trees.json")[
                "effects"
            ]
        )
        definitions = {}
        for family in (333, 334):
            candidates = [
                (int(ref), row)
                for ref, row in combined.items()
                if row["effect_class"] == family
                and not row.get("criteria")
                and row.get("variant") == 0
            ]
            self.assertTrue(candidates, f"Missing original family{family} fixture")
            definitions[family] = min(candidates)[0]
        # Explicit callback fixture is instant; native definition timing is
        # untouched. This is factory binding proof, not retained spell proof.
        adapter = NativeServerRuntimeAdapter(
            actor_authority=f.authority,
            cast=ordinary_cast_authority(
                actors=f.authority,
                timing=NativeEffectTimingProvider(f.fixture.states),
                rng=Random(1),
                critical=False,
            ),
        )
        contexts = replace(
            adapter.contexts(),
            stat=lambda p, plan, e, i: StatExecutionContext(
                True, True, None, False, b""
            ),
        )
        factory = NativeEffectRuntimeFactory(
            effects=combined,
            state_catalog=f.fixture.states,
            characteristic_registry=f.fixture.registry,
            action_id=1,
            contexts=contexts,
            displacement_authority=f.authority,
        )
        dispatcher, packets = factory(preview, dict(spell_id=6266, evaluation_level=1))
        raw = dispatcher.handlers[334].cancel_prepared.__self__
        self.assertIsNotNone(raw.area_events)
        self.assertIsNotNone(raw.event_lifecycle)
        # Execute through the actual factory handler, avoiding a definition's
        # retained-wrapper policy in this explicitly instant callback fixture.
        context_hex = "0800100020ffffffffffffffffff0128013000380040004800"
        carry = EffectInvocation(
            definitions[334],
            1,
            7,
            -7,
            preview.actors[-7].position,
            native_context_hex=context_hex,
        )
        self.assertTrue(raw(combined[str(carry.reference)], {}, carry))
        self.assertEqual(preview.actors[7].native_carried_actor_id, -7)
        throw = EffectInvocation(
            definitions[333], 1, 7, None, (2, 1, 0), native_context_hex=context_hex
        )
        self.assertTrue(raw(combined[str(throw.reference)], {}, throw))
        self.assertIsNone(preview.actors[7].native_carried_actor_id)
        self.assertEqual(preview.actors[-7].position, (2, 1, 0))
        self.assertEqual(
            [opcode for opcode, _ in packets if opcode == 12613], [12613, 12613]
        )
        before = len(packets)
        with self.assertRaisesRegex(ValueError, "execution-context origin"):
            raw(
                combined[str(carry.reference)],
                {},
                replace(carry, native_context_hex=None),
            )
        self.assertEqual(len(packets), before)

        # Actual Panda carry definition has native table29 release child
        # 290563 (eZE, qcl=true). The source actor is a registered ordinary
        # fighter; the explicit instant context above isolates machinery.
        self.assertEqual(combined["290562"]["effect_class"], 334)
        self.assertEqual(combined["290562"]["children"][0], 290563)
        self.assertTrue(
            raw(
                combined["290562"],
                {},
                EffectInvocation(
                    290562,
                    1,
                    -7,
                    8,
                    preview.actors[8].position,
                    native_context_hex=context_hex,
                ),
            )
        )
        carrier_before = preview.actors[-7].position
        carried_before = preview.actors[8].position
        self.assertEqual(carrier_before, carried_before)
        movement = dispatcher.handlers[300]
        self.assertTrue(
            movement(
                combined["358000"],
                None,
                EffectInvocation(358000, 1, 7, -7, carrier_before),
            )
        )
        self.assertIsNone(preview.actors[-7].native_carried_actor_id)
        self.assertIsNone(preview.actors[8].native_carrier_id)
        self.assertNotEqual(preview.actors[-7].position, carrier_before)
        self.assertEqual(preview.actors[8].position, carried_before)
        from wakfu_server.combat_qi_fight import current_registry

        registry = current_registry(preview)
        self.assertTrue(registry.slots[preview.actors[8].native_obstacle_id]["indexed"])
