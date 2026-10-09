"""Synthetic activation of an original eYZ dependency through real factories.

The activation criterion is cleared to isolate execution/transaction machinery;
this does not certify the class spell's original activation conditions.
"""
import unittest
from copy import deepcopy
from dataclasses import replace
from random import Random
from unittest.mock import patch

import test_combat_displacement as fixtures
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.combat_native_spell_casting import merged_spell_effects
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_ordinary_authority import ordinary_cast_authority
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_spell_transaction import prepare_spell_transaction
from wakfu_server.combat_geometry_snapshot import source_snapshot


class TriggeredSpellRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NativeDisplacementTests.setUpClass()
        cls.effects = merged_spell_effects()

    def fixture(self):
        f = fixtures.NativeDisplacementTests()
        f.setUp()
        # This parent is an original retained-state child, not a class spell
        # root. Production factories merge the authoritative state catalog.
        original = f.fixture.states["effects"]["343655"]
        effect = deepcopy(original)
        effect["criteria"] = ""
        effects = dict(self.effects)
        states = dict(f.fixture.states)
        states["effects"] = dict(states["effects"])
        states["effects"]["343655"] = effect
        rng = Random(19)
        adapter = NativeServerRuntimeAdapter(
            actor_authority=f.authority,
            cast=ordinary_cast_authority(
                actors=f.authority,
                timing=NativeEffectTimingProvider(states),
                rng=rng,
                critical=False,
            ),
        )
        # The draw is an explicit deterministic test input to prove that a
        # rejected nested execution rewinds the factory's actual RNG owner.
        contexts = replace(
            adapter.contexts(),
            probability=lambda p, plan, chance, i: (rng.random(), True)[1],
        )
        factory = NativeEffectRuntimeFactory(
            effects=effects,
            state_catalog=states,
            characteristic_registry=f.fixture.registry,
            action_id=1,
            contexts=contexts,
            displacement_authority=f.authority,
            transaction_rng=rng,
        )
        plan = dict(
            actor_id=7,
            spell_id=6266,
            spell_uid=(7 << 32) | 6266,
            evaluation_level=1,
            target_id=-7,
            target=f.preview.actors[-7].position,
            effect_ids=(343655,),
            costs=dict(ap=1, mp=0, wp=0),
        )
        from wakfu_server.combat_spell_usage import validate_usage

        plan["native_usage"] = validate_usage(
            f.preview,
            f.preview.actors[7],
            6266,
            1,
            plan["target"],
            f.fixture.cast_context(dict(actor_id=7), f.preview),
        )
        return f.preview, factory, rng, plan

    def execute(self, fight, factory, plan):
        with patch(
            "wakfu_server.combat_spell_transaction.prepare_spell_cast",
            return_value=plan,
        ):
            return prepare_spell_transaction(
                b"",
                dict(id=7, breed=15, level=1),
                fight,
                3,
                b"",
                wp_current=6,
                action_id=1,
                line_of_sight=lambda *args: True,
                runtime_factory=factory,
            )

    def test_real_factory_executes_nested_native_ability_and_restores_active_context(
        self,
    ):
        fight, factory, rng, plan = self.fixture()
        seen = []
        original = NativeEffectRuntimeFactory.__call__

        def build(instance, preview, selected):
            if selected.get("native_triggered_spell_policy"):
                seen.append((selected["spell_id"], selected["evaluation_level"]))
            return original(instance, preview, selected)

        with patch.object(NativeEffectRuntimeFactory, "__call__", build):
            transaction = self.execute(fight, factory, plan)
        self.assertEqual(seen, [(7697, 1)])
        self.assertTrue(transaction.outcomes[0])
        self.assertIsNone(transaction.fight.native_active_spell_id)
        self.assertTrue(any(opcode == 12613 for opcode, body in transaction.packets))
        self.assertEqual(fight.actors[7].ap, 6)

    def test_nested_missing_effect_rolls_back_full_source_rng_and_private_outbox(self):
        fight, factory, rng, plan = self.fixture()
        before, rng_before = source_snapshot(fight), rng.getstate()
        parent_outboxes, nested_seen = [], []
        original = NativeEffectRuntimeFactory.__call__

        def build(instance, preview, selected):
            dispatcher, packets = original(instance, preview, selected)
            if selected.get("native_triggered_spell_policy"):
                nested_seen.append(selected["spell_id"])
                # Deliberately remove a real native root to exercise the
                # production mandatory-effect rejection after nested setup.
                self.assertTrue(selected["effect_ids"])
                dispatcher.effects = dict(dispatcher.effects)
                dispatcher.effects.pop(str(selected["effect_ids"][0]), None)
            else:
                parent_outboxes.append(packets)
            return dispatcher, packets

        with patch.object(NativeEffectRuntimeFactory, "__call__", build):
            with self.assertRaisesRegex(ValueError, "Missing native effect definition"):
                self.execute(fight, factory, plan)
        self.assertEqual(nested_seen, [7697])
        self.assertEqual(source_snapshot(fight), before)
        self.assertEqual(rng.getstate(), rng_before)
        self.assertTrue(parent_outboxes)
        self.assertEqual(parent_outboxes[0], [])
