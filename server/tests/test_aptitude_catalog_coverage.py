"""Catalog-wide checks for native aptitude budgets and effect reduction."""

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from wakfu_server import aptitudes
from wakfu_server.wire import proto_field
from wakfu_server import native_catalog


def aptitude_sheet(allocations):
    return proto_field(24, (1 << 64) - 1) + b"".join(
        proto_field(34, proto_field(8, bonus) + proto_field(16, points))
        for bonus, points in allocations
    )


def character_for(allocations, level=250):
    return {
        "level": level,
        "builds": {0: {"aptitudes": aptitude_sheet(allocations).hex()}},
    }


class AptitudeCatalogCoverageTests(unittest.TestCase):
    def test_rules_effects_and_category_ownership_are_complete(self):
        native_audit = json.loads(
            native_catalog.read_text(
                Path(__file__).parents[1]
                / "protocol"
                / "native-aptitude-catalog-audit.json"
            )
        )
        catalog_ids = set(aptitudes.BONUSES)
        effect_ids = set(aptitudes.EFFECTS)
        category_ids = set(aptitudes.CATEGORIES)
        owned_ids = [
            bonus for row in aptitudes.CATEGORIES.values() for bonus in row["bonuses"]
        ]
        dormant_ids = set(native_audit["dormant_category_references"])
        native_ids = set(native_audit["native_bonus_ids"])

        self.assertEqual(effect_ids, catalog_ids)
        self.assertEqual(len(owned_ids), len(set(owned_ids)))
        self.assertEqual(catalog_ids, native_ids)
        self.assertEqual(set(owned_ids) - catalog_ids, dormant_ids)
        self.assertEqual(catalog_ids - set(owned_ids), set())
        self.assertEqual(native_audit["schema_version"], 1)
        self.assertEqual(native_audit["native_decoder"], "aJX (eED.oYG ABILITY=135)")
        self.assertEqual(
            native_audit["dormant_reference_policy"],
            "Preserve category data; native lookup returns null and does not instantiate an effect. Allocation of missing native bonus identities remains rejected.",
        )
        native_catalogs = native_audit["primary_catalogs"]
        self.assertEqual(len(native_catalogs), 2)
        self.assertEqual(
            native_catalogs[0]["member_sha256"], native_catalogs[1]["member_sha256"]
        )
        self.assertEqual(set(native_catalogs[0]["native_bonus_ids"]), native_ids)
        self.assertEqual(set(native_catalogs[1]["native_bonus_ids"]), native_ids)
        self.assertTrue(category_ids)

        for bonus, rule in aptitudes.BONUSES.items():
            effect = aptitudes.EFFECTS[bonus]
            self.assertEqual(rule["effect_references"], [effect["effect"]], bonus)
            category = aptitudes.BONUS_CATEGORY[bonus]
            point_budget = aptitudes.budgets(250)[category]
            legal_maximum = min(rule["maximum"] or point_budget, point_budget)
            self.assertGreater(legal_maximum, 0, bonus)
            self.assertGreaterEqual(
                len(effect["values_by_points"]), legal_maximum, bonus
            )
            for child in effect.get("children", []):
                self.assertGreaterEqual(
                    len(child.get("values_by_points", [])),
                    legal_maximum,
                    (bonus, child),
                )

    def test_category_budgets_match_every_native_level_and_enforce_boundary(self):
        for level in range(1, 251):
            available = aptitudes.budgets(level)
            self.assertEqual(set(available), set(aptitudes.CATEGORIES))
            allocations = []
            for category, budget in available.items():
                remaining = budget
                for bonus in aptitudes.CATEGORIES[category]["bonuses"]:
                    maximum = aptitudes.BONUSES[bonus]["maximum"] or remaining
                    points = min(maximum, remaining)
                    if points:
                        allocations.append((bonus, points))
                        remaining -= points
                    if not remaining:
                        break
                self.assertEqual(remaining, 0, (level, category, budget))

            parsed = aptitudes.validate({"level": level}, aptitude_sheet(allocations))
            self.assertEqual(parsed["available"], available)
            self.assertEqual(parsed["spent"], available)

            for category, budget in available.items():
                if not budget:
                    continue
                over_budget = list(allocations)
                bonus = next(
                    candidate
                    for candidate in aptitudes.CATEGORIES[category]["bonuses"]
                    if candidate in aptitudes.BONUSES
                    and (
                        aptitudes.BONUSES[candidate]["maximum"] == 0
                        or candidate not in {owned for owned, _ in allocations}
                        or any(
                            candidate == owned
                            and points < aptitudes.BONUSES[candidate]["maximum"]
                            for owned, points in allocations
                        )
                    )
                )
                for index, (owned, points) in enumerate(over_budget):
                    if owned == bonus:
                        over_budget[index] = (owned, points + 1)
                        break
                else:
                    over_budget.append((bonus, 1))
                with self.assertRaises(ValueError, msg=(level, category)):
                    aptitudes.validate({"level": level}, aptitude_sheet(over_budget))

    def test_every_legal_bonus_point_value_is_reduced_or_reported_unsupported(self):
        """Never silently drop an allocated, legal native bonus point."""
        level_budgets = aptitudes.budgets(250)
        for bonus, rule in aptitudes.BONUSES.items():
            category = aptitudes.BONUS_CATEGORY[bonus]
            legal_maximum = min(
                rule["maximum"] or level_budgets[category], level_budgets[category]
            )
            for points in range(1, legal_maximum + 1):
                result = aptitudes.bonuses(character_for([(bonus, points)]))
                with self.subTest(bonus=bonus, points=points):
                    self.assertEqual(
                        result["unsupported"],
                        [],
                        f"native aptitude {bonus} ({aptitudes.EFFECTS[bonus]['effect']}) "
                        f"is not reduced at {points} point(s)",
                    )
                    self.assertTrue(
                        result["stats"]
                        or result["percentages"]
                        or result.get("native_effects"),
                        f"native aptitude {bonus} at {points} points has no applied value",
                    )

    def test_all_group_reducers_fail_closed_without_partial_child_results(self):
        for bonus, effect in aptitudes.EFFECTS.items():
            if bonus in (17, 27, 36):
                continue  # These roots are checked by native runtime initialization tests.
            if effect.get("runner") != "eYg":
                continue
            mutated = copy.deepcopy(aptitudes.EFFECTS)
            children = mutated[bonus].get("children", [])
            self.assertTrue(children, bonus)
            children[0]["runner"] = "unsupported-native-runner"
            with patch.object(aptitudes, "EFFECTS", mutated):
                result = aptitudes.bonuses(character_for([(bonus, 1)]))
            with self.subTest(bonus=bonus):
                self.assertEqual(result["stats"], {})
                self.assertEqual(result["percentages"], {})
                self.assertEqual(
                    result["unsupported"],
                    [{"bonus": bonus, "effect": effect["effect"], "runner": "eYg"}],
                )
