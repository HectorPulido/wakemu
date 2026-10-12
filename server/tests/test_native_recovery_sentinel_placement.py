"""Native signed-short sentinel registration regressions."""
import unittest
from test_combat_summon_indexed_placement import NativeSummonIndexedPlacementTests
import wakfu_server.combat_summon_placement as shadow


class SentinelPlacementTests(NativeSummonIndexedPlacementTests):
    def test_exact_native_missing_index_sentinel_with_owned_qk(self):
        fight, actor, provenance, surfaces = self.fixture()
        fight.native_qi_snapshot["cell_masks"] = [257]
        actor.position = (-7, -21, -32768)
        with self.providers(provenance, surfaces):
            self.assertTrue(shadow.native_summon_placement(fight, actor))

    def test_sentinel_cannot_replace_present_selected_height(self):
        fight, actor, provenance, surfaces = self.fixture()
        actor.position = (-7, -21, -32768)
        with self.providers(provenance, surfaces):
            self.assertFalse(shadow.native_summon_placement(fight, actor))

    def test_sentinel_still_requires_owned_qk(self):
        fight, actor, provenance, surfaces = self.fixture()
        fight.native_qi_snapshot["cell_masks"] = [257]
        actor.position = (-7, -21, -32768)
        fight.native_qi_slots[2]["identity"] = ["actor", 90]
        with self.providers(provenance, surfaces):
            self.assertFalse(shadow.native_summon_placement(fight, actor))

    def test_sentinel_without_catalog_provenance_rejected(self):
        fight, actor, provenance, surfaces = self.fixture()
        fight.native_qi_snapshot["cell_masks"] = [257]
        actor.position = (-7, -21, -32768)
        del fight.native_qi_surface_provenance
        self.assertFalse(shadow.native_summon_placement(fight, actor))
