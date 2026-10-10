"""Exact eXD.fOQ binding, constructor context and inherited PL inputs."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_carrying import NativeCarryPair
from wakfu_server.combat_carry_release import execute_carry_release
from wakfu_server.combat_effect_dispatch import EffectInvocation


class CarryReleaseTests(unittest.TestCase):
    def fixture(self, children):
        carrier = SimpleNamespace(
            id=7,
            position=(4, 0, 0),
            direction=3,
            native_carrier_id=None,
            native_carried_actor_id=8,
        )
        carried = SimpleNamespace(
            id=8,
            position=(4, 0, 0),
            direction=3,
            native_carrier_id=7,
            native_carried_actor_id=None,
        )
        fight = SimpleNamespace(
            actors={7: carrier, 8: carried},
            native_carry_pairs={7: NativeCarryPair(7, 8, (4, 0, 0), 3, 3, 1, 290562)},
        )
        effects = {
            "290562": dict(effect_class=334, children=children),
            "290563": dict(effect_class=333),
        }
        return fight, carrier, effects

    def test_first_native_group_child_gets_fresh_context_and_same_pl(self):
        fight, carrier, effects = self.fixture([290563, 999])
        calls = []
        parent = EffectInvocation(
            358000,
            20,
            -7,
            7,
            (5, 0, 0),
            state_uid=88,
            native_context_hex="00",
            native_explicit_target=True,
            native_retained_container={"present": False},
        )
        self.assertTrue(
            execute_carry_release(
                fight, effects, lambda i: calls.append(i) or True, parent, carrier
            )
        )
        self.assertEqual(len(calls), 1)
        child = calls[0]
        self.assertEqual(
            (child.reference, child.caster_id, child.target_id), (290563, 7, None)
        )
        self.assertEqual(child.cell, carrier.position)
        self.assertEqual(child.state_uid, parent.state_uid)
        self.assertEqual(child.level, parent.level)
        self.assertIs(child.native_retained_container, parent.native_retained_container)
        self.assertEqual(
            child.native_context_hex,
            "0801100020ffffffffffffffffff0128013000380040004800",
        )
        self.assertFalse(child.native_explicit_target)

    def test_verified_empty_group_does_not_release_or_execute(self):
        fight, carrier, effects = self.fixture([])
        self.assertFalse(
            execute_carry_release(
                fight,
                effects,
                lambda i: self.fail("Empty native group executed"),
                EffectInvocation(358000, 1, -7, 7, (4, 0, 0)),
                carrier,
            )
        )
        self.assertEqual(carrier.native_carried_actor_id, 8)
