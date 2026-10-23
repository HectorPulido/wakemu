"""Native faM authority and explicitly reconstructed movement pickup boundary."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_artifact_area import verify_artifact_area
from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime


class ArtifactAreaTests(unittest.TestCase):
    def fixture(self):
        definition = dict(
            type="ARTIFACT",
            native_class="bcC",
            native_type_id=20,
            native_container_type=3,
            native_shape_class="anD",
            native_shape_description="point",
            shape_parameters=[],
            entry_masks=[2243],
            exit_masks=[],
            native_removal_masks=[],
        )
        row = dict(
            uid=31,
            reference=1561,
            native_area_contract="faM",
            native_type_id=20,
            native_cells_xy=((0, 0),),
            cell=(0, 0, 0),
        )
        target = SimpleNamespace(id=8, position=(0, 0, 0), physical_radius=0)
        fight = SimpleNamespace(actors={8: target}, native_effect_areas={31: row})
        runtime = NativeAreaEventRuntime(fight, None, definitions={"1561": definition})
        return runtime, row, definition

    def test_constructor_rejects_substituted_native_factory_and_registered_type(self):
        _, row, definition = self.fixture()
        verify_artifact_area(row, definition)
        for key, value in (
            ("native_class", "bcT"),
            ("native_type_id", True),
            ("native_container_type", 2),
            ("native_shape_class", "anu"),
        ):
            with self.subTest(key=key):
                wrong = {**definition, key: value}
                with self.assertRaisesRegex(ValueError, "constructor authority"):
                    verify_artifact_area(row, wrong)
        with self.assertRaisesRegex(ValueError, "registered"):
            verify_artifact_area({**row, "native_type_id": 13}, definition)

    def test_pickup_frozen_actual_entry_only_preserves_other_movement_events(self):
        runtime, row, _ = self.fixture()
        delivered = []

        def deliver(candidate, definition, target, event_id, **kwargs):
            delivered.append((candidate, event_id, target.id))
            # Simulate earlier sibling callbacks unregistering the original Qq.
            runtime.fight.native_effect_areas.clear()
            return (event_id,)

        runtime._deliver_event = deliver
        with patch("wakfu_server.combat_effect_area_events._rows", return_value=(row,)):
            result = runtime.movement(8, from_cell=(-1, 0, 0), to_cell=(0, 0, 0))
        self.assertEqual([item[1] for item in delivered], [10001, 2243])
        self.assertTrue(all(item[0] is row for item in delivered))
        self.assertEqual(result, ((10001,), (), (), (2243,)))
        for origin, destination in (((0, 0, 0), (0, 0, 0)), ((0, 0, 0), (1, 0, 0))):
            delivered.clear()
            with patch(
                "wakfu_server.combat_effect_area_events._rows", return_value=(row,)
            ):
                runtime.movement(8, from_cell=origin, to_cell=destination)
            self.assertNotIn(2243, [item[1] for item in delivered])

    def test_exit_has_no_recipients_and_event_is_not_an_arbitrary_public_producer(self):
        runtime, row, _ = self.fixture()
        before = deepcopy(row)
        self.assertFalse(runtime._exit(row, runtime.fight.actors[8]))
        self.assertEqual(row, before)
        with self.assertRaisesRegex(ValueError, "Unknown native effect-area event"):
            runtime.event(2243, 8)
