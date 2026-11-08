"""Native glyph storage admits only pure recipient reads in an actual read pass."""
from contextlib import nullcontext
import sys
import unittest
from unittest.mock import patch
from test_larva_glyph_movement_integration import LarvaGlyphMovementIntegrationTests
from wakfu_server import combat_ordinary_events as events_module
from wakfu_server import combat_retained_query as query
from wakfu_server.combat_external_read_pass import (
    external_recipient_read,
    external_read_pass,
    external_global_iterator,
    _plain_iteration,
)
from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_retained_collections import OwnedMap
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_state_managers import registered_area_pv
from wakfu_server.combat_retained_area_query import selected_area_manager


class OwnedAreaReadPassTests(unittest.TestCase):
    def fixture(self):
        helper = LarvaGlyphMovementIntegrationTests()
        _, _, fight, _, dispatcher = helper.fixture()
        row = helper.install_glyph(fight, dispatcher, fight.actors[7].position)
        retention = dispatcher.native_retention
        events = retention.stat_handler.event_lifecycle
        return fight, row, retention, events

    def test_native_glyph_reuses_views_and_revokes_for_mutation_or_opaque_readers(self):
        outcomes, builds = [], []
        for enabled in (False, True):
            fight, row, retention, events = self.fixture()
            identity = row["uid"]
            self.assertIs(type(row), OwnedAreaRow)
            self.assertTrue(events_module._pure_area_recipient_read(fight, identity))
            self.assertTrue(_plain_iteration(fight))
            calls = []
            codes = (query.manager_query.__code__, type(retention).view.__code__)

            def profile(frame, event, arg):
                if event == "call" and frame.f_code in codes:
                    calls.append(frame.f_code.co_name)

            gate = (
                nullcontext()
                if enabled
                else patch.object(
                    events_module, "_pure_area_recipient_read", return_value=False
                )
            )
            values, views = [], []
            previous = sys.getprofile()
            try:
                with gate, external_read_pass(
                    fight, events.replay, events.authority, retention
                ):
                    self.assertIsNotNone(events.replay._read_pass)
                    sys.setprofile(profile)
                    for _ in range(3):
                        with external_recipient_read(fight, identity, events.replay):
                            manager = registered_area_pv(fight, identity)
                        view = events.replay._current_view(7)
                        views.append(view)
                        values.append(
                            (manager.id, manager.position, tuple(view.entries))
                        )
                    if enabled:
                        print(
                            {
                                "routing": type(query.prepare_routing(fight)).__name__,
                                "area_running_manager": row.get(
                                    "native_running_effect_manager"
                                ),
                                "area_ledger": type(row.get("state_ledger")).__name__,
                                "selected_area_manager_none": selected_area_manager(
                                    fight, identity
                                )
                                is None,
                            }
                        )
                        self.assertTrue(all(view is views[0] for view in views))
                        before_iteration = events.replay._read_pass["view"]
                        tuple(external_global_iterator(fight, 7))
                        self.assertIs(
                            events.replay._read_pass["view"], before_iteration
                        )
            finally:
                sys.setprofile(previous)
            self.assertIsNone(events.replay._read_pass)
            outcomes.append((values, source_snapshot(fight)))
            builds.append(calls)
        self.assertEqual(*outcomes)
        self.assertLess(len(builds[1]), len(builds[0]), builds)
        print(
            {
                "scope": "native glyph external recipient read inside ordinary phase",
                "baseline_builds": builds[0],
                "owned_builds": builds[1],
            }
        )

        fight, row, retention, events = self.fixture()
        identity = row["uid"]
        with events_module._phase_read_pass(events, None):
            first = events.replay._current_view(7)
            with events.replay._callback_read_boundary():
                row["cell"] = (row["cell"][0] + 1, *row["cell"][1:])
            self.assertIsNone(events.replay._read_pass["view"])
            with external_recipient_read(fight, identity, events.replay):
                self.assertEqual(
                    registered_area_pv(fight, identity).position, tuple(row["cell"])
                )
                self.assertIsNot(events.replay._current_view(7), first)
        areas = fight.native_effect_areas
        retired = fight.native_retired_area_managers
        try:
            fight.native_retired_area_managers = {}
            self.assertFalse(events_module._pure_area_recipient_read(fight, identity))
            self.assertFalse(_plain_iteration(fight))
            fight.native_retired_area_managers = retired
            fight.native_effect_areas = dict(areas)
            self.assertFalse(events_module._pure_area_recipient_read(fight, identity))
            self.assertFalse(_plain_iteration(fight))
        finally:
            fight.native_effect_areas = areas
            fight.native_retired_area_managers = retired
        reads = []

        def opaque_attribute(self, name):
            reads.append(name)
            raise AssertionError("opaque owned-map attribute read")

        with patch.object(OwnedMap, "__getattribute__", new=opaque_attribute):
            self.assertFalse(events_module._pure_area_recipient_read(fight, identity))
            self.assertFalse(_plain_iteration(fight))
        self.assertEqual(reads, [])
        with patch.object(areas, "get", side_effect=AssertionError("custom map read")):
            self.assertFalse(events_module._pure_area_recipient_read(fight, identity))
            self.assertFalse(_plain_iteration(fight))
        other, _, _, _ = self.fixture()
        try:
            fight.native_effect_areas = other.native_effect_areas
            self.assertFalse(events_module._pure_area_recipient_read(fight, identity))
        finally:
            fight.native_effect_areas = areas
        original_contract = row["native_area_contract"]
        row["native_area_contract"] = "faN"
        self.assertFalse(events_module._pure_area_recipient_read(fight, identity))
        row["native_area_contract"] = original_contract

        class OpaqueRow(OwnedAreaRow):
            def get(self, *args):
                raise AssertionError("custom row getter")

        dict.__setitem__(areas, identity, OpaqueRow(row))
        try:
            self.assertFalse(events_module._pure_area_recipient_read(fight, identity))
        finally:
            dict.__setitem__(areas, identity, row)
        self.assertTrue(events_module._pure_area_recipient_read(fight, identity))


if __name__ == "__main__":
    unittest.main()
