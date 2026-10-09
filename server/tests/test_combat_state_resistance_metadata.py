import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from wakfu_server.combat import combat_state_resistance_metadata as metadata


class StateResistanceMetadataTests(unittest.TestCase):
    def document(self):
        return dict(
            schema="native-class-state-resistance-v1",
            seed_identity=dict(
                schema="native-class-state-resistance-seeds-v1", state_ids=[9323, 759]
            ),
            provenance=dict(original_inputs_stable=True),
            enum_ordinals={"NEGATIF": 0, "NEUTRAL": 1, "POSITIF": 2},
            native_level_checks=6,
            missing_state_ids=[759],
            states={
                "9323": dict(
                    native_getter="fyW.elk",
                    native_resistance_mode=dict(
                        enum_class="fza", name="POSITIF", ordinal=2
                    ),
                )
            },
        )

    def query(self, document, fn):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "native-class-state-resistance.json").write_text(
                json.dumps(document)
            )
            metadata.native_state_resistance_catalog.cache_clear()
            with patch.object(metadata, "DATA_ROOT", Path(directory)):
                try:
                    return fn()
                finally:
                    metadata.native_state_resistance_catalog.cache_clear()

    def test_exact_enum_identity_and_missing_state_remain_distinct(self):
        def check():
            self.assertEqual(
                metadata.native_state_resistance_mode(9323),
                dict(enum_class="fza", name="POSITIF", ordinal=2),
            )
            with self.assertRaisesRegex(ValueError, "outside proven"):
                metadata.native_state_resistance_mode(759)

        self.query(self.document(), check)

    def test_enum_conflict_and_unsealed_source_rejected(self):
        doc = self.document()
        doc["states"]["9323"]["native_resistance_mode"]["ordinal"] = 0
        with self.assertRaisesRegex(ValueError, "Invalid native"):
            self.query(doc, metadata.native_state_resistance_catalog)
        doc = self.document()
        doc["provenance"]["original_inputs_stable"] = False
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.query(doc, metadata.native_state_resistance_catalog)
