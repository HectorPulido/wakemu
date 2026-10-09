import unittest
from test_combat_maximum_resource import MaximumResourceTests
from wakfu_server.combat_spell_grant import (
    NativeSpellGrantHandler,
    remove_spell_grant,
    granted_spells,
    native_spell_references,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation


class SpellGrantTests(unittest.TestCase):
    def setUp(self):
        fixture = MaximumResourceTests()
        fixture.setUp()
        self.fight = fixture.fight
        self.packets = []
        self.uid = 100

        def allocate():
            self.uid += 1
            return self.uid

        self.handler = NativeSpellGrantHandler(
            self.fight,
            self.packets,
            action_id=1,
            allocate_uid=allocate,
            context=lambda *a: StatExecutionContext(True, True, None, True, None),
        )
        self.inv = EffectInvocation(313107, 1, 7, 7, (0, 0, 0))

    def apply(self, reference=5345):
        return self.handler(
            dict(
                effect_class=649,
                parameters=[2.0, 0.0, 0.0, 0.0, float(reference), 0.0, -1.0, 0.0],
            ),
            [],
            self.inv,
        )

    def test_owned_grant_native_uid_and_removal(self):
        self.apply()
        record = granted_spells(self.fight, 7)[5345]
        self.assertEqual(
            record,
            dict(uid=5345, reference=5345, level=self.fight.actors[7].effective_level),
        )
        payload = bytes.fromhex(self.fight.owned_stat_effects[101]["payload"])
        self.assertIn(
            bytes.fromhex("50e12970ffffffffffffffffff01980102a00100"), payload
        )
        self.assertEqual(self.packets[0][1][12], 0)
        self.assertEqual(self.packets[0][1][19:], payload)
        remove_spell_grant(self.handler, 101)
        self.assertFalse(granted_spells(self.fight, 7))
        self.assertEqual([op for op, _ in self.packets], [12613, 13560])

    def test_no_reference_counter_invented_for_native_registry(self):
        self.apply()
        self.apply()
        self.assertEqual(len(granted_spells(self.fight, 7)), 1)
        remove_spell_grant(self.handler, 101)
        self.assertFalse(granted_spells(self.fight, 7))

    def test_unknown_reference_rejects_without_owned_mutation(self):
        with self.assertRaises(ValueError):
            self.apply(999999999)
        self.assertFalse(granted_spells(self.fight, 7))
        self.assertFalse(self.packets)

    def test_native_catalog_is_immutable_and_general(self):
        refs = native_spell_references()
        self.assertIsInstance(refs, frozenset)
        self.assertEqual(len(refs), 4143)
        self.assertIn(3909, refs)
