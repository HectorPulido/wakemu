"""Explicit minigame policy preserves data and rejects ordinary activation."""
import json
from pathlib import Path
import tempfile
import unittest

from wakfu_server.maps.monster_minigame_policy import (
    MINIGAME_BLOCKED_REFERENCES,
    exclusion_reason,
    ordinary_group_members,
    require_ordinary_spawn,
    requires_npc_summon_validation,
)
from monster_activation_exceptions import ENCOUNTER_EXCEPTIONS, exclusion_status
from prepare_monster_spell_activation import select_candidates
from finalize_monster_spell_activation import finalize


class MonsterMinigamePolicyTests(unittest.TestCase):
    def test_exact_source_proven_scope_and_existing_policy_preserved(self):
        self.assertEqual(
            MINIGAME_BLOCKED_REFERENCES,
            {2782, 2784, 3217, 3893, 3896, 3897, 3942, 3943, 3944},
        )
        self.assertEqual(len(ENCOUNTER_EXCEPTIONS), 7)
        for ref in MINIGAME_BLOCKED_REFERENCES:
            self.assertEqual(exclusion_reason(ref), "minigame_requires_encounter")
            self.assertEqual(exclusion_status(ref), "blocked_minigame")

    def test_higher_level_bworkball_requires_native_encounter(self):
        for ref in (2782, 2784):
            self.assertEqual(exclusion_reason(ref), "minigame_requires_encounter")
            self.assertEqual(exclusion_status(ref), "blocked_minigame")
            with self.assertRaisesRegex(ValueError, "native minigame"):
                require_ordinary_spawn(ref)

    def test_unproven_stealth_and_ordinary_variants_not_blocked(self):
        for ref in (3949, 3939, 3945, 6):
            self.assertIsNone(exclusion_reason(ref))
            require_ordinary_spawn(ref)

    def test_ordinary_spawn_rejected_without_changing_native_constructor(self):
        for ref in MINIGAME_BLOCKED_REFERENCES:
            with self.assertRaisesRegex(ValueError, "native minigame encounter"):
                require_ordinary_spawn(ref)

    def test_tentacles_are_summon_only_not_ordinary_wild_or_admin_spawns(self):
        for ref in (5403, 5404):
            self.assertEqual(exclusion_reason(ref), "npc_summon_only")
            self.assertIsNone(exclusion_reason(ref, context="native_summon"))
            self.assertTrue(requires_npc_summon_validation(ref))
            with self.assertRaisesRegex(ValueError, "native summon creator"):
                require_ordinary_spawn(ref)

    def test_public_group_projection_removes_only_summon_only_members(self):
        members = [
            {"id": -1, "ref": 5373},
            {"id": -2, "ref": 5403},
            {"id": -3, "ref": 5404},
            {"id": -4, "ref": 5373},
            {"id": -5, "ref": 5374},
        ]
        self.assertEqual(
            ordinary_group_members(members, instance_id=0),
            (members[0], members[3], members[4]),
        )
        self.assertEqual(
            ordinary_group_members(members, instance_id=17), tuple(members)
        )

    def test_automatic_selection_excludes_blocked_but_retains_inventory(self):
        rows = [
            dict(
                ref=r,
                status="covered",
                spell_ids=[1],
                data_gaps=[],
                missing_families=[],
                min_level=1,
                max_level=1,
            )
            for r in [*MINIGAME_BLOCKED_REFERENCES, 3949]
        ]
        self.assertEqual(
            [r["ref"] for r in select_candidates({"monsters": rows}, 30000)], [3949]
        )
        self.assertEqual(len(rows), 10)

    def test_old_candidate_cannot_bypass_finalizer_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manifest.json").write_text(
                json.dumps({"selected_references": [3217]})
            )
            with self.assertRaisesRegex(ValueError, "explicitly blocked references"):
                finalize(root, root / "absent-validation.json", root / "output")
            self.assertFalse((root / "output").exists())


if __name__ == "__main__":
    unittest.main()
