import unittest
from wakfu_server import native_catalog as protocol_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.spell_audit import inspect_spell, catalog, costs_catalog


class NativeSpellAuditTests(unittest.TestCase):
    def test_complete_owned_catalog_and_native_level_tables(self):
        data = catalog()
        # Compare to the complete native owned-spell set, not a frozen count.
        native_ids = {
            str(spell["id"])
            for spell in protocol_catalog.load(DATA_ROOT / "spells.json")["spells"]
        }
        self.assertEqual(set(data["spells"]), native_ids)
        self.assertEqual(set(costs_catalog()), native_ids)
        for spell in data["spells"].values():
            self.assertEqual(len(spell["levels"]), 200)
            for _minimum, _maximum, roots in spell["levels"]:
                for reference in roots:
                    self.assertIn(str(reference), data["effects"])
        for effect in data["effects"].values():
            self.assertIs(type(effect["native_localization_enabled"]), bool)
            self.assertTrue(
                all(type(flag) is int for flag in effect["native_effect_flags"])
            )

    def test_iop_cannot_omit_required_states(self):
        for spell in (4778, 4780, 4785):
            audit = inspect_spell(spell, 1)
            self.assertIn("extra_effects_or_groups", audit["blockers"])
            self.assertFalse(audit["execution_verified"])
        effects = inspect_spell(4780, 1)["effects"]
        self.assertTrue(any(e["effect_class"] == 304 for e in effects))
        audit = inspect_spell(4780, 1)
        self.assertTrue(audit["linked_states"])
        self.assertTrue(any(e["state_path"] for e in audit["effects"]))

    def test_single_xelor_damage_still_requires_conditional_rules(self):
        result = inspect_spell(754, 19)
        self.assertEqual(result["blockers"], ["conditional_costs_or_range"])
        self.assertFalse(result["structurally_simple"])
        self.assertFalse(result["execution_verified"])

    def test_native_values_and_invalid_references(self):
        damage = next(
            e for e in inspect_spell(754, 19)["effects"] if e["reference"] == 98124
        )
        self.assertEqual(damage["parameter0"], 12)
        for args in ((754, 0), (754, 201), (-1, 1)):
            with self.assertRaises(ValueError):
                inspect_spell(*args)
