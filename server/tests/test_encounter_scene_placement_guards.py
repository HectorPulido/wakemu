"""Guards for the sealed scene crossing durable placement."""
from copy import deepcopy
import unittest

from wakfu_server.combat_encounter_scene_policy import prepare_scene, _digest
from wakfu_server.combat_placement_policy import _placement_scene


class EncounterScenePlacementGuards(unittest.TestCase):
    def setUp(self):
        self.cells = {(0, 0, 0), (1, 0, 0)}
        self.record = prepare_scene(
            dict(
                schema_version=1,
                full_room_scope=True,
                policy_id="placement-seal-test",
                authority="explicit-source-qualified-test",
                source_uri="native:test",
            ),
            scope=dict(
                map_id=1134,
                instance_id=0,
                group_id=1,
                room_order=1,
                policy_version=1,
                route_key="placement-test",
                evidence_hashes={},
            ),
            room_cells=self.cells,
        )

    def validate(self, record, **kwargs):
        return _placement_scene(
            record, map_id=1134, instance_id=0, cells=kwargs.get("cells", self.cells)
        )

    def test_scene_is_copied_and_legacy_absence_stays_absent(self):
        result = self.validate(self.record)
        self.assertEqual(result, self.record)
        result["descriptor"]["policy_id"] = "changed"
        self.assertEqual(self.record["descriptor"]["policy_id"], "placement-seal-test")
        self.assertIsNone(self.validate(None))

    def test_tampered_seal_is_rejected(self):
        record = deepcopy(self.record)
        record["descriptor"]["policy_id"] = "changed"
        with self.assertRaises(ValueError):
            self.validate(record)

    def test_resealed_foreign_scope_and_malformed_program_are_rejected(self):
        for mutate in (
            lambda r: r["scope"].update(instance_id=9),
            lambda r: r["descriptor"].update(full_room_scope="true"),
        ):
            record = deepcopy(self.record)
            mutate(record)
            record["sha256"] = _digest(
                {k: v for k, v in record.items() if k != "sha256"}
            )
            with self.assertRaises(ValueError):
                self.validate(record)

    def test_full_room_crop_and_foreign_cell_are_rejected(self):
        for cells in ({(0, 0, 0)}, self.cells | {(2, 0, 0)}):
            with self.assertRaises(ValueError):
                self.validate(self.record, cells=cells)
