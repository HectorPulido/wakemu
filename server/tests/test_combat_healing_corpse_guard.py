"""Proven native corpse rejection is nonexecution; missing authority is error."""
import unittest
from unittest.mock import patch
import test_combat_healing_handler as fixtures

from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_state import Actor, Fight


class HealingCorpseGuardTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.HealingHandlerTests()
        fixture.setUp()
        self.handler = fixture.handler
        source, target = fixture.fight.actors[7], fixture.fight.actors[-7]
        # Keep a real second opponent alive: killing the only enemy correctly
        # settles the fight and removes the active healing context.
        survivor = Actor(-8, 1, (2, 0, 0), 100, 6, 3, 1, 1, max_hp=100)
        cells = {source.position, target.position, survivor.position}
        self.fight = Fight(
            77,
            [source, target, survivor],
            cells,
            {0: {source.position}, 1: {target.position, survivor.position}},
        )
        self.fight.ready(3)
        self.handler.fight = self.fight
        self.effect = dict(fixture.effect, effect_class=258)
        self.invocation = fixture.invocation
        self.packets = fixture.packets
        initialize_global_pv_collections(self.fight, tuple(self.fight.actors))

    def kill(self):
        with self.fight.effect_resolution():
            self.fight.apply_effect_damage(7, -7, 90)

    def test_proven_corpse_false_skips_healing_descriptors_and_application(self):
        self.kill()
        target = self.fight.actors[-7]
        target.effect_stats = None
        with patch(
            "wakfu_server.combat_ordinary_death._policies",
            return_value={
                "258": {"bcd_constant": False},
            },
        ):
            self.assertFalse(self.handler(self.effect, {}, self.invocation))
        self.assertEqual(target.hp, 0)
        self.assertEqual(self.packets, [])

    def test_prepared_nonexecution_keeps_l1_and_clears_owned_caches(self):
        self.kill()
        channels = []

        class Events:
            def phase(self, effect, invocation, **kwargs):
                channels.append(kwargs["channel"])

        self.handler.event_lifecycle = Events()
        with patch(
            "wakfu_server.combat_ordinary_death._policies",
            return_value={
                "258": {"bcd_constant": False},
            },
        ):
            prepared = self.handler.prepare(self.effect, {}, self.invocation)
            self.assertFalse(self.handler(self.effect, {}, prepared))
        self.assertEqual(channels, [1])
        self.assertEqual(self.handler.prepared, {})
        self.assertEqual(self.handler.final_modifiers, {})
        self.assertEqual(self.handler.runner_modifiers, {})
        self.assertEqual(self.packets, [])

    def test_unknown_corpse_policy_still_raises(self):
        self.kill()
        with patch("wakfu_server.combat_ordinary_death._policies", return_value={}):
            with self.assertRaisesRegex(
                ValueError, "Missing native runner corpse policy"
            ):
                self.handler(self.effect, {}, self.invocation)
        self.assertEqual(self.packets, [])

    def test_unknown_hp0_status_is_not_a_noop(self):
        self.fight.actors[-7].hp = 0
        with patch(
            "wakfu_server.combat_runner_target_life.owned_fighter_guards",
            return_value={"baG": None, "baK": False},
        ):
            with self.assertRaisesRegex(
                ValueError, "Missing actual native HP0 runner target status"
            ):
                self.handler(self.effect, {}, self.invocation)
        self.assertEqual(self.packets, [])
