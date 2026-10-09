import unittest
from types import SimpleNamespace
from server.tests import test_combat_effect_area_events as area_event_tests
from wakfu_server.combat_effect_area_targets import NativeAreaTarget


class CapturedAreaActivationTests(unittest.TestCase):
    def fixture(self):
        runtime, row, calls = area_event_tests.AreaEventTests().fixture()
        definition = runtime.definitions["1474"]
        definition["native_area_properties"] = [1]
        row.update(
            native_fight_affiliation=0,
            native_fight_affiliation_source="faV.j(PV).bcM",
            remaining_activations=1,
        )
        target = runtime.fight.actors[8]
        target.native_is_amO = True
        target.native_fight_affiliation = 0
        return runtime, row, calls, definition, target

    def test_owner_change_does_not_change_captured_ally_filter(self):
        runtime, row, calls, definition, target = self.fixture()
        runtime.fight.actors[7].team = 1
        runtime.fight.actors[7].native_fight_affiliation = 1
        self.assertFalse(runtime._activate(row, definition, target))
        self.assertEqual((row["remaining_activations"], calls), (1, []))
        target.native_fight_affiliation = 1
        self.assertTrue(runtime._activate(row, definition, target))
        self.assertEqual(row["remaining_activations"], 0)
        self.assertEqual(len(calls), 1)

    def test_captured_filter_survives_absent_owner(self):
        runtime, row, calls, definition, target = self.fixture()
        del runtime.fight.actors[7]
        self.assertFalse(runtime._activate(row, definition, target))
        self.assertEqual(row["remaining_activations"], 1)

    def test_unknown_capture_and_unknown_target_reject_before_charge(self):
        for missing in ("capture", "target", "target_type"):
            runtime, row, calls, definition, target = self.fixture()
            if missing == "capture":
                row.pop("native_fight_affiliation_source")
            elif missing == "target":
                target.native_fight_affiliation = None
            else:
                del target.native_is_amO
            with self.assertRaisesRegex(ValueError, "native"):
                runtime._activate(row, definition, target)
            self.assertEqual((row["remaining_activations"], calls), (1, []))

    def test_null_qf_area_target_reads_its_captured_affiliation(self):
        runtime, row, calls, definition, target = self.fixture()
        runtime.fight.native_effect_areas[902] = dict(
            uid=902,
            native_fight_affiliation=0,
            native_fight_affiliation_source="faV.j(PV).bcM",
            native_running_effect_manager=False,
        )
        area = NativeAreaTarget(902, (0, 0, 0), 1, 99)
        self.assertFalse(runtime._activate(row, definition, area))
        self.assertEqual(row["remaining_activations"], 1)

    def test_null_and_explicit_non_amo_bypass_only_this_filter(self):
        runtime, row, calls, definition, target = self.fixture()
        row.pop("native_fight_affiliation_source")
        self.assertTrue(runtime._activate(row, definition, None))
        self.assertEqual(row["remaining_activations"], 0)
        target.native_is_amO = False
        self.assertIsNone(runtime._target_affiliation(target))

    def test_real_roster_target_uses_existing_typed_affiliation_provider(self):
        runtime, row, calls, definition, target = self.fixture()
        del target.native_is_amO

        class Adapter:
            def _actor(self, fight, actor):
                return SimpleNamespace(targeting=dict(is_amO=True, is_eGj=True))

            def affiliation(self, fight, identity):
                return 0

        runtime.dispatcher.contexts = SimpleNamespace(
            area_affiliation=Adapter().affiliation
        )
        self.assertFalse(runtime._activate(row, definition, target))
