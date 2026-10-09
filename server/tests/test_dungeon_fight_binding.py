"""Dungeon encounter admission distinguishes room groups from ordinary fights."""
from unittest import TestCase
from unittest.mock import Mock, patch
from wakfu_server.maps.dungeon_fight_binding import bind_room_group


class DungeonFightBindingTests(TestCase):
    def db(self, *rows):
        db = Mock()
        db.execute.side_effect = [Mock(fetchone=Mock(return_value=row)) for row in rows]
        return db

    def test_ordinary_world_does_not_query_dungeon_tables(self):
        db = self.db()
        self.assertIsNone(bind_room_group(db, (527, 0, 5), 1, 2))
        db.execute.assert_not_called()

    def test_non_dungeon_instance_retains_ordinary_behavior(self):
        self.assertIsNone(bind_room_group(self.db(None), (527, 88, 5), 1, 2))

    def test_current_receipt_binds_durable_participant(self):
        db = self.db(
            dict(party_id=9, current_room=2, status="active"),
            dict(asset_map_id=1086, group_id=5),
        )
        with patch(
            "wakfu_server.maps.dungeon_fight_binding.reconcile_aborted_encounters"
        ) as reconcile, patch(
            "wakfu_server.maps.dungeon_fight_binding.bind_encounter",
            return_value={"fight_id": 2},
        ) as bind:
            self.assertEqual(bind_room_group(db, (1086, 88, 5), 1, 2), {"fight_id": 2})
            reconcile.assert_called_once_with(db, instance_id=88)
            bind.assert_called_once_with(db, 88, 9, 1, 2, player_team=0)

    def test_incidental_or_previous_room_group_is_rejected(self):
        for receipt in (
            None,
            dict(asset_map_id=1085, group_id=5),
            dict(asset_map_id=1086, group_id=4),
        ):
            with self.subTest(receipt=receipt):
                db = self.db(dict(party_id=9, current_room=2, status="active"), receipt)
                with self.assertRaisesRegex(ValueError, "current dungeon room"):
                    bind_room_group(db, (1086, 88, 5), 1, 2)

    def test_completed_run_cannot_start_another_encounter(self):
        with self.assertRaisesRegex(ValueError, "not active"):
            bind_room_group(self.db(dict(status="completed")), (1086, 88, 5), 1, 2)

    def test_group_identity_rejects_boolean_or_incomplete_values(self):
        for key in ((1086, True, 5), (1086, 88), [1086, 88, 5]):
            with self.subTest(key=key), self.assertRaises(ValueError):
                bind_room_group(self.db(), key, 1, 2)


class DungeonAbortedEncounterTests(TestCase):
    db = DungeonFightBindingTests.db

    def test_ordinary_fight_has_no_dungeon_cleanup(self):
        from wakfu_server.maps.dungeon_fight_binding import abort_room_encounter

        self.assertIsNone(abort_room_encounter(self.db(None), 5))

    def test_live_fight_cannot_release_encounter(self):
        from wakfu_server.maps.dungeon_fight_binding import abort_room_encounter

        with self.assertRaisesRegex(ValueError, "aborted durable"):
            abort_room_encounter(
                self.db(dict(instance_id=88), dict(status="active")), 5
            )

    def test_aborted_receipt_replay_preserves_result(self):
        from wakfu_server.maps.dungeon_fight_binding import abort_room_encounter

        db = self.db(
            dict(instance_id=88),
            dict(status="aborted"),
            {},
            dict(status="aborted", result=dict(current_room=2, revision=3)),
        )
        self.assertEqual(
            abort_room_encounter(db, 5), dict(current_room=2, revision=3, replay=True)
        )
