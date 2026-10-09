import struct
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from class_spell_eligible_targets import candidate_cells, eligible_cast_targets
from wakfu_server.combat_conditions import UnknownCondition


class EligibleTargetSelectionTests(unittest.TestCase):
    def fixture(self):
        caster = SimpleNamespace(
            id=7, team=0, position=(0, 0, 0), owner_id=3, effect_stats={4: 6}
        )
        enemy = SimpleNamespace(id=-7, team=1, position=(1, 0, 0), owner_id=None)
        fight = SimpleNamespace(
            actors={7: caster, -7: enemy}, walkable={(x, 0, 0) for x in range(9)}
        )
        adapter = SimpleNamespace(
            cast_condition=lambda preview, request: request["target"]
        )
        return fight, adapter

    def select(self, fight, adapter, validate, **kwargs):
        return eligible_cast_targets(
            fight,
            dict(id=7),
            b"owned-deck",
            4820,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            validate=validate,
            **kwargs
        )

    def test_finds_eligible_actual_cell_beyond_old_first_three_targets(self):
        fight, adapter = self.fixture()
        seen = []

        def validate(body, character, preview, owner, deck, **kwargs):
            identity, uid, x, y, z = struct.unpack(">qqiih", body)
            self.assertEqual(
                (identity, uid, owner, deck, kwargs["wp"]),
                (7, 4820, 3, b"owned-deck", 6),
            )
            seen.append((x, y, z))
            self.assertEqual(
                kwargs["conditional_context"](dict(target=(x, y, z)), preview),
                (x, y, z),
            )
            if x != 6:
                error = ValueError("Native spell casting eligibility rejected: twI")
                error.native_casting_result = "twI"
                error.native_casting_diagnostic = dict(
                    result="twI", target_cell=[x, y, z]
                )
                raise error
            return dict(
                actor_id=identity, spell_id=uid, evaluation_level=1, target=(x, y, z)
            )

        result = self.select(fight, adapter, validate, maximum_eligible=1)
        self.assertEqual(result["status"], "eligible_targets_found")
        self.assertEqual(result["eligible"][0]["target"], (6, 0, 0))
        self.assertEqual(result["checked_count"], len(seen))
        self.assertGreater(len(result["rejected"]), 3)
        self.assertTrue(
            all(
                row["native_casting_diagnostic"]["result"] == "twI"
                for row in result["rejected"]
            )
        )

    def test_truncated_search_is_not_no_eligible_context_proof(self):
        fight, adapter = self.fixture()

        def reject(*args, **kwargs):
            error = ValueError("Native spell casting eligibility rejected: twV")
            error.native_casting_result = "twV"
            raise error

        result = self.select(fight, adapter, reject, limit=3)
        self.assertEqual(result["status"], "bounded_search_exhausted")
        self.assertTrue(result["candidate_truncated"])
        self.assertFalse(result["search_complete"])
        self.assertEqual(result["checked_count"], 3)
        complete = self.select(fight, adapter, reject)
        self.assertEqual(complete["status"], "no_eligible_context")
        self.assertTrue(complete["search_complete"])

    def test_unknown_authority_stays_separate_from_context_rejection(self):
        fight, adapter = self.fixture()

        def unknown(*args, **kwargs):
            raise UnknownCondition("Missing actual fight model producer")

        result = self.select(fight, adapter, unknown)
        self.assertEqual(result["status"], "eligibility_authority_unresolved")
        self.assertTrue(all(row["authority_unresolved"] for row in result["rejected"]))

    def test_native_alignment_and_ap_property_rejections_are_known_negatives(self):
        fight, adapter = self.fixture()
        for native_result in ("twU", "twJ"):
            with self.subTest(native_result=native_result):

                def reject(*args, **kwargs):
                    error = ValueError("Known native validation rejection")
                    error.native_casting_result = native_result
                    raise error

                result = self.select(fight, adapter, reject, limit=3)
                self.assertEqual(result["status"], "bounded_search_exhausted")
                self.assertFalse(
                    any(row["authority_unresolved"] for row in result["rejected"])
                )

    def test_unexplained_value_error_is_unknown_even_with_rejection_like_message(self):
        fight, adapter = self.fixture()

        def unknown(*args, **kwargs):
            raise ValueError("Native spell casting eligibility rejected: twV")

        result = self.select(fight, adapter, unknown)
        self.assertEqual(result["status"], "eligibility_authority_unresolved")
        self.assertTrue(
            all(row["native_casting_result"] is None for row in result["rejected"])
        )

    def test_validation_uses_one_private_snapshot_and_preserves_resources(self):
        fight, adapter = self.fixture()
        snapshots = []

        def validate(body, character, preview, owner, deck, **kwargs):
            snapshots.append(preview)
            self.assertIsNot(preview, fight)
            return dict(target=struct.unpack(">qqiih", body)[2:])

        result = self.select(fight, adapter, validate)
        self.assertEqual(len(result["eligible"]), 3)
        self.assertTrue(all(value is snapshots[0] for value in snapshots))
        self.assertEqual(fight.actors[7].effect_stats, {4: 6})

    def test_candidates_use_actual_actor_and_walkable_cells_with_no_duplicates(self):
        fight, adapter = self.fixture()
        cells, count = candidate_cells(fight, 7)
        self.assertEqual(cells[:2], ((1, 0, 0), (0, 0, 0)))
        self.assertEqual(set(cells), fight.walkable)
        self.assertEqual(len(cells), count)
