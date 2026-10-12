"""Portable source and proof regressions; no native engine or injected areas."""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from types import SimpleNamespace
from external_owned_area_preparation import (
    recipes,
    necessary_area_references,
    new_area_proof,
    verify_surviving_area,
    producer_scene_cells,
    actual_external_targets,
)
from target_area_scene import target_area_scene


class CriterionDiscoveryTests(unittest.TestCase):
    def rows(self, criterion, reference=99999, spell=77777):
        return recipes(
            reference,
            spell,
            minimum=2,
            maximum=8,
            casting_record={"cast_criterion_raw": criterion},
        )

    def test_any_owned_consumer_identity_uses_native_criterion(self):
        rows = self.rows(
            'IsOnSpecificEffectArea("caster",393) or IsOnSpecificEffectArea("caster",394)'
        )
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r["area_mode"] == "caster_area" for r in rows))
        self.assertTrue(all(r["qualification_spell"] == 77777 for r in rows))

    def test_target_criterion_discovers_without_specific_spell_id(self):
        rows = self.rows(
            "(IsSpecificArea(393) or IsSpecificArea(394) or IsSpecificArea(401)) and not CellContainsEffectAreaType(5)"
        )
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(r["area_mode"] == "target_area" for r in rows))

    def test_unknown_producer_and_negated_or_optional_requirement_fail_closed(self):
        for criterion in [
            "IsSpecificArea(401)",
            "IsSpecificArea(471)",
            "not IsSpecificArea(393)",
            "IsSpecificArea(393) or IsEnnemy()",
            "IsSpecificArea(393) and IsSpecificArea(401)",
            "Malformed(",
            'IsSpecificArea(393) and IsOnSpecificEffectArea("caster",393)',
        ]:
            with self.subTest(criterion=criterion):
                self.assertEqual(self.rows(criterion), [])

    def test_actual_capability_range_required(self):
        self.assertEqual(
            recipes(1, 2, casting_record={"cast_criterion_raw": "IsSpecificArea(393)"}),
            [],
        )


class NativeAreaProofTests(unittest.TestCase):
    def setUp(self):
        self.cell = (2, 0, 0)
        self.area = dict(
            uid=29,
            reference=393,
            owner_id=-201,
            cell=self.cell,
            effect_uid=30,
            effect_class=315,
            effect_reference=71539,
            target_id=None,
            native_area_contract="faY",
        )
        self.runner = dict(
            uid=30,
            area_uid=29,
            effect_class=315,
            caster_id=-201,
            target_id=None,
            executed=True,
            timer=dict(actor_id=-201, expiration_round=2, phase="end"),
        )
        self.fight = SimpleNamespace(
            actors={
                -200: SimpleNamespace(hp=100, position=(0, 0, 0)),
                7: SimpleNamespace(position=(0, 1, 0)),
            },
            native_effect_areas={29: self.area},
            native_owned_area_effects={30: self.runner},
            validation_external_target_area_cell=self.cell,
        )
        self.contains = lambda row, cell: tuple(row["cell"]) == tuple(cell)

    def proof(self):
        return new_area_proof(
            self.fight, set(), -201, -200, self.contains, target_cell=self.cell
        )

    def survive(self, proof):
        return verify_surviving_area(
            self.fight, proof, -200, self.contains, target_cell=self.cell
        )

    def test_exact_native_cell_target_null_and_actual_request(self):
        proof = self.proof()
        self.survive(proof)
        self.assertEqual(actual_external_targets(self.fight), [(self.cell, None)])

    def test_false_uid_owner_runner_or_executed_state_rejected(self):
        for mapping, key, value in [
            (self.area, "effect_uid", 31),
            (self.area, "owner_id", 9),
            (self.runner, "area_uid", 28),
            (self.runner, "executed", False),
            (self.runner, "target_id", -202),
        ]:
            with self.subTest(key=key):
                before = mapping[key]
                mapping[key] = value
                with self.assertRaises(ValueError):
                    self.proof()
                mapping[key] = before

    def test_old_area_and_wrong_footprint_rejected(self):
        with self.assertRaises(ValueError):
            new_area_proof(
                self.fight, {29}, -201, -200, self.contains, target_cell=self.cell
            )
        self.area["cell"] = (0, 0, 0)
        with self.assertRaises(ValueError):
            self.proof()

    def test_expiration_or_retired_runner_rejected(self):
        proof = self.proof()
        self.fight.native_owned_area_effects.clear()
        with self.assertRaises(ValueError):
            self.survive(proof)
        self.fight.native_owned_area_effects[30] = self.runner
        self.fight.native_effect_areas.clear()
        with self.assertRaises(ValueError):
            self.survive(proof)

    def test_native_max_duration_never_extended_or_rewritten(self):
        proof = self.proof()
        before = dict(self.runner["timer"])
        self.survive(proof)
        self.assertEqual(self.runner["timer"], before)
        self.runner["timer"]["expiration_round"] += 1
        with self.assertRaises(ValueError):
            self.survive(proof)

    def test_replacement_effect_identity_rejected_after_commit(self):
        proof = self.proof()
        self.area["effect_reference"] = 999
        with self.assertRaises(ValueError):
            self.survive(proof)


class NativeScenePlacementTests(unittest.TestCase):
    def test_producer_off_player_los_for_both_teams(self):
        for team in [0, 1]:
            self.assertEqual(
                producer_scene_cells(
                    (0, 0, 0),
                    (-2, 0, 0),
                    {(0, 0, 0), (-1, 0, 0), (-2, 0, 0), (0, 1, 0)},
                    team,
                ),
                ((0, 1, 0), (-2, 0, 0)),
            )

    def test_no_validated_off_ray_cell_fails_closed(self):
        with self.assertRaises(ValueError):
            producer_scene_cells(
                (0, 0, 0), (-2, 0, 0), {(0, 0, 0), (-1, 0, 0), (-2, 0, 0)}, 0
            )

    def test_target_area_empty_and_producer_beyond_target(self):
        row = target_area_scene(
            (0, 0, 0),
            (2, 0, 0),
            {(0, 0, 0), (2, 0, 0), (3, 0, 0), (0, 1, 0)},
            minimum=2,
            maximum=8,
        )
        self.assertEqual(row["producer_cell"], (3, 0, 0))
        self.assertEqual(row["player_cell"], (0, 1, 0))
        self.assertIsNone(row["native_cast_target_id"])

    def test_unvalidated_out_of_range_or_unavailable_player_rejected(self):
        for cells, target in [
            ({(0, 0, 0), (2, 0, 0), (3, 0, 0)}, (2, 0, 0)),
            ({(0, 0, 0), (1, 0, 0), (2, 0, 0), (0, 1, 0)}, (1, 0, 0)),
        ]:
            with self.assertRaises(ValueError):
                target_area_scene((0, 0, 0), target, cells, minimum=2, maximum=8)


if __name__ == "__main__":
    unittest.main()
