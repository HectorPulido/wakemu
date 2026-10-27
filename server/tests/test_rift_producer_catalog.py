"""Indexed original producer import and the weapon-prewarm merge backedge."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import unittest


class RiftProducerCatalogTests(unittest.TestCase):
    def test_original_indexed_leaf_compiles_and_remerges_unchanged_weapon_source(self):
        from tools.sublimation_bounded_census import BoundedDataset

        dataset = BoundedDataset(os.environ["WAKFU_RIFT_COMPONENT_MANIFEST"])
        self.assertIn("indexed_records", dataset.manifest)
        dataset.install_catalog_backend()
        path = Path(
            ".runtime/rift-phase2-dataset/native-artifact315-persistent-template.json"
        )
        raw = path.read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "9db04aa9f8d945cea3601388bcb9c508969a60aab338022a818e04d855df5760",
        )
        original = json.loads(raw)
        from wakfu_server import native_catalog
        from wakfu_server.rift_producer_catalog import original_artifact_producer
        from wakfu_server.combat_effect_runtime import _merge_effects
        from wakfu_server.combat_static_catalogs import CompiledEffects
        from wakfu_server.paths import DATA_ROOT

        reference = original["template_reference"]
        record = dict(
            path=original["source_document"],
            reference=reference,
            effect=original["effects"][str(reference)],
        )
        self.assertEqual(record["path"], "combat-state-definitions.json")
        # Only the published indexed record reader and its source inventory are
        # projected by the hash-pinned backend. No importer/compiler/gameplay
        # callback is replaced, and missing indexed dependencies fail closed.
        self.assertEqual(
            native_catalog.record(DATA_ROOT / record["path"], "effects", reference),
            record["effect"],
        )
        projected = original_artifact_producer(
            dict(
                source_kind="native_context_area_ref",
                template_effect_reference=reference,
                source_document=record["path"],
            )
        )
        self.assertEqual(projected["effects"], original["effects"])
        self.assertEqual(projected["provenance"]["revision"], original["revision"])
        compiled = CompiledEffects(
            projected["effects"],
            dict(states={}, effects=deepcopy(projected["effects"])),
        )
        self.assertEqual(compiled.effects[str(reference)]["effect_class"], 315)
        remerged = _merge_effects(
            compiled.source_effects,
            dict(effects={str(reference): deepcopy(record["effect"])}),
        )
        self.assertEqual(remerged, projected["effects"])
        from wakfu_server.combat_native_timing_context import native_definition_timing

        timing = native_definition_timing(projected["effects"][str(reference)], 245)
        self.assertEqual(timing, dict(retained=True, delay=False, duration=-1))
        legacy_raw = Path(
            ".runtime/rift-phase2-dataset/native-artifact315-template.json"
        ).read_bytes()
        self.assertEqual(
            hashlib.sha256(legacy_raw).hexdigest(),
            "defa64e1b2f9b959f4d1addc64ba3483bcce4a3654dcf1693b49904ca1abaf66",
        )
        legacy = json.loads(legacy_raw)
        weapon_overlay = _merge_effects(compiled.source_effects, legacy)
        self.assertEqual(
            weapon_overlay[str(reference)], projected["effects"][str(reference)]
        )
        self.assertEqual(
            weapon_overlay[str(legacy["template_reference"])],
            legacy["effects"][str(legacy["template_reference"])],
        )
        altered = deepcopy(record["effect"])
        altered["parameters"][0] += 1
        with self.assertRaisesRegex(ValueError, "Conflicting native"):
            _merge_effects(
                compiled.source_effects, dict(effects={str(reference): altered})
            )
