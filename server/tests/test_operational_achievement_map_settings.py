"""Database operational policy authority without runtime JSON file access."""
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch
from wakfu_server.achievements import catalog
from wakfu_server import admin_map_catalog


class OperationalAchievementMapSettingsTests(TestCase):
    def test_exact_migration_seed_preserves_all_reviewed_rules_and_labels(self):
        sql = Path(
            "server/migrations/152_achievement_rules_admin_map_names.sql"
        ).read_text()
        rules = json.loads(sql.split("$rules$")[1])
        names = json.loads(sql.split("$names$")[1])
        self.assertEqual(
            rules,
            json.loads(
                Path(catalog.__file__).with_name("qualified_rules.json").read_text()
            ),
        )
        self.assertEqual(
            names,
            json.loads(
                Path(admin_map_catalog.__file__)
                .with_name("admin_map_names.json")
                .read_text()
            ),
        )
        db = Mock()
        db.execute.return_value.fetchone.return_value = {"value": rules}
        with patch.object(
            Path, "read_text", side_effect=AssertionError("Runtime filesystem read")
        ):
            loaded = catalog.load(db)
        self.assertEqual(len(loaded["definitions"]), 30)
        self.assertEqual(
            sum(len(row["objectives"]) for row in loaded["definitions"].values()), 69
        )
        db.execute.return_value.fetchone.return_value = {"value": names}
        with patch.object(
            Path, "read_text", side_effect=AssertionError("Runtime filesystem read")
        ):
            self.assertEqual(admin_map_catalog.load(db), names)
        self.assertIn("ON CONFLICT (name) DO NOTHING", sql)

    def test_missing_or_invalid_database_policy_has_no_file_fallback(self):
        for value in [None, {"value": None}, {"value": {}}, {"value": []}]:
            db = Mock()
            db.execute.return_value.fetchone.return_value = value
            with self.subTest(value=value), patch.object(
                Path, "read_text", side_effect=AssertionError("Fallback read")
            ):
                with self.assertRaises(ValueError):
                    catalog.load(db)
        for names in [
            None,
            [],
            {"01": "Invalid"},
            {"x": "Invalid"},
            {"1": ""},
            {"1": 5},
        ]:
            db = Mock()
            db.execute.return_value.fetchone.return_value = {"value": names}
            with self.subTest(names=names), self.assertRaises(ValueError):
                admin_map_catalog.load(db)

    def test_live_database_labels_preserve_operator_precedence_and_unknowns(self):
        db = Mock()
        db.execute.return_value.fetchone.return_value = {"value": {"527": "Native"}}
        names = admin_map_catalog.load(db)
        self.assertEqual(
            admin_map_catalog.label({"id": 527, "name": "Operator"}, names)[
                "name_source"
            ],
            "operator",
        )
        self.assertEqual(admin_map_catalog.label({"id": 527}, names)["name"], "Native")
        self.assertEqual(
            admin_map_catalog.label({"id": 99999}, names)["name"], "Map #99999"
        )
        db.execute.return_value.fetchone.return_value = {"value": {"527": "Updated"}}
        self.assertEqual(admin_map_catalog.load(db)["527"], "Updated")
