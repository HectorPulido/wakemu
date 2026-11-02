"""Explicit native Qe.bft survives actor effects and retained null replay."""
import unittest

from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_effects import direct_damage
from wakfu_server.combat_displacement import position_payload
from wakfu_server.combat_stat_effects import (
    owned_effect_payload,
    null_listener_clone_payload,
)


class RunningVisualPositionTests(unittest.TestCase):
    def null_payload(self, **extra):
        return owned_effect_payload(
            uid=10,
            base_uid=10,
            generic_effect=341742,
            caster_id=105,
            target_id=105,
            value=0,
            timing_payload=b"",
            execution_status=-1,
            **extra
        )

    def test_distinct_native_cells_and_legacy_absence_preserve_actor_fields(self):
        legacy = self.null_payload()
        original = _identity_fields(legacy)
        messages = {}
        _identity_fields(legacy, messages=messages)
        self.assertNotIn(5, messages)
        for cell in ((2, -25, -2), (4, -21, -2), (0, 0, 0)):
            with self.subTest(cell=cell):
                messages = {}
                self.assertEqual(
                    _identity_fields(self.null_payload(cell=cell), messages=messages),
                    original,
                )
                self.assertEqual(messages[5], position_payload(cell))

    def test_rebound_null_clone_updates_only_explicit_native_position(self):
        old = self.null_payload(cell=(2, -25, -2))
        args = dict(
            uid=11, base_uid=10, execution_status=-1, caster_id=105, target_id=105
        )
        legacy_messages, current_messages = {}, {}
        _identity_fields(
            null_listener_clone_payload(old, **args), messages=legacy_messages
        )
        fields = _identity_fields(
            null_listener_clone_payload(old, cell=(4, -21, -2), **args),
            messages=current_messages,
        )
        self.assertEqual(legacy_messages[5], position_payload((2, -25, -2)))
        self.assertEqual(current_messages[5], position_payload((4, -21, -2)))
        self.assertEqual((fields[6], fields[7], fields[4]), (105, 105, 0))

    def test_retained_damage_keeps_authoritative_position_without_rejecting_replay(
        self,
    ):
        args = dict(
            uid=10,
            base_uid=10,
            generic_effect=341743,
            element=4,
            caster_id=105,
            target_id=16,
            damage=50,
        )
        cell = (2, -25, -2)
        retained = owned_effect_payload(
            uid=10,
            base_uid=10,
            generic_effect=341743,
            caster_id=105,
            target_id=16,
            value=50,
            cell=cell,
        )
        messages = {}
        fields = _identity_fields(
            direct_damage(357, 1, cell=cell, retained_payload=retained, **args)[19:],
            messages=messages,
        )
        self.assertEqual(messages[5], position_payload(cell))
        self.assertEqual((fields[6], fields[7], fields[4]), (105, 16, 50))
        messages = {}
        _identity_fields(
            direct_damage(357, 1, cell=(4, -21, -2), retained_payload=retained, **args)[
                19:
            ],
            messages=messages,
        )
        self.assertEqual(messages[5], position_payload(cell))
