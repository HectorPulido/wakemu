"""Prepared ecology plans survive unrelated catalog additions only."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from wakfu_server import (
    combat_ground_support,
    combat_npc_activation_policy,
    ecology_admin_planner,
    dungeon_main_completion,
    monster_initial_population,
    native_catalog_compatibility,
    native_catalog,
)

ROOT = Path(__file__).resolve().parents[2]


def _revision(hashes):
    return hashlib.sha256(
        b"".join(
            path.encode("utf8") + b"\0" + checksum.encode("ascii") + b"\n"
            for path, checksum in sorted(hashes.items())
        )
    ).hexdigest()


class FrozenConsumerSourceCompatibilityTests(unittest.TestCase):
    def setUp(self):
        manifest = json.loads(
            (ROOT / "database/data/installation/catalogs/manifest.json").read_bytes()
        )
        self.original = deepcopy(
            next(
                row
                for row in manifest["releases"]
                if row["revision"] == manifest["active_revision"]
            )
        )
        self.pinned = self.original["revision"]
        self.hashes = {row["path"]: row["sha256"] for row in self.original["documents"]}
        self.database, self.db = MagicMock(), MagicMock()
        self.database.connection.return_value.__enter__.return_value = self.db

    def _patched_revision(self, hashes):
        current = _revision(hashes)
        self.db.execute.reset_mock()
        self.db.execute.return_value.fetchone.return_value = None
        document = json.dumps(
            {
                "policy": native_catalog_compatibility.MANIFEST_POLICY,
                "releases": [self.original],
            }
        ).encode()
        native_catalog_compatibility._historical_documents.cache_clear()
        native_catalog_compatibility._current_documents.cache_clear()
        return (
            patch.object(
                native_catalog_compatibility.native_catalog,
                "release",
                return_value=current,
            ),
            patch.object(
                native_catalog_compatibility.native_catalog,
                "_database",
                return_value=self.database,
            ),
            patch.object(
                native_catalog_compatibility.native_catalog,
                "document_hashes",
                return_value=hashes,
            ),
            patch.object(
                native_catalog_compatibility.native_catalog,
                "read_published_bytes",
                return_value=document,
            ),
            current,
        )

    def test_prepared_dependencies_ignore_six_unrelated_edits_and_reject_changed_habitat(
        self,
    ):
        dependencies = monster_initial_population.proposal_dependencies(711)
        self.assertEqual(
            dependencies,
            (
                "initial-monster-population.json",
                "ecology-regions.json",
                "monsters.json",
                "native-actor-characteristics.json",
                "monster-encyclopedia.json",
                "combat-maps/711.json",
                "planting-maps/711.json",
            ),
        )
        changed_names = (
            "native-class-morph-a.json",
            "native-class-morph-b.json",
            "native-class-morph-c.json",
            "native-class-morph-d.json",
            "native-common-spell-effect-trees.json",
            "native-common-spell-casting-roots.json",
        )
        current_hashes = dict(self.hashes)
        for index, path in enumerate(changed_names):
            current_hashes[path] = f"{index + 1:064x}"
        current_hashes["new-unrelated-document.json"] = "f" * 64
        contexts = self._patched_revision(current_hashes)
        with contexts[0], contexts[1], contexts[2], contexts[3]:
            ecology_admin_planner.require_prepared_revision(self.pinned, 711)
            ecology_admin_planner.require_prepared_revision(
                self.pinned, 711, domain="flora"
            )

        habitat_changed = dict(current_hashes)
        habitat_changed["planting-maps/711.json"] = "e" * 64
        contexts = self._patched_revision(habitat_changed)
        with contexts[0], contexts[1], contexts[2], contexts[3]:
            with self.assertRaisesRegex(ValueError, "dependency changed"):
                ecology_admin_planner.require_prepared_revision(self.pinned, 711)
            store = MagicMock()
            result = monster_initial_population.apply_prepared(
                store,
                MagicMock(),
                {
                    "catalog_revision": self.pinned,
                    "plan": {"map_id": 711},
                    "policy": {},
                },
            )
            self.assertEqual(result, "stale")
            store.connection.assert_not_called()
            self.db.execute.reset_mock()
            with self.assertRaises(ValueError):
                ecology_admin_planner.require_prepared_revision(
                    self.pinned, 711, domain="unknown"
                )

    def test_ground_main_completion_and_npc_supplement_keep_their_failure_boundaries(
        self,
    ):
        candidate = "d" * 64
        with patch.object(
            native_catalog, "release", return_value=candidate
        ), patch.object(
            combat_ground_support,
            "_catalog",
            return_value={
                "schema": "wakemu-native-renderable-ground-support-v1",
                "qualified_native_release": self.pinned,
                "maps": {
                    "153": {
                        "map_id": 153,
                        "status": "exported",
                        "source_sha256": "a" * 64,
                        "supported_cells": [],
                        "unknown_material_cells": [],
                    }
                },
            },
        ), patch.object(
            native_catalog_compatibility,
            "require_source_revision",
            side_effect=ValueError("combat map dependency changed"),
        ) as require:
            combat_ground_support._map.cache_clear()
            with self.assertRaisesRegex(ValueError, "combat map dependency changed"):
                combat_ground_support.supported(153, (0, 0, 0), "a" * 64)
            require.assert_called_once_with(self.pinned, ("combat-maps/153.json",))
        combat_ground_support._map.cache_clear()

        rule = dungeon_main_completion.rules()[0]
        dungeon_main_completion._native_rule.cache_clear()
        with patch.object(
            native_catalog, "release", return_value=candidate
        ), patch.object(
            native_catalog_compatibility,
            "require_source_revision",
            side_effect=ValueError("main source changed"),
        ) as require:
            with self.assertRaisesRegex(ValueError, "main source changed"):
                dungeon_main_completion._native_rule(
                    rule["key"], dungeon_main_completion.digest(rule), candidate
                )
            require.assert_called_once_with(
                rule["qualified_native_release"],
                ("native-map-objects.json", "native-interactive-states.json"),
            )
        dungeon_main_completion._native_rule.cache_clear()

        base = deepcopy(combat_npc_activation_policy.current_policy())
        for reference in ("4400", "5114"):
            base["enabled_monsters"].pop(reference, None)
        combat_npc_activation_policy._CACHE.clear()
        with patch.object(
            native_catalog, "release", return_value=candidate
        ), patch.object(
            native_catalog_compatibility,
            "require_source_revision",
            side_effect=ValueError("supplement source changed"),
        ):
            merged = combat_npc_activation_policy.merge_policy(base, revision=candidate)
            self.assertIs(merged, base)
            self.assertNotIn("4400", merged["enabled_monsters"])

        combat_npc_activation_policy._CACHE.clear()
        with patch.object(
            native_catalog, "release", return_value=candidate
        ), patch.object(
            native_catalog_compatibility, "require_source_revision"
        ) as require, patch(
            "wakfu_server.combat_npc_event_controller.event_controller_record",
            return_value={"native": "qualified"},
        ):
            merged = combat_npc_activation_policy.merge_policy(base, revision=candidate)
            self.assertIsNot(merged, base)
            self.assertIn("4400", merged["enabled_monsters"])
            self.assertIn("5114", merged["enabled_monsters"])
            require.assert_called_once_with(
                combat_npc_activation_policy._supplement()["native_catalog_revision"],
                (
                    "native-npc-spell-effect-trees.json",
                    "monsters.json",
                    "combat-state-definitions.json",
                ),
            )


if __name__ == "__main__":
    unittest.main()
