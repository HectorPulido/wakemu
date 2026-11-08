"""New native source rows retain the existing callback-free manager pass."""
import unittest
from unittest.mock import patch

import test_combat_retained_manager_pass as fixture
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow
from wakfu_server.combat_pointer_qi_spatialowned import NativeSpatialRecord


class NativeSourceManagerPassTests(unittest.TestCase):
    def test_native_source_rows_keep_pass_and_custom_reads_keep_fallback(self):
        runtime, fight = fixture.RetainedManagerPassTests().fixture(count=2)
        for uid, original in tuple(fight.owned_stat_effects.items()):
            fight.owned_stat_effects[uid] = OwnedStateSourceRow(original)
        self.assertIsNotNone(runtime._pure_view_manager_pass())
        selected = runtime.view()
        with patch.object(
            NativeRetainedRuntime, "_pure_view_manager_pass", return_value=None
        ):
            fallback = runtime.view()
        self.assertEqual(selected.entries, fallback.entries)

        class CustomSource(OwnedStateSourceRow):
            pass

        original = fight.owned_stat_effects[100]
        fight.owned_stat_effects[100] = CustomSource(original)
        self.assertIsNone(runtime._pure_view_manager_pass())
        self.assertEqual(runtime.view().entries, fallback.entries)
        fight.owned_stat_effects[100] = original
        original.get = lambda *args: dict.get(original, *args)
        self.assertIsNone(runtime._pure_view_manager_pass())
        del original.get

        # Spatial records retain their hidden runner/PK validation calls and
        # are intentionally not certified solely by their public dict reads.
        spatial = dict.__new__(NativeSpatialRecord)
        dict.__init__(spatial, uid=199)
        fight.native_owned_spatial_effects = {}
        fight.native_owned_spatial_effects[199] = spatial
        self.assertIsNone(runtime._pure_view_manager_pass())


if __name__ == "__main__":
    unittest.main()
