"""Shared indexed read consumption, lifecycle boundaries and plain snapshots."""
from copy import deepcopy
from dataclasses import asdict
import unittest
from unittest.mock import patch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_retained_collections import OwnedMap, RetainedCollections
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_runtime import (
    NativeRetainedRuntime,
    native_retained_condition_effects,
)
from wakfu_server.combat_retained_query import (
    IndexedRouting,
    manager_query,
    prepare_routing,
)
from wakfu_server.combat_event_replay import NativeEventReplay
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from test_retained_local_query import payload


def fixture():
    actors = [Actor(i, i - 1, (i, 0, 0), 100, 6, 3, 10, 20) for i in (1, 2)]
    fight = Fight(7, actors, {(1, 0, 0), (2, 0, 0)}, {0: {(1, 0, 0)}, 1: {(2, 0, 0)}})
    retention = NativeRetainedRuntime.__new__(NativeRetainedRuntime)
    retention.fight = fight
    for uid, identity in ((10, 1), (20, 2)):
        install(fight, retention, uid, identity)
    return fight, retention


def install(fight, retention, uid, identity):
    fight.native_owned_group_effects[uid] = dict(
        target_id=identity,
        effect_class=330,
        state_uid=None,
        payload=payload(uid, identity),
    )
    retention.record(RetainedEffect(uid, identity, 330, 101, manager_id=identity))


class IndexedRetainedQueryTests(unittest.TestCase):
    def test_real_fight_registration_reads_no_global_maps(self):
        fight, _ = fixture()
        self.assertIs(type(prepare_routing(fight)), IndexedRouting)
        fight.native_owned_group_effects[20]["payload"] = "zz"
        with patch.object(
            OwnedMap, "values", side_effect=AssertionError("global values")
        ):
            with patch.object(
                OwnedMap, "items", side_effect=AssertionError("global items")
            ):
                with patch.object(
                    OwnedMap, "__iter__", side_effect=AssertionError("global iteration")
                ):
                    self.assertEqual(
                        native_retained_condition_effects(fight, 1), ((101, 330, 10),)
                    )
        with self.assertRaises(ValueError):
            manager_query(fight, 2)

    def test_indexed_parent_authority_rechecks_actual_ledger_and_wire(self):
        from wakfu_server.combat_state_ledger import RunningState

        fight, retention = fixture()
        parent = RunningState(30, 501, 1, 2, 2, -1, "target", False, (), 0, True, None)
        fight.actors[2].state_ledger._entries = (parent,)
        fight.state_wire_payloads[30] = payload(30, 2, 103)
        retention.record(RetainedEffect(30, 2, 310, 103, manager_id=2))
        fight.native_owned_group_effects[10]["state_uid"] = 30
        fight.native_retained_records[10]["owner_uid"] = 30
        self.assertEqual([e.uid for e in manager_query(fight, 1).entries], [10])
        fight.state_wire_payloads[30] = payload(30, 2, 104)
        with self.assertRaises(ValueError):
            manager_query(fight, 1)
        fight.state_wire_payloads[30] = payload(30, 2, 103)
        fight.actors[2].state_ledger._entries = ()
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 1)

    def test_indexed_selected_custom_keys_defer_without_comparison(self):
        fight, _ = fixture()
        comparisons = []

        class Key:
            def __hash__(self):
                return hash("effect_class")

            def __eq__(self, other):
                comparisons.append(other)
                return other == "effect_class"

        fight.native_owned_group_effects[10] = {
            "target_id": 1,
            Key(): 330,
            "state_uid": None,
            "payload": payload(10, 1),
        }
        comparisons.clear()
        self.assertIsNone(manager_query(fight, 1))
        self.assertEqual(comparisons, [])
        self.assertEqual(native_retained_condition_effects(fight, 1), ((101, 330, 10),))
        self.assertTrue(comparisons)

    def test_indexed_probe_does_not_build_stage1_locator_for_plain_storage(self):
        from test_retained_local_query import fixture as plain_fixture
        from wakfu_server.combat_retained_query import replay_queries

        _, retention = plain_fixture()
        with patch(
            "wakfu_server.combat_retained_query.prepare_routing",
            side_effect=AssertionError("historical routing"),
        ):
            self.assertIsNone(replay_queries(retention, indexed_only=True))

    def test_source_before_metadata_and_removal_require_reconciliation(self):
        fight, retention = fixture()
        fight.native_owned_group_effects[11] = dict(
            target_id=1, effect_class=330, state_uid=None, payload=payload(11, 1)
        )
        self.assertIsNone(prepare_routing(fight))
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 1)
        retention.record(RetainedEffect(11, 1, 330, 101, manager_id=1))
        self.assertEqual([e.uid for e in manager_query(fight, 1).entries], [10, 11])
        fight.native_owned_group_effects.pop(11)
        self.assertIsNone(prepare_routing(fight))
        retention.view()
        self.assertEqual([e.uid for e in manager_query(fight, 1).entries], [10])

    def test_manager_rehome_payload_alias_and_replacement_are_current(self):
        fight, _ = fixture()
        fight.native_retained_records[20]["manager_id"] = 1
        self.assertEqual([e.uid for e in manager_query(fight, 1).entries], [10, 20])
        alias = fight.native_owned_group_effects[20]
        alias["payload"] = "zz"
        with self.assertRaises(ValueError):
            manager_query(fight, 1)
        alias["payload"] = payload(20, 2)
        fight.native_owned_group_effects = dict(fight.native_owned_group_effects)
        self.assertIsNone(prepare_routing(fight))
        self.assertEqual(
            native_retained_condition_effects(fight, 1),
            ((101, 330, 10), (101, 330, 20)),
        )

    def test_initialization_adoption_preserves_actual_roster_and_binds_new_storage(
        self,
    ):
        from wakfu_server.combat_actor_snapshot import _adopt_initialized_fight
        from wakfu_server.combat_retained_collections import bound_collections

        fight, _ = fixture()
        actual_actors, actor = fight.actors, fight.actors[1]
        original_fields = dict(vars(fight))
        preview = deepcopy(fight)
        preview.actors[1].hp -= 5
        _adopt_initialized_fight(fight, preview, None)
        self.assertIs(fight.actors, actual_actors)
        self.assertIs(fight.actors[1], actor)
        self.assertEqual(actor.hp, 95)
        self.assertIsNotNone(bound_collections(vars(fight)))
        self.assertIsNone(bound_collections(original_fields))
        self.assertIs(type(prepare_routing(fight)), IndexedRouting)
        self.assertEqual([e.uid for e in manager_query(fight, 1).entries], [10])

    def test_clone_and_same_identity_adoption_rebind_owner(self):
        fight, _ = fixture()
        clone = deepcopy(fight)
        self.assertIsNot(
            clone.native_retained_records.owner, fight.native_retained_records.owner
        )
        clone.native_retained_records[20]["manager_id"] = 1
        self.assertEqual([e.uid for e in manager_query(clone, 1).entries], [10, 20])
        self.assertEqual([e.uid for e in manager_query(fight, 1).entries], [10])
        fight.__dict__.clear()
        fight.__dict__.update(clone.__dict__)
        self.assertEqual([e.uid for e in manager_query(fight, 1).entries], [10, 20])

    def test_reproduction_rebuilds_only_routing_and_preserves_aliases(self):
        fight, _ = fixture()
        graph = [
            fight,
            fight.native_retained_records[10],
            fight.native_owned_group_effects,
        ]
        restored = decode_state(encode_state(graph))
        current = restored[0]
        self.assertIs(type(current.native_retained_records), OwnedMap)
        self.assertIs(restored[1], current.native_retained_records[10])
        self.assertIs(restored[2], current.native_owned_group_effects)
        self.assertEqual(
            native_retained_condition_effects(current, 1), ((101, 330, 10),)
        )
        self.assertIs(type(prepare_routing(current)), IndexedRouting)

    def test_legacy_plain_restore_is_owned_once_without_modifying_input(self):
        fight, _ = fixture()
        encoded = encode_state(fight)
        for node in encoded["nodes"]:
            for key in (
                "native_retained_storage",
                "native_retained_owner",
                "native_retained_uid",
            ):
                node.pop(key, None)
        before = deepcopy(encoded)
        restored = decode_state(encoded)
        self.assertEqual(encoded, before)
        self.assertIs(type(prepare_routing(restored)), IndexedRouting)
        self.assertEqual(
            native_retained_condition_effects(restored, 1), ((101, 330, 10),)
        )

    def test_registered_summon_stays_indexed_temporary_detached_scope_falls_back(self):
        from types import SimpleNamespace
        from wakfu_server.combat_summon_initialization import (
            _construction,
            DetachedSummonConstruction,
        )

        fight, _ = fixture()
        summon = Actor(3, 0, (3, 0, 0), 100, 6, 3, 10, 20, owner_id=1)
        fight.actors[3] = summon
        self.assertIs(type(prepare_routing(fight)), IndexedRouting)
        detached = Actor(4, 0, (4, 0, 0), 100, 6, 3, 10, 20, owner_id=1)
        token = _construction.set(
            (DetachedSummonConstruction(fight, detached, object()),)
        )
        try:
            self.assertIsNone(prepare_routing(fight))
        finally:
            _construction.reset(token)
        self.assertIs(type(prepare_routing(fight)), IndexedRouting)
        self.assertEqual(manager_query(fight, 3).entries, ())

    def test_native_replacement_preserves_gateway_and_detached_old_alias(self):
        from wakfu_server.combat_retained_collections import replace_collection

        fight, _ = fixture()
        old = fight.actors
        replace_collection(fight, "actors", dict(fight.actors))
        self.assertIsNot(fight.actors, old)
        old["opaque"] = object()
        self.assertIs(type(prepare_routing(fight)), IndexedRouting)
        records = {10: fight.native_retained_records[10]}
        fight.native_owned_group_effects.pop(20)
        replace_collection(fight, "native_retained_records", records)
        fight.native_retained_order[:] = [10]
        self.assertIs(type(prepare_routing(fight)), IndexedRouting)
        self.assertIs(fight.native_retained_records[10], records[10])

    def test_spatial_publication_does_not_deepcopy_unrelated_registry(self):
        from native_combat_fixture import initialize_fixture_qi
        from wakfu_server.combat_pointer_qi_actor import ActualActorQI
        from wakfu_server.combat_pointer_qi_checkpoint import NativePointerCheckpoint
        from wakfu_server.combat_pointer_qi_commit import PointerCommitBinding
        from wakfu_server.combat_retained_collections import bound_collections

        fight, _ = fixture()
        initialize_fixture_qi(fight)
        fight.native_pointer_checkpoint = NativePointerCheckpoint(ActualActorQI(fight))
        destination = deepcopy(fight)
        binding = PointerCommitBinding(fight)
        with patch.object(
            RetainedCollections,
            "__deepcopy__",
            side_effect=AssertionError("unrelated registry clone"),
        ):
            binding.stage(destination)
        binding.publish()
        self.assertIsNotNone(bound_collections(vars(destination)))
        self.assertIs(
            destination.native_pointer_checkpoint.validate(destination)
            .objects[1]
            .actor,
            destination.actors[1],
        )

    def test_indexed_replay_inside_event_frame_does_not_rebuild_population(self):
        fight, retention = fixture()
        replay = NativeEventReplay(None, retention)
        with patch(
            "wakfu_server.combat_structural_qf_scope.event_frame", return_value=object()
        ):
            with patch.object(
                retention,
                "event_population",
                side_effect=AssertionError("global population"),
            ):
                self.assertEqual([e.uid for e in replay._current_view(1).entries], [10])
                self.assertEqual([e.uid for e in replay._current_view(2).entries], [20])


if __name__ == "__main__":
    unittest.main()
