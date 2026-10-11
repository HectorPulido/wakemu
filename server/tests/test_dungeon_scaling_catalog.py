"""Optional SQL supplement preserves existing native NPC activation data."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.maps import dungeon_scaling_catalog as catalog
from wakfu_server.maps.dungeon_combat_scaling import POLICY


class DungeonScalingCatalogTests(unittest.TestCase):
    def document(self):
        return dict(
            schema_version=1,
            policy=POLICY,
            hp={"70": 1},
            damage={"60": [2]},
            effects={
                "1": {"effect_class": 16, "children": []},
                "2": {"effect_class": 330, "children": [3]},
                "3": {"effect_class": 430, "children": []},
            },
        )

    def test_missing_setting_keeps_existing_source_identity(self):
        db = SimpleNamespace(
            execute=lambda *args: SimpleNamespace(fetchone=lambda: None)
        )
        self.assertIsNone(catalog.load(db))
        existing = {"99": {"effect_class": 1}}
        with patch.object(catalog, "current", return_value=None):
            self.assertIs(catalog.merge(existing), existing)

    def test_supplement_adds_closure_without_changing_ordinary_reference(self):
        existing = {"99": {"effect_class": 1, "parameters": [5, 0]}}
        merged = catalog.merge(existing, self.document())
        self.assertIs(merged["99"], existing["99"])
        self.assertEqual(set(merged), {"1", "2", "3", "99"})
        self.assertEqual(set(existing), {"99"})

    def test_matching_native_row_may_have_extra_samples_but_conflict_rejects(self):
        document = self.document()
        matching = {"1": dict(document["effects"]["1"], parameters_by_level=[[70]])}
        self.assertIs(catalog.merge(matching, document)["1"], matching["1"])
        with self.assertRaisesRegex(ValueError, "conflicts"):
            catalog.merge({"1": {"effect_class": 16, "children": [999]}}, document)

    def test_invalid_family_or_incomplete_closure_fails_before_activation(self):
        for mutate in (
            lambda d: d["effects"].pop("3"),
            lambda d: d["effects"]["1"].update(effect_class=304),
        ):
            document = self.document()
            mutate(document)
            db = SimpleNamespace(
                execute=lambda *args: SimpleNamespace(
                    fetchone=lambda: {"value": document}
                )
            )
            with self.assertRaises(ValueError):
                catalog.load(db)
