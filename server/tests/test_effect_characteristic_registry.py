import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "server/protocol/effect-characteristic-registry.json"


class NativeCharacteristicRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text())
        cls.effects = cls.catalog["effects"]

    def test_registry_matches_installed_client_and_owned_wire_opcodes(self):
        self.assertEqual(
            self.catalog["client_jar_sha256"],
            hashlib.sha256(
                (ROOT / "client/lib/wakfu-client.jar").read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(
            (self.catalog["application_opcode"], self.catalog["removal_opcode"]),
            (13497, 13560),
        )

    def test_native_known_characteristics_and_dynamic_registry(self):
        for effect, runner, stat in [
            ("120", "eWQ", 20),
            ("130", "eWR", 20),
            ("193", "eWQ", 4),
            ("26", "eWQ", 18),
            ("1095", "eWQ", 114),
            ("1011", "eWR", 97),
        ]:
            self.assertEqual(
                (self.effects[effect]["runner"], self.effects[effect]["fixed_stat_id"]),
                (runner, stat),
            )
        for effect in ("39", "40"):
            self.assertIsNone(self.effects[effect]["fixed_stat_id"])
            self.assertTrue(self.effects[effect]["dynamic_stat"])
        self.assertNotIn("1201", self.effects)  # eWS maximum family excluded

    def test_current_families_have_native_codec_fields_and_explicit_guards(self):
        for key, row in self.effects.items():
            self.assertEqual(int(key), row["effect_class"])
            if row["runner"] == "eXE":
                continue
            self.assertIn(row["runner"], ("eWQ", "eWR"))
            self.assertEqual(row["additional_fields"], dict(stat_id=12, requested=25))
            self.assertEqual(row["dynamic_stat"], row["fixed_stat_id"] is None)
            self.assertTrue(row["zero_initial_amount_rejected"])
            self.assertEqual(row["source_guards"][0]["native_method"], "eWW.fMy")
            if row["runner"] == "eWQ":
                self.assertEqual(
                    (
                        row["source_guards"][1]["stat_id"],
                        row["source_guards"][1]["bypass_flag"],
                    ),
                    (33, 21),
                )
            else:
                self.assertEqual(
                    (
                        row["source_guards"][1]["stat_id"],
                        row["source_guards"][1]["property_id"],
                    ),
                    (3, 4),
                )
            self.assertEqual(
                row["limit_policy_requires_owned_stack"],
                row["limit_policy"] == "RESISTANCE_CAP",
            )

    def test_null400_parameterless_status_and_levelzero_semantics(self):
        row = self.effects["400"]
        self.assertEqual((row["runner"], row["operation"]), ("eXE", "none"))
        self.assertEqual(row["parameter_contract"]["parameterless_status"], -1)
        self.assertEqual(
            row["parameter_contract"]["parameterless_status_policy"],
            "preserve_existing_status",
        )
        self.assertEqual(row["parameter_contract"]["evaluation_level"], 0)
        self.assertFalse(row["parameter_contract"]["current_stat_change"])
        self.assertEqual(row["additional_fields"], {})
