"""Focused storage gateway checks, without catalog or database imports."""
from copy import deepcopy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_retained_collections import (
    RetainedCollections,
    OwnedMap,
    OwnedOrder,
    TrackedRow,
    SOURCE_NAMES,
    restore_collections,
    replace_collection,
    bound_collections,
    owned_metadata_row,
    bind_adopted_actors,
)


class RetainedCollectionsTests(unittest.TestCase):
    def test_actor_adoption_preserves_outer_alias_and_rejects_old_binding(self):
        old, fresh = RetainedCollections(), RetainedCollections()
        actor = object()
        old.actors[-1] = actor
        old_fields = dict(
            native_retained_records=old.records,
            native_retained_order=old.order,
            actors=old.actors,
            **old.sources
        )
        fight = SimpleNamespace(
            native_retained_records=fresh.records,
            native_retained_order=fresh.order,
            actors=fresh.actors,
            **fresh.sources
        )
        alias = old.actors
        self.assertIs(bind_adopted_actors(fight, alias), alias)
        self.assertIs(fight.actors, alias)
        self.assertIs(fight.actors[-1], actor)
        self.assertIs(alias.owner, fresh)
        self.assertIs(bound_collections(vars(fight)), fresh)
        self.assertIsNone(bound_collections(old_fields))

    def test_binding_rejects_wrong_owner_or_role_without_scanning(self):
        owner, foreign = RetainedCollections(), RetainedCollections()
        self.install(owner, 11, -1)
        fields = dict(
            native_retained_records=owner.records,
            native_retained_order=owner.order,
            actors=owner.actors,
            **owner.sources
        )
        with patch.object(OwnedMap, "__iter__", side_effect=AssertionError("scan")):
            self.assertIs(bound_collections(fields), owner)
            self.assertTrue(owned_metadata_row(owner, 11, owner.records[11]))
            fields["actors"] = foreign.actors
            self.assertIsNone(bound_collections(fields))
            fields["actors"] = owner.actors
            owner.sources["state_wire_payloads"].name = "owned_stat_effects"
            self.assertIsNone(bound_collections(fields))
        old = owner.records[11]
        owner.records.install_owned(11, dict(uid=11, manager_id=-2))
        self.assertFalse(owned_metadata_row(owner, 11, old))

        class OpaqueSources:
            def get(self, name):
                raise AssertionError("Opaque source mapping callback")

        owner.sources = OpaqueSources()
        self.assertIsNone(bound_collections(fields))

    def install(self, owner, uid, manager):
        row = dict(uid=uid, manager_id=manager, target_id=manager)
        owner.records.install_owned(uid, row)
        owner.order.append(uid)
        owner.sources["owned_stat_effects"][uid] = {"payload": "00"}
        return row

    def test_owned_metadata_rehomes_external_metadata_falls_back(self):
        owner = RetainedCollections()
        original = self.install(owner, 11, -1)
        original["manager_id"] = 900
        self.assertEqual(owner.manager_uids(-1), (11,))

        owner.records[11]["manager_id"] = -2
        self.assertEqual(owner.manager_uids(-1), ())
        self.assertEqual(owner.manager_uids(-2), (11,))
        external = dict(uid=12, manager_id=-2)
        owner.records[12] = external
        self.assertIs(owner.records[12], external)
        self.assertFalse(owner.consistent())

    def test_source_reinsertion_order_and_opaque_actor_keys(self):
        owner = RetainedCollections()
        source = owner.sources["owned_stat_effects"]
        self.install(owner, 11, -1)
        self.install(owner, 12, -1)
        row = source.pop(11)
        source[11] = row
        self.assertEqual(owner.source_uids("owned_stat_effects", {11, 12}), (12, 11))
        owner.actors[-1] = object()
        self.assertTrue(owner.consistent())
        owner.actors["-2"] = object()
        self.assertFalse(owner.consistent())

    def test_source_pending_membership_order_and_payload_aliases(self):
        owner = RetainedCollections()
        self.install(owner, 11, -1)
        self.install(owner, 12, -1)
        self.assertTrue(owner.consistent())
        owner.order.reverse()
        self.assertEqual(owner.manager_uids(-1), (12, 11))
        payload = owner.sources["owned_stat_effects"][11]
        payload["payload"] = "01"
        self.assertIs(owner.sources["owned_stat_effects"][11], payload)
        owner.sources["state_wire_payloads"][13] = "02"
        self.assertFalse(owner.consistent())
        self.assertTrue(owner.consistent(pending={13}))
        owner.sources["state_wire_payloads"].pop(13)
        owner.sources["state_wire_payloads"][11] = "03"
        self.assertFalse(owner.consistent())
        owner.sources["state_wire_payloads"].clear()
        del owner.records[12]
        del owner.sources["owned_stat_effects"][12]
        owner.order.remove(12)
        self.assertTrue(owner.consistent())
        self.assertEqual(owner.manager_uids(-1), (11,))

    def test_deepcopy_preserves_aliases_with_fresh_owner_and_plain_json(self):
        owner = RetainedCollections()
        self.install(owner, 11, -1)
        graph = [
            owner.records[11],
            owner.records,
            owner.order,
            owner.sources["owned_stat_effects"],
        ]
        copied = deepcopy(graph)
        fresh = copied[1].owner
        self.assertIsNot(fresh, owner)
        self.assertIs(copied[0], copied[1][11])
        self.assertIs(copied[2], fresh.order)
        self.assertIs(copied[3], fresh.sources["owned_stat_effects"])
        copied[0]["manager_id"] = -2
        self.assertEqual(owner.manager_uids(-1), (11,))
        self.assertEqual(fresh.manager_uids(-2), (11,))
        self.assertTrue(fresh.consistent())
        self.assertEqual(
            json.loads(json.dumps(copied[1])),
            {"11": {"uid": 11, "manager_id": -2, "target_id": -1}},
        )

    def test_deepcopy_detached_rows_preserves_replaced_and_deleted_aliases(self):
        for deleted in (False, True):
            with self.subTest(deleted=deleted):
                owner = RetainedCollections()
                self.install(owner, 11, -1)
                old = owner.records[11]
                if deleted:
                    del owner.records[11]
                else:
                    owner.records.install_owned(11, dict(uid=11, manager_id=-2))
                fresh, detached = deepcopy((owner, old))
                self.assertIs(detached.owner, fresh)
                self.assertEqual(detached["manager_id"], -1)
                self.assertIsNot(detached, fresh.records.get(11))
                self.assertEqual(11 in fresh.records, not deleted)

    def test_order_extra_and_duplicates_are_not_certified(self):
        owner = RetainedCollections()
        self.install(owner, 11, -1)
        owner.order.append(12)
        self.assertFalse(owner.consistent())
        owner.order.remove(12)
        self.assertTrue(owner.consistent())
        owner.order.append(11)
        self.assertFalse(owner.consistent())

    def test_opaque_uid_comparison_is_not_invoked_by_row_gateway(self):
        class Opaque:
            def __eq__(self, other):
                raise AssertionError("Opaque comparison invoked")

        owner = RetainedCollections()
        self.install(owner, 11, -1)
        owner.records[11]["uid"] = Opaque()
        self.assertFalse(owner.consistent())

    def test_opaque_key_insert_performs_no_extra_hash_for_routing(self):
        class Key:
            calls = 0

            def __hash__(self):
                self.calls += 1
                return 99

        owner = RetainedCollections()
        key = Key()
        owner.sources["owned_stat_effects"][key] = {}
        self.assertEqual(key.calls, 1)
        self.assertFalse(owner.consistent())
        self.assertEqual(key.calls, 1)

    def test_native_replacement_keeps_rows_and_detached_map_is_inert(self):
        owner = RetainedCollections()
        self.install(owner, 11, -1)
        fight = SimpleNamespace(
            native_retained_records=owner.records, actors=owner.actors, **owner.sources
        )
        old = owner.sources["owned_stat_effects"]
        row = old[11]
        new = replace_collection(fight, "owned_stat_effects", dict(old))
        self.assertIs(new[11], row)
        old.clear()
        self.assertTrue(owner.consistent())
        self.assertEqual(tuple(owner.source_uids("owned_stat_effects")), (11,))

    def test_codec_restore_rebinds_exact_tagged_instances_without_alias_loss(self):
        fields = {
            "native_retained_records": "records",
            "actors": "actors",
            **{name: name for name in SOURCE_NAMES},
        }
        fight = SimpleNamespace(
            **{field: OwnedMap(None, name) for field, name in fields.items()}
        )
        fight.native_retained_order = OwnedOrder(None)
        row = TrackedRow(None, 11, dict(uid=11, manager_id=-1))
        dict.__setitem__(fight.native_retained_records, 11, row)
        dict.__setitem__(fight.owned_stat_effects, 11, {"payload": "00"})
        list.append(fight.native_retained_order, 11)
        original = fight.native_retained_records
        owner = restore_collections(fight)
        self.assertIs(owner.records, original)
        self.assertIs(owner.records[11], row)
        self.assertIs(row.owner, owner)
        self.assertTrue(owner.consistent())
        self.assertEqual(owner.manager_uids(-1), (11,))

    def test_actor_and_source_replacement_do_not_scan_other_collections(self):
        owner = RetainedCollections()
        self.install(owner, 11, -1)
        self.install(owner, 12, -1)
        fight = SimpleNamespace(
            native_retained_records=owner.records, actors=owner.actors, **owner.sources
        )
        protected = [owner.records, owner.sources["native_owned_group_effects"]]

        def checked_iteration(mapping):
            if any(mapping is current for current in protected):
                raise AssertionError("Unrelated collection was scanned")
            return dict.__iter__(mapping)

        with patch.object(OwnedMap, "__iter__", checked_iteration):
            replace_collection(fight, "actors", {-1: object()})
            source = owner.sources["owned_stat_effects"]
            replace_collection(
                fight, "owned_stat_effects", {12: source[12], 11: source[11]}
            )
            self.assertEqual(
                owner.source_uids("owned_stat_effects", {11, 12}), (12, 11)
            )
            self.assertTrue(owner.consistent())
            self.assertEqual(owner.manager_uids(-1), (11, 12))


if __name__ == "__main__":
    unittest.main()
