"""The audit must not mistake ordinary movement for a trap's gameplay effect."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from sram_trap_audit_outcomes import qualify_outcome


class SramTrapAuditOutcomeTests(unittest.TestCase):
    def test_ordinary_movement_cannot_certify_repulsion(self):
        with self.assertRaisesRegex(AssertionError, "movement endpoint"):
            qualify_outcome(
                5182,
                dict(
                    mover_origin=(0, 0, 0),
                    requested_endpoint=(1, 0, 0),
                    final_position=[1, 0, 0],
                ),
            )

    def test_repulsion_requires_change_beyond_requested_endpoint(self):
        details = dict(
            requested_endpoint=(1, 0, 0),
            final_position=(3, 0, 0),
            trap_uid=91,
            movement_trace=[],
        )
        with self.assertRaisesRegex(AssertionError, "trap-source displacement"):
            qualify_outcome(5182, details)
        details["movement_trace"] = [
            dict(
                event="combat_effect",
                effect_class=300,
                caster_id=91,
                status="completed",
            )
        ]
        self.assertTrue(qualify_outcome(5182, details)[0])

    def test_damage_requires_actual_hp_or_armor_loss(self):
        details = dict(
            mover_hp_before=100,
            mover_hp_after=100,
            mover_armor_before=20,
            mover_armor_after=20,
        )
        with self.assertRaisesRegex(AssertionError, "HP or armor"):
            qualify_outcome(5183, details)
        self.assertTrue(qualify_outcome(5183, dict(details, mover_hp_after=99))[0])
        self.assertTrue(qualify_outcome(5183, dict(details, mover_armor_after=19))[0])

    def test_single_teleport_area_is_not_gameplay_qualification(self):
        self.assertFalse(qualify_outcome(5184, {})[0])

    def test_unknown_spell_does_not_get_default_success(self):
        with self.assertRaises(ValueError):
            qualify_outcome(999, {})
