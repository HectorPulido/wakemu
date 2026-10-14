"""Native faV.bcM is captured at j(PV), independent of later owner changes."""
import os
import unittest

from test_combat_area_timed_expiration import AreaTimedExpirationTests
from wakfu_server.combat_effect_area_queries import (
    actor_on_specific_area,
    team_area_count,
)
from wakfu_server.combat_effect_area_targets import (
    area_targets,
    retained_area_source_target,
)


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class CapturedAreaAffiliationConsistencyTests(unittest.TestCase):
    def fixture(self):
        fight = AreaTimedExpirationTests().fixture()
        row = next(iter(fight.native_effect_areas.values()))
        self.assertEqual(row["native_fight_affiliation_source"], "faV.j(PV).bcM")
        captured = row["native_fight_affiliation"]
        self.assertIs(type(captured), int)
        owner = fight.actors[row["owner_id"]]
        self.assertEqual(
            getattr(owner, "native_fight_affiliation", owner.team), captured
        )
        # Isolate the immutable faV.ebh contract from the owner's subsequent
        # mutable affiliation. No actor/QI position, ownership or team changes.
        owner.native_fight_affiliation = 1 if captured == 0 else 0
        return fight, row, captured

    def test_selected_area_targets_keep_captured_affiliation_after_owner_changes(self):
        fight, row, captured = self.fixture()
        selected = retained_area_source_target(fight, row["uid"])
        self.assertEqual(selected.team, captured)
        target = next(
            target for target in area_targets(fight) if target.id == row["uid"]
        )
        self.assertEqual(target.team, selected.team)
        self.assertEqual(target.owner_id, row["owner_id"])

    def test_team_membership_matches_captured_count_and_does_not_follow_owner(self):
        fight, row, captured = self.fixture()
        self.assertNotEqual(
            fight.actors[row["owner_id"]].native_fight_affiliation, captured
        )
        self.assertTrue(
            actor_on_specific_area(
                fight, actor_id=row["uid"], reference=row["reference"], ownership="team"
            )
        )
        # The area source is excluded from eLw's count; other captured members
        # must be counted using their own bcM rather than their live owners.
        expected = sum(
            candidate["uid"] != row["uid"]
            and candidate.get("native_type_id", 1) == row.get("native_type_id", 1)
            and candidate["native_fight_affiliation"] == captured
            for candidate in fight.native_effect_areas.values()
        )
        self.assertEqual(
            team_area_count(
                fight,
                source_id=row["uid"],
                center=row["cell"],
                area_type=row.get("native_type_id", 1),
                minimum=0,
                maximum=-1,
            ),
            expected,
        )

    def test_explicit_missing_capture_cannot_be_replaced_by_live_owner_affiliation(
        self,
    ):
        fight, row, _ = self.fixture()
        row["native_fight_affiliation"] = None
        with self.assertRaisesRegex(ValueError, "affiliation|bcM"):
            area_targets(fight)


if __name__ == "__main__":
    unittest.main()
