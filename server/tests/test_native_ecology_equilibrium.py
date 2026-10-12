"""Native chief display and player affinity share regional equilibrium bounds."""
import unittest
from unittest.mock import patch
from wakfu_server import ecology_equilibrium, ecology_policy, territory_bonuses


POLICY = dict(
    version=2,
    unit="basis_points",
    balance_delta=25,
    imbalance_delta=-25,
    plant=dict(minimum=10, maximum=100),
    monster=dict(minimum=1, maximum=128),
)
CATALOG = dict(
    territories={
        "76101": dict(
            map_id=527,
            monster_wishes=[dict(family_id=68, minimum=150, maximum=200)],
            plant_wishes=[dict(family_id=10, minimum=100, maximum=150)],
        )
    },
    states={
        "1916": dict(effects=[]),
        "1915": dict(effects=[]),
        "1917": dict(effects=[]),
    },
)


class PolicyDatabase:
    def execute(self, sql, args=()):
        if "personal_ecology_policy" not in sql:
            raise AssertionError("Equilibrium must not read obsolete SQL overrides")
        return self

    def fetchone(self):
        return dict(value=POLICY)


class NativeEcologyEquilibriumTests(unittest.TestCase):
    def setUp(self):
        self.catalog_patch = patch.object(
            ecology_equilibrium, "catalog", return_value=CATALOG
        )
        self.catalog_patch.start()
        self.addCleanup(self.catalog_patch.stop)

    def decision(self, *, before, action="plant", kind="monster", family_id=68):
        return ecology_policy.decision(
            PolicyDatabase(),
            map_id=527,
            region_id=76101,
            kind=kind,
            family_id=family_id,
            action=action,
            before=before,
        )

    def test_planting_below_native_chief_minimum_earns_wakfu_above_old_128(self):
        for population in (120, 128, 146, 149):
            outcome = self.decision(before=population)
            self.assertEqual(outcome["delta"], 25)
            self.assertEqual(
                (outcome["evidence"]["minimum"], outcome["evidence"]["maximum"]),
                (150, 200),
            )
            self.assertEqual(outcome["evidence"]["limit_source"], "native_chief_wish")

    def test_native_equilibrium_neutral_inside_and_stasis_above(self):
        self.assertEqual(self.decision(before=150)["delta"], 0)
        self.assertEqual(self.decision(before=200)["delta"], -25)
        self.assertEqual(self.decision(before=150, action="remove")["delta"], -25)
        self.assertEqual(self.decision(before=201, action="remove")["delta"], 25)

    def test_monster_without_native_wish_has_zero_to_ten_tolerance(self):
        self.assertEqual(self.decision(before=9, family_id=999)["delta"], 0)
        outcome = self.decision(before=10, family_id=999)
        self.assertEqual(outcome["delta"], -25)
        self.assertEqual(
            (outcome["evidence"]["minimum"], outcome["evidence"]["maximum"]), (0, 10)
        )

    def test_plants_without_native_wish_are_unmanaged_and_neutral(self):
        outcome = self.decision(before=300, kind="plant", family_id=1)
        self.assertEqual(outcome["delta"], 0)
        self.assertIsNone(outcome["evidence"]["minimum"])
        self.assertFalse(outcome["evidence"]["managed_equilibrium"])
        self.assertEqual(
            self.decision(before=48, kind="plant", family_id=10)["delta"], 25
        )

    def test_native_chief_satisfaction_uses_same_bounds_as_affinity(self):
        with patch.object(territory_bonuses, "_catalog", return_value=CATALOG):
            for monster_count, expected in ((120, 1), (150, 2), (200, 2), (201, 1)):
                status = territory_bonuses.evaluate_population(
                    76101, {68: monster_count}, {10: 125}
                )
                self.assertEqual(status["satisfied_wishes"], expected)
                limits = ecology_equilibrium.limits(527, 76101, "monster", 68)
                self.assertEqual(
                    limits["minimum"] <= monster_count <= limits["maximum"],
                    expected == 2,
                )

    def test_wrong_map_never_uses_another_chiefs_wishes(self):
        with self.assertRaisesRegex(ValueError, "different map"):
            ecology_equilibrium.limits(1134, 76101, "monster", 68)


if __name__ == "__main__":
    unittest.main()
