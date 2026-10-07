import math
import unittest

from postgres_case import PostgresCase
from psycopg.errors import CheckViolation
from psycopg.types.json import Jsonb
from wakfu_server import ecology_policy
from wakfu_server.planting_context import MAPS


class EcologyPolicyTests(PostgresCase):
    def _decision(self, **overrides):
        arguments = {
            "map_id": 1134,
            "region_id": 79301,
            "kind": "plant",
            "family_id": 10,
            "action": "plant",
            "before": 0,
        }
        arguments.update(overrides)
        with self.store.connection() as db:
            return ecology_policy.decision(db, **arguments)

    def _policy(self, value):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='personal_ecology_policy'",
                (Jsonb(value),),
            )

    def test_all_159_native_plant_bounds_match_region_catalog(self):
        expected = {}
        for map_id, map_row in MAPS.items():
            for region in map_row["regions"]:
                for family in region["plant_families"]:
                    minimum = family["parameter_bKQ"]
                    maximum = family["parameter_bKR"]
                    if maximum > 0:
                        expected[(map_id, region["region_id"], family["family_id"])] = (
                            minimum,
                            maximum,
                        )
        self.assertEqual(159, len(expected))

        with self.store.connection() as db:
            rows = db.execute(
                "SELECT map_id,region_id,family_id,minimum,maximum,source "
                "FROM ecology_family_limits WHERE source='native' AND kind='plant'"
            ).fetchall()
            monsters = db.execute(
                "SELECT count(*) AS count FROM ecology_family_limits "
                "WHERE source='native' AND kind='monster'"
            ).fetchone()["count"]
        actual = {
            (row["map_id"], row["region_id"], row["family_id"]): (
                row["minimum"],
                row["maximum"],
            )
            for row in rows
        }
        self.assertEqual(expected, actual)
        self.assertEqual(159, len(rows))
        self.assertEqual(0, monsters)

    def test_zero_zero_native_family_uses_explicit_local_fallback(self):
        region = next(row for row in MAPS[1134]["regions"] if row["region_id"] == 79301)
        native_family = next(
            row for row in region["plant_families"] if row["family_id"] == 10
        )
        self.assertEqual(
            (0, 0), (native_family["parameter_bKQ"], native_family["parameter_bKR"])
        )
        result = self._decision()
        self.assertEqual(25, result["delta"])
        self.assertEqual(
            (10, 100, "local_fallback", None),
            (
                result["evidence"]["minimum"],
                result["evidence"]["maximum"],
                result["evidence"]["limit_source"],
                result["evidence"]["limit_revision"],
            ),
        )
        monster_fallback = self._decision(
            region_id=79001,
            kind="monster",
            family_id=225,
            before=128,
        )
        self.assertEqual(
            (1, 128, "local_fallback"),
            tuple(
                monster_fallback["evidence"][key]
                for key in ("minimum", "maximum", "limit_source")
            ),
        )

    def test_native_bounds_are_scoped_to_exact_region_and_family(self):
        # Family 10 has distinct native bounds in these two map-1134 regions.
        first = self._decision(
            region_id=79001,
            family_id=10,
            before=300,
        )
        second = self._decision(
            region_id=79201,
            family_id=10,
            before=201,
        )
        other_family = self._decision(
            region_id=79001,
            family_id=1,
            before=101,
        )
        self.assertEqual(
            (300, 300, "native"),
            tuple(
                first["evidence"][key] for key in ("minimum", "maximum", "limit_source")
            ),
        )
        self.assertEqual(
            (200, 200, "native"),
            tuple(
                second["evidence"][key]
                for key in ("minimum", "maximum", "limit_source")
            ),
        )
        self.assertEqual("local_fallback", other_family["evidence"]["limit_source"])

        with self.store.connection() as db:
            db.execute(
                "INSERT INTO ecology_family_limits(map_id,region_id,kind,family_id,minimum,maximum,source,revision) "
                "VALUES(1134,79201,'monster',68,4,9,'local',2)"
            )
        local_override = self._decision(
            region_id=79201,
            kind="monster",
            family_id=68,
            before=9,
        )
        unoverridden = self._decision(
            region_id=79101,
            kind="monster",
            family_id=68,
            before=9,
        )
        self.assertEqual(
            (4, 9, "local", 2),
            tuple(
                local_override["evidence"][key]
                for key in ("minimum", "maximum", "limit_source", "limit_revision")
            ),
        )
        self.assertEqual("local_fallback", unoverridden["evidence"]["limit_source"])

    def test_only_actions_that_move_toward_the_band_earn_balance(self):
        at_boundary = self._decision(before=100)
        beyond_boundary = self._decision(before=101)
        inside_band = self._decision(before=50)
        self.assertEqual(-25, at_boundary["delta"])
        self.assertEqual(
            (100, 101),
            (
                at_boundary["evidence"]["before_population"],
                at_boundary["evidence"]["after_population"],
            ),
        )
        self.assertEqual(-25, beyond_boundary["delta"])
        self.assertEqual(0, inside_band["delta"])

    def test_gradual_crossing_rewards_only_steps_toward_band_then_stops(self):
        below = self._decision(before=8, amount=1)
        approaches = self._decision(before=9, amount=1)
        enters = self._decision(before=10, amount=1)
        neutral = self._decision(before=11, amount=1)
        self.assertEqual(
            (25, 25, 0, 0),
            tuple(result["delta"] for result in (below, approaches, enters, neutral)),
        )

    def test_nonremoving_harvest_is_an_explicit_neutral_population_action(self):
        result = self._decision(action="harvest", before=23, amount=1)
        self.assertEqual(0, result["delta"])
        self.assertEqual("harvest", result["evidence"]["action"])
        self.assertEqual(23, result["evidence"]["after_population"])

    def test_removal_at_minimum_and_multiunit_boundary(self):
        one_removed_to_min = self._decision(
            region_id=79001,
            family_id=10,
            action="remove",
            before=301,
            amount=1,
        )
        unit_crosses_minimum = self._decision(
            region_id=79001,
            family_id=10,
            action="remove",
            before=300,
            amount=1,
        )
        multiple_removed_to_min = self._decision(
            region_id=79001,
            family_id=10,
            action="remove",
            before=302,
            amount=2,
        )
        multiple_cross_minimum = self._decision(
            region_id=79001,
            family_id=10,
            action="remove",
            before=301,
            amount=2,
        )
        self.assertEqual(25, one_removed_to_min["delta"])
        self.assertEqual(-25, unit_crosses_minimum["delta"])
        self.assertEqual(25, multiple_removed_to_min["delta"])
        self.assertEqual(0, multiple_cross_minimum["delta"])

    def test_invalid_policy_inputs_and_bounds_reject_before_any_effect(self):
        valid = {
            "version": 2,
            "unit": "basis_points",
            "balance_delta": 25,
            "imbalance_delta": -25,
            "plant": {"minimum": 0, "maximum": 100},
            "monster": {"minimum": 1, "maximum": 128},
        }
        invalid_policies = (
            {**valid, "balance_delta": True},
            {**valid, "imbalance_delta": 0},
            {**valid, "version": True},
            {**valid, "unexpected": 3},
            {key: value for key, value in valid.items() if key != "plant"},
            {**valid, "plant": {"minimum": True, "maximum": 100}},
            {**valid, "plant": {"minimum": 101, "maximum": 100}},
            {**valid, "monster": {"minimum": -1, "maximum": 128}},
        )
        for policy in invalid_policies:
            with self.subTest(policy=policy):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE settings SET value=%s WHERE name='personal_ecology_policy'",
                        (Jsonb(policy),),
                    )
                    with self.assertRaises(ValueError):
                        ecology_policy.decision(
                            db,
                            map_id=1134,
                            region_id=79301,
                            kind="plant",
                            family_id=10,
                            action="plant",
                            before=0,
                        )
        with self.assertRaises(ValueError):
            ecology_policy.bounds({"minimum": math.nan, "maximum": 100})
        self._policy(valid)
        for arguments in (
            {"before": True},
            {"before": math.nan},
            {"amount": True},
            {"amount": math.inf},
            {"action": "grow"},
            {"kind": "water"},
            {"family_id": 0},
            {"region_id": True},
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    self._decision(**arguments)

        account = self.store.register("policy-no-effects", "test-password")["id"]
        character = self.store.create_character(account, "Policy Effects")
        with self.store.connection() as db:
            state = db.execute(
                "SELECT ecology_value,ecology_revision FROM characters WHERE id=%s",
                (character["id"],),
            ).fetchone()
            receipts = db.execute(
                "SELECT count(*) AS count FROM personal_ecology_receipts WHERE character_id=%s",
                (character["id"],),
            ).fetchone()["count"]
        self.assertEqual(
            (0, 0, 0), (state["ecology_value"], state["ecology_revision"], receipts)
        )

    def test_invalid_family_bound_update_is_rejected_without_changing_row(self):
        with self.store.connection() as db:
            original = db.execute(
                "SELECT minimum,maximum,revision FROM ecology_family_limits "
                "WHERE map_id=1134 AND region_id=79001 AND kind='plant' AND family_id=10"
            ).fetchone()
        with self.assertRaises(CheckViolation):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE ecology_family_limits SET minimum=301,maximum=300,revision=revision+1 "
                    "WHERE map_id=1134 AND region_id=79001 AND kind='plant' AND family_id=10"
                )
        with self.store.connection() as db:
            current = db.execute(
                "SELECT minimum,maximum,revision FROM ecology_family_limits "
                "WHERE map_id=1134 AND region_id=79001 AND kind='plant' AND family_id=10"
            ).fetchone()
        self.assertEqual(dict(original), dict(current))


if __name__ == "__main__":
    unittest.main()
