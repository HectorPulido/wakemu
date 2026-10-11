"""Qq PV allocation avoids actor identities without changing effect IDs."""
from copy import deepcopy
import json
import unittest
from types import MethodType

import test_combat_fake_fighter_area as area_fixture
import test_combat_effect_resolver as resolver_fixture
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_area_targets import area_targets, area_target_context
from wakfu_server.combat_state_managers import registered_area_pv


class AreaPVIdentityAllocationTests(unittest.TestCase):
    def fight(self, ids=(7, -200)):
        actors = [
            Actor(identity, team, (team, 0, 0), 100, 6, 3, 20, 1)
            for team, identity in enumerate(ids)
        ]
        return Fight(
            1,
            actors,
            {a.position for a in actors},
            {a.team: {a.position} for a in actors},
        )

    def test_ordinary_running_effect_can_still_overlap_actor_identity(self):
        fight = self.fight()
        fight.native_effect_uid_next = 7
        self.assertEqual(fight.allocate_effect_uid(), 7)
        fight.native_effect_uid_next = 7
        self.assertEqual(fight.allocate_area_uid(), 8)
        self.assertEqual(fight.native_effect_uid_next, 9)

    def test_active_retired_and_dead_actor_pvs_are_reserved(self):
        fight = self.fight((7, -200))
        fight.actors[7].hp = 0
        fight.native_effect_areas[8] = {"uid": 8}
        fight.native_retired_area_managers[9] = {"uid": 9}
        fight.native_owned_area_effects[30] = {"area_uid": 10}
        fight.native_effect_uid_next = 7
        self.assertEqual(fight.allocate_area_uid(), 11)
        self.assertIn(-200, fight.actors)
        self.assertEqual(fight.native_effect_uid_next, 12)

    def test_owned_effect_collision_keeps_counter_and_rollback_authority(self):
        fight = self.fight()
        fight.native_effect_uid_next = 7
        fight.owned_stat_effects[8] = {}
        with self.assertRaisesRegex(ValueError, "collides"):
            fight.allocate_area_uid()
        self.assertEqual(fight.native_effect_uid_next, 7)
        fight.owned_stat_effects.clear()
        preview = deepcopy(fight)
        self.assertEqual(preview.allocate_area_uid(), 8)
        self.assertEqual(fight.native_effect_uid_next, 7)
        restored = json.loads(
            json.dumps({"native_effect_uid_next": preview.native_effect_uid_next})
        )
        fight.native_effect_uid_next = restored["native_effect_uid_next"]
        self.assertEqual(fight.allocate_area_uid(), 9)

    def test_exhausted_skip_does_not_consume_counter(self):
        fight = self.fight()
        final = (1 << 63) - 2
        fight.actors[final] = fight.actors[7]
        fight.native_effect_uid_next = final
        with self.assertRaisesRegex(ValueError, "exhausted"):
            fight.allocate_area_uid()
        self.assertEqual(fight.native_effect_uid_next, final)

    def test_real_area_creation_and_resolver_have_unique_player7_pvs(self):
        fight, handler, _, _ = area_fixture.NativeFakeFighterAreaTests().create()
        fight.actors[7].state_ledger = StateLedger(7)
        fight.actors[7].physical_radius = 0
        for name in (
            "owned_stat_effects",
            "state_wire_payloads",
            "native_owned_group_effects",
            "native_owned_area_effects",
            "native_retired_area_managers",
        ):
            setattr(fight, name, {})
        fight.native_effect_uid_next = 7
        fight.allocate_effect_uid = MethodType(Fight.allocate_effect_uid, fight)
        fight.allocate_area_uid = MethodType(Fight.allocate_area_uid, fight)
        handler.allocate_uid = fight.allocate_effect_uid
        handler.allocate_area_uid = fight.allocate_area_uid
        self.assertTrue(
            handler(
                {"effect_class": 339},
                {"parameters": [1035]},
                EffectInvocation(400, 1, 7, None, (2, 3, 0)),
            )
        )
        self.assertIsNotNone(registered_area_pv(fight, 8))
        actors = tuple(fight.actors.values()) + area_targets(fight)
        self.assertEqual([actor.id for actor in actors], [7, 8])
        fixture = resolver_fixture.NativeResolverTests()
        fixture.setUp()
        fixture.resolver.actors = lambda effect, invocation: actors
        native = dict(fixture.native[1])
        fixture.resolver.native_context = lambda effect, invocation: {
            7: native,
            8: area_target_context(actors[1]),
        }
        fixture.resolver(fixture.effect, EffectInvocation(50, 20, 7, None, (0, 0, 0)))
        self.assertEqual(fight.native_effect_uid_next, 10)
