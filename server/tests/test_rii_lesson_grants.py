import unittest
from unittest.mock import patch

import test_combat_maximum_resource as maximum_fixture
from wakfu_server import rii_lesson_grants
from wakfu_server.combat_spell_grant import granted_spells


class RiiLessonGrantTests(unittest.TestCase):
    def setUp(self):
        fixture = maximum_fixture.MaximumResourceTests()
        fixture.setUp()
        self.fight = fixture.fight
        self.fight.rii_element_lesson_contract = {"owner": 7, "target": -2}
        self.packets = []
        self.uid = 1000
        references = rii_lesson_grants.SPELLS + (7967, 7968, 7969, 7970, 7971)
        self.refs = patch(
            "wakfu_server.combat_spell_grant.native_spell_references",
            return_value=frozenset(references),
        )
        self.casting = patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={str(i): {"maximum_level": 200} for i in references},
        )
        self.metadata = patch(
            "wakfu_server.combat_retained_runtime.native_retained_metadata",
            return_value={
                "effects": {
                    "347172": {
                        "effect_class": 649,
                        "definition_type": 2,
                        "definition_dispellable": False,
                        "subscription": False,
                    }
                }
            },
        )
        self.refs.start()
        self.casting.start()
        self.metadata.start()
        self.addCleanup(self.refs.stop)
        self.addCleanup(self.casting.stop)
        self.addCleanup(self.metadata.stop)

    def allocate(self):
        self.uid += 1
        return self.uid

    def test_install_and_remove_only_temporary_grants(self):
        uids = rii_lesson_grants.install(
            self.fight, 7, self.packets, action_id=1, allocate_uid=self.allocate
        )
        self.assertEqual(
            set(granted_spells(self.fight, 7)), set(rii_lesson_grants.SPELLS)
        )
        self.assertEqual(set(self.fight.native_retained_records), set(uids))
        self.assertEqual(set(self.fight.native_retained_order), set(uids))
        self.assertEqual([packet[0] for packet in self.packets], [12613] * 4)
        rii_lesson_grants.remove(self.fight, 7, uids, self.packets, action_id=1)
        self.assertFalse(granted_spells(self.fight, 7))
        self.assertFalse(self.fight.native_retained_records)
        self.assertFalse(self.fight.native_retained_order)
        self.assertEqual(
            [packet[0] for packet in self.packets], [12613] * 4 + [13560] * 4
        )

    def test_other_owner_cannot_install_or_remove(self):
        with self.assertRaises(ValueError):
            rii_lesson_grants.install(
                self.fight, 8, self.packets, action_id=1, allocate_uid=self.allocate
            )
        uids = rii_lesson_grants.install(
            self.fight, 7, self.packets, action_id=1, allocate_uid=self.allocate
        )
        with self.assertRaises(ValueError):
            rii_lesson_grants.remove(self.fight, 8, uids, self.packets, action_id=1)
        self.assertEqual(
            set(granted_spells(self.fight, 7)), set(rii_lesson_grants.SPELLS)
        )

    def test_only_owner_can_cast_grant_and_it_expires_after_removal(self):
        from wakfu_server.combat_cast import resolve_owned_spell_action

        uids = rii_lesson_grants.install(
            self.fight, 7, self.packets, action_id=1, allocate_uid=self.allocate
        )
        request = {"actor_id": 7, "spell_uid": 7963}
        with patch(
            "wakfu_server.combat_cast.validate_deck",
            side_effect=AssertionError("saved deck"),
        ):
            actor, reference, _ = resolve_owned_spell_action(
                request, {"id": 7}, self.fight, 3, b""
            )
            self.assertEqual((actor.id, reference), (7, 7963))
            with self.assertRaises(ValueError):
                resolve_owned_spell_action(request, {"id": 7}, self.fight, 4, b"")
            rii_lesson_grants.remove(self.fight, 7, uids, self.packets, action_id=1)
            with self.assertRaises(ValueError):
                resolve_owned_spell_action(request, {"id": 7}, self.fight, 3, b"")

    def test_already_expired_grant_cleanup_remains_idempotent(self):
        uids = rii_lesson_grants.install(
            self.fight, 7, self.packets, action_id=1, allocate_uid=self.allocate
        )
        rii_lesson_grants.remove(self.fight, 7, uids, self.packets, action_id=1)
        count = len(self.packets)
        rii_lesson_grants.remove(self.fight, 7, uids, self.packets, action_id=1)
        self.assertEqual(len(self.packets), count)

    def test_retained_runtime_accepts_carriers_before_and_after_removal(self):
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime

        uids = rii_lesson_grants.install(
            self.fight, 7, self.packets, action_id=1, allocate_uid=self.allocate
        )

        def retained():
            return NativeRetainedRuntime(
                self.fight,
                [],
                plan={"native_retained_container": {"present": False}},
                state_catalog={},
                action_id=2,
                timing=None,
                metadata={},
            )

        retained()
        rii_lesson_grants.remove(self.fight, 7, uids, self.packets, action_id=2)
        retained()

    def test_distance_grant_is_owner_scoped_and_cannot_remove_element_grants(self):
        self.fight.rii_distance_lesson_contract = {"owner": 7, "target": -2}
        uids = rii_lesson_grants.install(
            self.fight,
            7,
            self.packets,
            action_id=1,
            allocate_uid=self.allocate,
            lesson="distance",
        )
        self.assertEqual(set(granted_spells(self.fight, 7)), {7967})
        with self.assertRaises(ValueError):
            rii_lesson_grants.remove(self.fight, 7, uids, self.packets, action_id=1)
        rii_lesson_grants.remove(
            self.fight, 7, uids, self.packets, action_id=1, lesson="distance"
        )
        self.assertFalse(granted_spells(self.fight, 7))

    def test_los_grant_is_owned_and_removed_on_terminal_path(self):
        self.fight.rii_los_lesson_contract = {"owner": 7, "target": -2}
        uids = rii_lesson_grants.install(
            self.fight,
            7,
            self.packets,
            action_id=1,
            allocate_uid=self.allocate,
            lesson="los",
        )
        self.assertEqual(set(granted_spells(self.fight, 7)), {7968})
        self.fight.rii_los_lesson_contract.update(initialized=True, grant_uids=uids)
        self.assertFalse(
            rii_lesson_grants.remove_los_if_present(
                self.fight, self.packets, action_id=2, owner_ids={8}
            )
        )
        self.assertTrue(
            rii_lesson_grants.remove_los_if_present(
                self.fight, self.packets, action_id=2, owner_ids={7}
            )
        )
        self.assertFalse(granted_spells(self.fight, 7))

    def test_area_grants_are_owned_and_cleaned_without_touching_other_lessons(self):
        self.fight.rii_area_lesson_contract = {"owner": 7, "targets": [-2, -3, -4, -5]}
        uids = rii_lesson_grants.install(
            self.fight,
            7,
            self.packets,
            action_id=1,
            allocate_uid=self.allocate,
            lesson="area",
        )
        self.assertEqual(set(granted_spells(self.fight, 7)), {7969, 7970, 7971})
        with self.assertRaises(ValueError):
            rii_lesson_grants.remove(
                self.fight, 8, uids, self.packets, action_id=1, lesson="area"
            )
        with self.assertRaises(ValueError):
            rii_lesson_grants.remove(
                self.fight, 7, uids, self.packets, action_id=1, lesson="distance"
            )
        self.fight.rii_area_lesson_contract.update(initialized=True, grant_uids=uids)
        self.assertTrue(
            rii_lesson_grants.remove_area_if_present(
                self.fight, self.packets, action_id=1
            )
        )
        self.assertFalse(granted_spells(self.fight, 7))
        self.assertFalse(self.fight.native_retained_records)

    def test_reconnect_retains_exact_four_grants_without_duplicate_projection(self):
        from wakfu_server.combat_reconnect_grants import ReconnectGrantProjection
        from wakfu_server.combat_remote_effects import (
            RemoteRunningEffect,
            encode_remote_effects,
            decode_remote_effects,
        )

        uids = rii_lesson_grants.install(
            self.fight, 7, self.packets, action_id=1, allocate_uid=self.allocate
        )
        effects = encode_remote_effects(
            tuple(
                RemoteRunningEffect(
                    649, bytes.fromhex(self.fight.owned_stat_effects[uid]["payload"]), 0
                )
                for uid in uids
            )
        )
        projection = ReconnectGrantProjection(self.packets)
        self.assertEqual(decode_remote_effects(projection.effects(7, effects)), ())
        projection.verify_complete()
        self.assertEqual(
            decode_remote_effects(projection.effects(7, effects, final=True)), ()
        )
        projection.verify_complete(final=True)
        self.assertEqual(len(projection.grant_carriers), 4)


if __name__ == "__main__":
    unittest.main()
