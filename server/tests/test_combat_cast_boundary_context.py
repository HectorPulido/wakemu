import unittest
from types import SimpleNamespace

from wakfu_server.combat_cast_events import (
    cast_boundary_context,
    validate_cast_boundary_context,
)
from wakfu_server.combat.combat_event_replay import NativeExternalEvent


class CastBoundaryContextTests(unittest.TestCase):
    def test_validated_target_distance_one_two_three_is_not_listener_self(self):
        caster = SimpleNamespace(id=7, position=(0, 0, 0), physical_radius=0)
        target = SimpleNamespace(id=-7, position=(1, 0, 0), physical_radius=0)
        fight = SimpleNamespace(actors={7: caster, -7: target})
        for distance in (1, 2, 3):
            target.position = (distance, 0, 0)
            context = cast_boundary_context(
                fight,
                dict(
                    actor_id=7,
                    spell_id=4783,
                    target_id=-7,
                    target=target.position,
                ),
            )
            self.assertEqual(context["distance"], distance)
            event = NativeExternalEvent(7, (1024,), 61, cast_boundary_context=context)
            event.validate()
            self.assertIsNone(event.caster_id)
            self.assertIsNone(event.uid)
            self.assertIsNone(event.target_id)
            # Snapshot remains the validated selection after Charge moves.
            caster.position = target.position
            self.assertEqual(context["distance"], distance)
            caster.position = (0, 0, 0)

    def test_empty_cell_and_legacy_context_are_distinct(self):
        fight = SimpleNamespace(
            actors={7: SimpleNamespace(id=7, position=(0, 0, 0), physical_radius=0)}
        )
        self.assertEqual(
            cast_boundary_context(
                fight,
                dict(
                    actor_id=7,
                    spell_id=123,
                    target_id=None,
                    target=(2, 0, 0),
                ),
            )["distance"],
            2,
        )
        self.assertIsNone(cast_boundary_context(fight, dict(actor_id=7, spell_id=123)))

    def test_unknown_policy_and_non_cast_event_reject(self):
        with self.assertRaises(ValueError):
            validate_cast_boundary_context(
                dict(policy="guess", caster_id=7, spell_id=123, distance=1)
            )
        from wakfu_server.combat_cast_events import POLICY

        context = dict(policy=POLICY, caster_id=7, spell_id=123, distance=1)
        with self.assertRaises(ValueError):
            NativeExternalEvent(7, (1013,), 6, cast_boundary_context=context).validate()
