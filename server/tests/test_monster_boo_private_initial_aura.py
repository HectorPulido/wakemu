"""Actual state5759 child270570 uses the existing detached eYJ primitive."""
from dataclasses import replace
import json
from pathlib import Path
import unittest

import test_combat_private_target_aura as private_fixture
from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_private_target_aura import validate_private_target_aura


class BooPrivateInitialAuraTests(unittest.TestCase):
    def setUp(self):
        self.fixture = private_fixture.PrivateTargetAuraTests()
        self.fixture.setUp()
        self.native = json.loads(
            (
                Path(__file__).parent / "fixtures/monster_boo_initial_aura_native.json"
            ).read_text()
        )
        self.invocation = replace(
            self.fixture.invocation, reference=self.native["child_reference"]
        )

    def test_real_initial_child_keeps_ring_aura_private_without_running_qs_children(
        self,
    ):
        self.assertEqual(self.native["initial_state_triples"], [5759, 1, 1])
        definition = native_effect_areas()["1373"]
        self.assertEqual(definition["native_class"], "bcD")
        self.assertEqual(definition["effect_ids"], [270560, 270561])
        self.assertEqual(definition["native_shape_class"], "anH")
        with self.fixture.f.scope():
            self.assertTrue(
                self.fixture.handler(
                    self.native["effect"], {"parameters": [1373]}, self.invocation
                )
            )
        fight = self.fixture.f.f.fight
        self.assertEqual(fight.native_effect_areas, {})
        row = fight.native_owned_area_effects[901]
        private = validate_private_target_aura(fight, row)
        self.assertEqual(private["reference"], 1373)
        self.assertFalse(private["creation_callbacks_executed"])
        self.assertFalse(private["registered"])
        self.assertNotIn(self.fixture.f.actor.id, fight.actors)
        self.assertEqual(self.fixture.registered, [901])
        self.assertEqual(len(self.fixture.f.f.packets), 1)

    def test_real_initial_child_does_not_authorize_foreign_detached_anchor(self):
        with self.fixture.f.scope(), self.assertRaises(ValueError):
            self.fixture.handler(
                self.native["effect"],
                {"parameters": [1373]},
                replace(self.invocation, caster_id=-77),
            )
        self.assertEqual(self.fixture.f.f.fight.native_effect_areas, {})
        self.assertEqual(self.fixture.f.f.packets, [])
