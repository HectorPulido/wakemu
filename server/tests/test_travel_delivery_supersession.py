"""Committed travel receipts cannot roll back later owned movement."""
import struct
from types import SimpleNamespace
from unittest.mock import Mock

import test_haven_world_travel_postgres as haven_fixture
import test_recustomization_and_item_teleport_postgres as item_fixture


def deliver_current_scene(case, positions, account, generation, cid, initial):
    """Use actual World hydration with real SQL and position fences; mock network IO."""
    from test_dungeon_recovery_callers import caller
    from wakfu_server import rift_transition_delivery

    case.addCleanup(
        rift_transition_delivery.supersede_recovered_sessions,
        (SimpleNamespace(account_id=account, generation=generation, character_id=cid),),
    )
    expected = case.store.character(account, cid)

    def leaving(*args):
        case.assertEqual(
            {key: expected[key] for key in ("map_id", "instance_id", "x", "y", "z")},
            {
                key: positions.entries[(account, generation, cid)]["current"][key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            },
        )

    namespace = dict(
        INITIAL_character=initial,
        INITIAL_position={key: initial[key] for key in ("x", "y", "z")},
        INITIAL_movement_state=None,
        loaded=True,
        account_id=account,
        generation=generation,
        fight=None,
        combat_session=None,
        STORE=case.store,
        POSITIONS=positions,
        consume_rift_entry_combat_retirement=Mock(),
        prepare_world_respawn_delivery=Mock(),
        cancel_crafting=Mock(),
        WORLD=Mock(leave=Mock(side_effect=leaving)),
        Movement=Mock(),
        owned_native_bootstrap=Mock(return_value=((13256, b"scene"),)),
        send=Mock(),
        connection=object(),
        service="world",
        join_world=Mock(),
        mark_static_sync_pending=Mock(),
        record=Mock(),
    )
    case.assertTrue(caller("deliver_rift_transition", namespace)())
    namespace["owned_native_bootstrap"].assert_called_once_with(expected)
    namespace["join_world"].assert_called_once_with(
        generation, namespace["connection"], expected
    )
    case.assertIsNone(rift_transition_delivery.pending(account, generation, cid))


class HavenTravelDeliverySupersessionTests(haven_fixture.HavenWorldTravelPostgresTests):
    test_entry_pending_reconnect_npc_identity_and_return_are_consistent = None

    def _entered_then_moved(self, *, read_pending):
        from wakfu_server import haven_world_travel
        from wakfu_server.haven_world_terrain import geometry

        account, generation, cid = (
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
        )
        entered = haven_world_travel.travel(
            self.store, self.positions, account, generation, cid
        )
        if read_pending:
            self.assertEqual(
                entered["transition"]["token"],
                haven_world_travel.pending(self.store, account, generation, cid)[
                    "transition"
                ]["token"],
            )
        start = {key: entered["character"][key] for key in ("x", "y", "z")}
        edge = next(
            pair
            for pair in geometry()["edges"]
            if tuple(pair[0]) == tuple(start.values())
        )
        end = dict(zip(("x", "y", "z"), edge[1]))
        self.positions.move(account, generation, cid, start, end)
        self.assertEqual(1, self.positions.flush(account_id=account))
        moved = self.store.character(account, cid)
        self.assertEqual(end, {key: moved[key] for key in end})
        return entered, moved

    def _assert_retired_without_false_delivery(self, token, moved, initial):
        from wakfu_server import haven_world_travel

        account, generation, cid = (
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT * FROM haven_world_transitions WHERE token=%s", (token,)
            ).fetchone()
            self.assertIsNone(row["delivered_at"])
            self.assertIsNotNone(row["superseded_at"])
            self.assertEqual(
                2,
                db.execute(
                    "SELECT count(*) AS n FROM haven_world_visits v JOIN characters c "
                    "ON c.id=v.character_id WHERE c.account_id=%s AND v.returned_at IS NULL",
                    (account,),
                ).fetchone()["n"],
            )
        self.assertEqual(moved, self.store.character(account, cid))
        deliver_current_scene(self, self.positions, account, generation, cid, initial)
        self.assertIsNone(
            haven_world_travel.pending(self.store, account, generation, cid)
        )
        self.assertFalse(
            haven_world_travel.acknowledge(self.store, account, generation, cid, token)
        )
        returned = haven_world_travel.travel(
            self.store, self.positions, account, generation, cid, leave=True
        )
        self.assertEqual(0, returned["character"]["instance_id"])
        self.assertFalse(
            haven_world_travel.acknowledge(self.store, account, generation, cid, token)
        )
        self.assertEqual(
            returned["transition"]["token"],
            haven_world_travel.pending(self.store, account, generation, cid)[
                "transition"
            ]["token"],
        )
        with self.assertRaises(ValueError):
            haven_world_travel.acknowledge(
                self.store, account, generation, cid, "foreign-" + token
            )
        with self.assertRaises(ValueError):
            haven_world_travel.acknowledge(
                self.store,
                account,
                generation + "-stale",
                cid,
                returned["transition"]["token"],
            )
        self.assertTrue(
            haven_world_travel.acknowledge(
                self.store, account, generation, cid, returned["transition"]["token"]
            )
        )
        for identity in (cid, self.hero["id"]):
            actual = self.store.character(account, identity)
            self.assertEqual(
                returned["transition"]["destination"],
                {key: actual[key] for key in haven_world_travel.KEYS},
            )
        self.assertEqual(
            returned["transition"]["destination"],
            {
                key: self.positions.entries[(account, generation, cid)]["current"][key]
                for key in haven_world_travel.KEYS
            },
        )
        self.store.create_character(
            account, "After Haven Recovery", selection_generation=generation
        )
        next_generation = self.store.begin_session(account)
        selected = self.store.select_character(account, next_generation, cid)
        self.assertEqual(
            returned["transition"]["destination"],
            {key: selected[key] for key in haven_world_travel.KEYS},
        )

    def test_pending_receipt_retires_after_actual_owned_movement(self):
        from wakfu_server import haven_world_travel

        entered, moved = self._entered_then_moved(read_pending=False)
        self.assertIsNone(
            haven_world_travel.pending(
                self.store,
                self.owner["account"],
                self.owner["generation"],
                self.owner["character"],
            )
        )
        self._assert_retired_without_false_delivery(
            entered["transition"]["token"], moved, entered["character"]
        )

    def test_acknowledgment_race_retires_only_original_receipt(self):
        from wakfu_server import haven_world_travel

        entered, moved = self._entered_then_moved(read_pending=True)
        self.assertFalse(
            haven_world_travel.acknowledge(
                self.store,
                self.owner["account"],
                self.owner["generation"],
                self.owner["character"],
                entered["transition"]["token"],
            )
        )
        self._assert_retired_without_false_delivery(
            entered["transition"]["token"], moved, entered["character"]
        )


class ItemTravelDeliverySupersessionTests(
    item_fixture.RecustomizationAndTeleportPostgresTests
):
    test_recustomization_keeps_identity_progress_inventory_and_build = None
    test_teleport_commits_relocation_once_and_acknowledges_retryably = None
    test_teleport_rejects_malformed_foreign_and_combat_requests_without_consuming = None

    def test_ack_race_preserves_consumption_and_allows_next_owned_travel(self):
        from wakfu_server import item_teleports
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server.dungeon_position_barrier import run_account_exit
        from wakfu_server.position_buffer import Positions

        cid = self.character["id"]
        keys = item_teleports.LOCATION_KEYS
        exterior = dict(
            map_id=552,
            instance_id=0,
            **dict(zip(("x", "y", "z"), map_geometry(552)["cells"][0]))
        )
        self.store.transition_map(
            self.account,
            self.generation,
            cid,
            {key: self.character[key] for key in keys},
            exterior,
        )
        positions = Positions(
            self.store,
            lease_active=lambda a, g, c: (a, g, c)
            == (self.account, self.generation, cid),
        )
        positions.attach(
            self.account, self.generation, self.store.character(self.account, cid)
        )
        uid = self._give(self.account, cid, 14306, 2)
        body = struct.pack(">iq", 2645, uid)
        outcome = item_teleports.use(
            self.store,
            positions,
            self.account,
            self.generation,
            cid,
            body,
            in_fight=False,
        )
        token = outcome["transition"]["token"]
        self.assertEqual(
            token,
            item_teleports.pending(self.store, self.account, self.generation, cid)[
                "transition"
            ]["token"],
        )
        run_account_exit(
            self.store,
            positions,
            self.account,
            transition=lambda: self.store.transition_map(
                self.account,
                self.generation,
                cid,
                outcome["transition"]["destination"],
                exterior,
            ),
        )
        before_ack = self.store.character(self.account, cid)
        self.assertFalse(
            item_teleports.acknowledge(
                self.store, self.account, self.generation, cid, token
            )
        )
        self.assertEqual(before_ack, self.store.character(self.account, cid))
        deliver_current_scene(
            self, positions, self.account, self.generation, cid, outcome["character"]
        )
        self.assertEqual(1, self._quantity(uid))
        with self.store.connection() as db:
            row = db.execute(
                "SELECT * FROM item_teleport_receipts WHERE token=%s", (token,)
            ).fetchone()
            self.assertIsNone(row["delivered_at"])
            self.assertIsNotNone(row["superseded_at"])
        next_outcome = item_teleports.use(
            self.store,
            positions,
            self.account,
            self.generation,
            cid,
            body,
            in_fight=False,
        )
        self.assertNotEqual(token, next_outcome["transition"]["token"])
        self.assertFalse(
            item_teleports.acknowledge(
                self.store, self.account, self.generation, cid, token
            )
        )
        self.assertEqual(
            next_outcome["transition"]["token"],
            item_teleports.pending(self.store, self.account, self.generation, cid)[
                "transition"
            ]["token"],
        )
        with self.assertRaises(ValueError):
            item_teleports.acknowledge(
                self.store, self.account, self.generation, cid, "foreign-" + token
            )
        with self.assertRaises(ValueError):
            item_teleports.acknowledge(
                self.store, self.account, self.generation + "-stale", cid, token
            )
        self.assertTrue(
            item_teleports.acknowledge(
                self.store,
                self.account,
                self.generation,
                cid,
                next_outcome["transition"]["token"],
            )
        )
        self.assertIsNone(self._quantity(uid))
