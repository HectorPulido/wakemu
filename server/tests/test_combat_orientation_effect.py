import copy
import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_orientation_effect import (
    orientation_transition,
    NativeOrientationHandler,
    remove_orientation,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_random_transaction import rollback_external_rng


class OrientationEffectTests(unittest.TestCase):
    def transition(self, mode, **kwargs):
        values = dict(
            caster_position=(0, 0, 0),
            caster_direction=1,
            target_position=(3, 2, 9),
            target_direction=7,
            cell=(4, 0, -8),
            draw_mode=lambda: 2,
        )
        values.update(kwargs)
        return orientation_transition(mode, **values)

    def test_all_modes_match_original_probe(self):
        expected = {
            0: 7,
            1: 5,
            2: 7,
            3: 1,
            4: 3,
            5: 7,
            6: 1,
            7: 5,
            8: 1,
            9: 5,
            10: 3,
            11: 3,
        }
        for mode, direction in expected.items():
            self.assertEqual(self.transition(mode), (mode == 8, direction))
        for direction in range(8):
            self.assertEqual(
                self.transition(7, caster_direction=direction)[1], (direction + 4) % 8
            )
            self.assertEqual(
                self.transition(11, target_direction=direction)[1], (direction + 4) % 8
            )
        self.assertEqual(self.transition(0, cell=(3, 2, 0))[1], -1)
        self.assertEqual(self.transition(12)[1], -1)

    def test_extra_parameter_is_ignored_like_original_eWF(self):
        fight, packets, handler, invocation, contexts = self.fixture()
        self.assertTrue(
            handler({"effect_class": 303}, {"parameters": (9, 0)}, invocation)
        )
        self.assertEqual(fight.actors[-7].direction, 5)
        self.assertEqual(packets[0][0], 12613)
        self.assertEqual(packets[0][1][12], 0)  # Original cvX evaluated eIK=false.
        fields = _identity_fields(packets[0][1][19:])
        self.assertEqual(
            (fields[1], fields[2], fields[4], fields[7]), (9, 9, 5, (1 << 64) - 7)
        )

    def fixture(self, *, retained=False, property51=False, draw=lambda *args: 2):
        caster = Actor(7, 0, (0, 0, 0), 50, 6, 3, 10, 1, 9, True)
        target = Actor(-7, 1, (3, 2, 0), 20, 3, 3, 1, 1)
        caster.direction = 7
        target.direction = 3
        fight = Fight(
            1,
            [caster, target],
            {caster.position, target.position},
            {0: {caster.position}, 1: {target.position}},
        )
        fight.ready(9)
        packets = []
        authority = SimpleNamespace(
            property_counts=lambda p, a: {51: 1 if property51 else 0}
        )
        contexts = []

        def context(effect, invocation):
            contexts.append(invocation.target_id)
            return StatExecutionContext(True, True, None, retained, None)

        handler = NativeOrientationHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 9,
            context=context,
            authority=authority,
            draw_mode=draw,
        )
        invocation = EffectInvocation(123, 1, 7, -7, (4, 0, 0))
        return fight, packets, handler, invocation, contexts

    def test_mode8_rotates_and_retains_on_caster_not_target(self):
        fight, packets, handler, invocation, contexts = self.fixture(retained=True)
        self.assertTrue(handler({"effect_class": 303}, {"parameters": [8]}, invocation))
        self.assertEqual(
            (fight.actors[7].direction, fight.actors[-7].direction), (1, 3)
        )
        self.assertEqual(contexts, [7])
        self.assertEqual(fight.owned_stat_effects[9]["target_id"], 7)
        fields = _identity_fields(packets[0][1][19:])
        self.assertEqual((fields[4], fields[7]), (1, 7))
        remove_orientation(handler, 9)
        self.assertEqual(fight.actors[7].direction, 1)
        self.assertEqual(packets[-1][0], 13560)
        self.assertEqual(fight.owned_stat_effects, {})

    def test_locked_or_unchanged_native_failure_does_not_change_or_emit(self):
        for mode, locked in [(4, False), (1, True)]:
            fight, packets, handler, invocation, _ = self.fixture(property51=locked)
            self.assertFalse(
                handler({"effect_class": 303}, {"parameters": [mode]}, invocation)
            )
            self.assertEqual(fight.actors[-7].direction, 3)
            self.assertEqual(packets, [])
            self.assertEqual(fight.owned_stat_effects, {})

    def test_random_draw_precedes_explicit_null_target(self):
        calls = []
        self.assertEqual(
            self.transition(
                5, target_position=None, draw_mode=lambda: (calls.append(1) or 4)
            ),
            (False, -1),
        )
        self.assertEqual(calls, [1])

    def test_late_codec_failure_rolls_back_shared_rng_and_original_direction(self):
        fight, packets, handler, invocation, _ = self.fixture()
        rng = random.Random(1)
        before = rng.getstate()

        @rollback_external_rng
        def attempt(*, rng):
            preview = copy.deepcopy(fight)
            handler.fight = preview
            handler.draw_mode = lambda *args: rng.randrange(4) + 1
            with patch(
                "wakfu_server.combat_orientation_effect.owned_effect_application",
                side_effect=ValueError("late codec"),
            ):
                handler({"effect_class": 303}, {"parameters": [5]}, invocation)

        with self.assertRaises(ValueError):
            attempt(rng=rng)
        self.assertEqual(rng.getstate(), before)
        self.assertEqual(fight.actors[-7].direction, 3)
        self.assertEqual(packets, [])

    def test_mode8_checks_rebound_caster_property_not_original_target(self):
        fight, packets, handler, invocation, _ = self.fixture()
        handler.authority.property_counts = lambda p, a: {51: 1 if a.id == -7 else 0}
        self.assertTrue(handler({"effect_class": 303}, {"parameters": [8]}, invocation))
        self.assertEqual(fight.actors[7].direction, 1)
        self.assertEqual(fight.actors[-7].direction, 3)
