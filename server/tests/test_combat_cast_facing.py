import unittest
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from wakfu_server.combat_spell_transaction import prepare_spell_transaction
from wakfu_server.combat_cast_facing import (
    mirror_cast_facing,
    native_cast_facing,
    cast_direction,
)


class CastFacingTest(unittest.TestCase):
    def test_original_desplume_script_turns_caster_before_mode6(self):
        source = SimpleNamespace(id=7, position=(0, 0, 0), direction=0)
        preview = deepcopy(source)
        self.assertTrue(
            mirror_cast_facing(
                preview,
                {"spell_id": 7318, "target": (-1, 0, 0)},
                fight=SimpleNamespace(actors={7: preview}),
            )
        )
        self.assertEqual(preview.direction, 5)
        self.assertEqual(source.direction, 0)
        self.assertEqual(native_cast_facing()["7318"]["script_id"], 1002410)

    def test_same_xy_preserves_direction_and_unknown_preserves_cast(self):
        actor = SimpleNamespace(position=(0, 0, 0), direction=3)
        for spell, target in ((7318, (0, 0, 9)), (-1, (2, 0, 0))):
            self.assertFalse(
                mirror_cast_facing(actor, {"spell_id": spell, "target": target})
            )
            self.assertEqual(actor.direction, 3)

    def test_explicit_no_turn_preserves_direction(self):
        actor = SimpleNamespace(position=(0, 0, 0), direction=7)
        records = {
            "1": {
                "status": "verified",
                "turnCasterTowardTargetCell": False,
                "useDiags": True,
            }
        }
        self.assertFalse(
            mirror_cast_facing(
                actor, {"spell_id": 1, "target": (2, 0, 0)}, contracts=records
            )
        )
        self.assertEqual(actor.direction, 7)

    def test_original_cardinal_and_diagonal_vector_matrix(self):
        path = (
            Path(__file__).parents[2]
            / "docs/reports/combat-inventory/native-cast-facing-probe.tsv"
        )
        for line in path.read_text().splitlines():
            dx, dy, cardinal, diagonal = map(int, line.split())
            for enabled, expected in ((False, cardinal), (True, diagonal)):
                expected = None if dx == dy == 0 else expected
                self.assertEqual(cast_direction(dx, dy, diagonals=enabled), expected)

    def test_signed_int_delta_overflow_before_float_conversion(self):
        actor = SimpleNamespace(id=7, position=(-2147483648, 0, 0), direction=7)
        records = {
            "1": {
                "status": "verified",
                "turnCasterTowardTargetCell": True,
                "useDiags": True,
            }
        }
        mirror_cast_facing(
            actor,
            {"spell_id": 1, "target": (2147483647, 1, 0)},
            contracts=records,
            fight=SimpleNamespace(actors={7: actor}),
        )
        self.assertEqual(actor.direction, 4)  # int delta(-1,+1), not (+4294967295,+1).

    def test_failed_dispatch_factory_does_not_commit_mirrored_direction_or_costs(self):
        caster = SimpleNamespace(
            id=7, position=(0, 0, 0), direction=3, ap=6, mp=3, effect_stats=None
        )
        fight = SimpleNamespace(actors={7: caster}, events=[])
        plan = {
            "actor_id": 7,
            "spell_id": 7318,
            "target": (-2, 0, 0),
            "costs": {"ap": 2, "mp": 0, "wp": 0},
        }

        def failing(preview, request):
            self.assertEqual(preview.actors[7].direction, 5)
            self.assertEqual(preview.actors[7].ap, 4)
            raise ValueError("later dispatcher failure")

        with patch(
            "wakfu_server.combat_spell_transaction.source_snapshot", return_value={}
        ), patch(
            "wakfu_server.combat_spell_transaction.prepare_spell_cast",
            return_value=plan,
        ):
            with self.assertRaisesRegex(ValueError, "later dispatcher failure"):
                prepare_spell_transaction(
                    b"",
                    {},
                    fight,
                    3,
                    b"",
                    wp_current=6,
                    action_id=1,
                    line_of_sight=lambda *a: True,
                    runtime_factory=failing,
                )
        self.assertEqual((caster.direction, caster.ap, caster.mp), (3, 6, 3))
