"""Source-exported NPC roots extend class metadata without inferred defaults."""
from pathlib import Path
import unittest

import sys

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from stage_npc_casting_roots import merge, validate_domain


class NpcCastingRootImportTests(unittest.TestCase):
    def setUp(self):
        self.class_root = dict(
            native_casting_collision_area=None,
            native_selector_present=True,
            native_target_selector={"class": "fcE", "mask": 2},
        )
        self.npc_root = dict(
            native_casting_collision_area=None,
            native_selector_present=True,
            native_target_selector={"class": "fcE", "mask": 1},
        )
        self.base = dict(
            schema="native-class-casting-roots-v1",
            fight_properties={"sdR": 2},
            normal_casting_overrides={"categories": {}},
            roots={"99": self.class_root},
        )
        self.exported = {**self.base, "roots": {"361119": self.npc_root}}
        self.domain = dict(
            root_ids=[361119],
            spell_references=[7962],
            missing_casting_tables=[],
            base_revision="base",
            export_sha256="export",
            exporter_sha256="tool",
        )

    def test_preserves_all_class_roots_and_installs_exact_npc_selector(self):
        merged = merge(self.base, self.exported, self.domain)
        self.assertEqual(
            merged["roots"], {"99": self.class_root, "361119": self.npc_root}
        )
        self.assertEqual(self.base["roots"], {"99": self.class_root})
        self.assertEqual(merged["npc_ability_root_domain"]["spell_references"], [7962])

    def test_rejects_missing_domain_roots(self):
        self.domain["root_ids"].append(42)
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            merge(self.base, self.exported, self.domain)

    def test_domain_is_derived_from_pinned_monster_ownership_and_all_levels(self):
        monsters = {"monsters": [{"native_abilities": [{"spell_id": 7962}]}]}
        casting = {"spells": {"7962": {"levels": [[1, 1, [361119]]]}}}
        validate_domain(monsters, casting, self.domain)
        self.domain["root_ids"] = []
        with self.assertRaisesRegex(ValueError, "pinned ability catalogs"):
            validate_domain(monsters, casting, self.domain)

    def test_rejects_conflicting_existing_root(self):
        self.base["roots"]["361119"] = self.class_root
        with self.assertRaisesRegex(ValueError, "Conflicting original NPC"):
            merge(self.base, self.exported, self.domain)

    def test_rejects_missing_selector_and_global_contract_changes(self):
        self.exported["fight_properties"] = {"sdR": 99}
        with self.assertRaisesRegex(ValueError, "global metadata"):
            merge(self.base, self.exported, self.domain)
        self.exported["fight_properties"] = self.base["fight_properties"]
        self.npc_root.pop("native_casting_collision_area")
        with self.assertRaisesRegex(ValueError, "selector contract"):
            merge(self.base, self.exported, self.domain)


if __name__ == "__main__":
    unittest.main()
