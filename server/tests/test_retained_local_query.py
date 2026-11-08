"""Local retained authority: current dependencies, independent historical wires."""
import unittest
from dataclasses import asdict
from unittest.mock import patch
from wakfu_server.combat_state import Fight, Actor
from wakfu_server.combat_state_ledger import RunningState
from wakfu_server.combat_effects import _integer
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_runtime import (
    NativeRetainedRuntime,
    native_retained_condition_effects,
)
from wakfu_server.combat_retained_query import (
    manager_query,
    LocalQueries,
    prepare_routing,
)
from wakfu_server.combat_event_replay import NativeEventReplay


def payload(uid, actor, generic=101):
    return b"".join(
        _integer(k, v)
        for k, v in ((1, uid), (2, uid), (3, generic), (6, actor), (7, actor))
    ).hex()


def fixture():
    fight = Fight.__new__(Fight)
    fight.actors = {i: Actor(i, i - 1, (i, 0, 0), 100, 6, 3, 10, 20) for i in (1, 2)}
    fight.native_retained_tracking = True
    for name in (
        "owned_stat_effects",
        "native_owned_group_effects",
        "native_owned_area_effects",
        "native_owned_spatial_effects",
        "state_wire_payloads",
        "native_effect_areas",
        "native_retired_area_managers",
        "native_owned_state_containers",
        "native_retained_records",
    ):
        setattr(fight, name, {})
    fight.native_retained_order = []
    for uid, actor in ((10, 1), (20, 2)):
        add_group(fight, uid, actor)
    retention = NativeRetainedRuntime.__new__(NativeRetainedRuntime)
    retention.fight = fight
    return fight, retention


def add_group(fight, uid, actor):
    fight.native_owned_group_effects[uid] = dict(
        target_id=actor, effect_class=330, state_uid=None, payload=payload(uid, actor)
    )
    fight.native_retained_records[uid] = asdict(
        RetainedEffect(uid, actor, 330, 101, manager_id=actor)
    )
    fight.native_retained_order.append(uid)


def add_parent(fight):
    parent = RunningState(30, 501, 1, 2, 2, -1, "target", False, (), 0, True, None)
    fight.actors[2].state_ledger._entries = (parent,)
    fight.state_wire_payloads[30] = payload(30, 2, 103)
    fight.native_retained_records[30] = asdict(
        RetainedEffect(30, 2, 310, 103, manager_id=2)
    )
    fight.native_retained_order.append(30)
    fight.native_owned_group_effects[10]["state_uid"] = 30
    fight.native_retained_records[10]["owner_uid"] = 30


class LocalRetainedQueryTests(unittest.TestCase):
    def test_valid_selected_matches_full_without_global_wire_decode(self):
        fight, retention = fixture()
        expected = retention.view().manager_entries(1)
        self.assertIsNotNone(prepare_routing(fight))
        selected = manager_query(fight, 1)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.entries, expected)
        fight.native_owned_group_effects[20]["payload"] = "zz"
        self.assertEqual(manager_query(fight, 1).entries, expected)
        with self.assertRaises(ValueError):
            manager_query(fight, 2)
        with self.assertRaises(ValueError):
            retention.view()

    def test_public_condition_read_ignores_unrelated_invalid_wire(self):
        fight, _ = fixture()
        fight.native_owned_group_effects[20]["payload"] = "zz"
        self.assertEqual(native_retained_condition_effects(fight, 1), ((101, 330, 10),))
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 2)

    def test_replay_routes_multiple_managers_and_refreshes_after_callback(self):
        fight, retention = fixture()
        replay = NativeEventReplay(None, retention)
        with patch.object(retention, "view", side_effect=AssertionError("full view")):
            # Method override intentionally disables native optimization.
            self.assertIsNone(
                __import__(
                    "wakfu_server.combat_retained_query", fromlist=["replay_queries"]
                ).replay_queries(retention)
            )
        with replay.read_pass():
            self.assertEqual([e.uid for e in replay._current_view(1).entries], [10])
            self.assertEqual([e.uid for e in replay._current_view(2).entries], [20])
            with replay._legacy_callback_read_boundary():
                add_group(fight, 11, 1)
            self.assertEqual([e.uid for e in replay._current_view(1).entries], [10, 11])
        fight.native_owned_group_effects[20]["payload"] = "zz"
        self.assertEqual([e.uid for e in replay._current_view(1).entries], [10, 11])
        with self.assertRaises(ValueError):
            replay._current_view(2)

    def test_parent_dependency_is_revalidated_without_delivering_parent(self):
        fight, _ = fixture()
        add_parent(fight)
        query = LocalQueries(fight)
        self.assertEqual([e.uid for e in query.for_manager(1).entries], [10])
        fight.state_wire_payloads[30] = payload(30, 2, 104)
        with self.assertRaises(ValueError):
            query.for_manager(1)
        fight.state_wire_payloads[30] = payload(30, 2, 103)
        fight.native_retained_records[30]["generic_effect"] = True
        with self.assertRaises(ValueError):
            manager_query(fight, 1)

    def test_condition_full_fallback_stays_one_snapshot_after_custom_callback(self):
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_reader,
        )

        fight, _ = fixture()

        class CustomFamily:
            def __eq__(self, other):
                fight.native_retained_records[10]["generic_effect"] = 102
                fight.native_owned_group_effects[20]["effect_class"] = 330
                return other == 330

        fight.native_owned_group_effects[20]["effect_class"] = CustomFamily()
        read = native_retained_condition_reader(fight)
        self.assertEqual(read(2), ((101, 330, 20),))
        self.assertEqual(read(1), ((101, 330, 10),))
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 1)

    def test_native_provider_overrides_keep_legacy_fallback(self):
        from wakfu_server.combat_retained_query import replay_queries

        _, retention = fixture()
        for method in ("view", "synchronize", "_live"):
            with self.subTest(method=method):
                with patch.object(retention, method, wraps=getattr(retention, method)):
                    self.assertIsNone(replay_queries(retention))

    def test_custom_source_value_falls_back_before_callback_and_resets_router(self):
        from wakfu_server.combat_retained_query import ReplayQueries

        fight, retention = fixture()
        observed = []

        class CustomFamily:
            def __eq__(self, other):
                observed.append(other)
                fight.native_retained_records[20]["manager_id"] = 1
                fight.native_owned_group_effects[10]["effect_class"] = 330
                return other == 330

        fight.native_owned_group_effects[10]["effect_class"] = CustomFamily()
        self.assertIsNone(manager_query(fight, 1))
        self.assertEqual(observed, [])
        provider = ReplayQueries(retention)
        provider.for_manager(1)
        self.assertTrue(observed)
        self.assertEqual([e.uid for e in provider.for_manager(1).entries], [10, 20])

    def test_new_query_observes_added_uid_and_custom_mapping_falls_back(self):
        fight, _ = fixture()
        self.assertEqual([e.uid for e in manager_query(fight, 1).entries], [10])
        add_group(fight, 11, 1)
        self.assertEqual([e.uid for e in manager_query(fight, 1).entries], [10, 11])

        class CustomRows(dict):
            pass

        fight.native_retained_records = CustomRows(fight.native_retained_records)
        self.assertIsNone(manager_query(fight, 1))
        self.assertEqual(
            native_retained_condition_effects(fight, 1),
            ((101, 330, 10), (101, 330, 11)),
        )


if __name__ == "__main__":
    unittest.main()
