"""Immutable admission authority for Rushu's reconstructed cycle ordering."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from postgres_case import PostgresCase


class EncounterTurnEndOrderAuthorityTests(PostgresCase):
    def test_exact_admission_freeze_actor_cycle_guards_and_active_switch(self):
        from wakfu_server import combat_encounter_turn_end_order as order
        from wakfu_server import combat_encounter_roles as roles

        for module in (order, roles):
            module._version.cache_clear()
            self.addCleanup(module._version.cache_clear)
            self.enterContext(
                patch.object(module, "_database", return_value=self.store)
            )
        policy = "wakemu-rushu-cycle-regeneration-before-end-v1"
        with self.store.connection() as db:
            version = db.execute(
                "SELECT * FROM encounter_turn_end_order_versions WHERE policy=%s",
                (policy,),
            ).fetchone()
        self.assertIsNotNone(version)
        self.enterContext(
            patch(
                "wakfu_server.native_catalog.release",
                return_value=version["catalog_revision"],
            )
        )
        assigned = roles.role_assignment(1332, [5306])
        boss = SimpleNamespace(id=-200, controlled=False, team=assigned.npc_team)
        player = SimpleNamespace(id=7, controlled=True, team=assigned.player_team)

        def fresh(selected=assigned):
            return SimpleNamespace(
                phase="placement",
                actors={-200: boss, 7: player},
                current=boss,
                native_encounter_roles=selected.record(),
                native_table_turn=5,
                native_npc_initialization_receipts={
                    -200: dict(
                        ref=5306,
                        initialized=True,
                        resolved_states=[dict(state_id=7000)],
                    )
                },
            )

        fight = fresh()
        saved = order.freeze_turn_end_order_policy(fight, roles=assigned)
        self.assertEqual(saved["policy"], policy)
        self.assertEqual(saved["event_ids"], [1037, 1002])
        fight.phase = "active"
        for table in (5, 10, 15, 20):
            fight.native_table_turn = table
            self.assertEqual(
                order.turn_end_event_order(fight, actor_id=-200), (1037, 1002)
            )
            self.assertEqual(
                order.turn_end_event_order(fight, actor_id=7), (1002, 1037)
            )
        for table in (0, 1, 4, 6, 19, 21):
            fight.native_table_turn = table
            self.assertEqual(
                order.turn_end_event_order(fight, actor_id=-200), (1002, 1037)
            )
        fight.native_table_turn = 5
        fight.current = player
        with self.assertRaisesRegex(ValueError, "owned native boss"):
            order.turn_end_event_order(fight, actor_id=-200)
        fight.current = boss
        fight.native_npc_initialization_receipts[-200]["resolved_states"] = []
        with self.assertRaisesRegex(ValueError, "owned native boss"):
            order.turn_end_event_order(fight, actor_id=-200)
        fight.native_npc_initialization_receipts[-200]["resolved_states"] = [
            dict(state_id=7000)
        ]
        # Strict frozen validation cannot be bypassed by changing plain fields.
        corrupted = deepcopy(saved)
        corrupted["event_ids"] = [1002, 1037]
        with self.assertRaises(ValueError):
            order.order_policy_from_record(corrupted)
        returned = order.order_policy_from_record(saved)
        returned["table_turns"].append(21)
        self.assertNotIn(21, order.order_policy_from_record(saved)["table_turns"])
        for map_id, refs in ((1332, [5306, 5306]), (1332, [5664]), (1435, [5306])):
            other = roles.role_assignment(map_id, refs)
            candidate = fresh(other)
            self.assertIsNone(
                order.freeze_turn_end_order_policy(candidate, roles=other)
            )
            self.assertIsNone(candidate.native_turn_end_order_policy)
        # Absence is also an admission decision. Activating a policy later
        # must not opt an already admitted fight into that new behavior.
        with self.store.connection() as db:
            db.execute("DELETE FROM encounter_turn_end_order_active WHERE map_id=1332")
        pinned_none = fresh()
        self.assertIsNone(
            order.freeze_turn_end_order_policy(pinned_none, roles=assigned)
        )
        self.assertIsNone(pinned_none.native_turn_end_order_policy)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_turn_end_order_active VALUES(1332,ARRAY[5306],%s)",
                (policy,),
            )
        with patch.object(
            order, "_database", side_effect=AssertionError("admission requery")
        ):
            self.assertIsNone(
                order.freeze_turn_end_order_policy(pinned_none, roles=assigned)
            )
        pinned_none.phase = "active"
        self.assertEqual(
            order.turn_end_event_order(pinned_none, actor_id=-200), (1002, 1037)
        )
        with self.assertRaisesRegex(psycopg.Error, "immutable"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE encounter_turn_end_order_versions SET event_ids=ARRAY[1002,1037] "
                    "WHERE policy=%s",
                    (policy,),
                )
        # A new active version affects only new admissions, never a committed
        # record or legacy fight that has no version authority.
        next_policy = "test-next-rushu-end-order"
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_turn_end_order_versions "
                "SELECT %s,authority,catalog_revision,map_id,monster_references,boss_reference,"
                "boss_constructor_state,table_turns,ARRAY[1002,1037] "
                "FROM encounter_turn_end_order_versions WHERE policy=%s",
                (next_policy, policy),
            )
            db.execute(
                "UPDATE encounter_turn_end_order_active SET policy=%s WHERE map_id=1332",
                (next_policy,),
            )
        newer = fresh()
        order.freeze_turn_end_order_policy(newer, roles=assigned)
        newer.phase = "active"
        self.assertEqual(order.turn_end_event_order(newer, actor_id=-200), (1002, 1037))
        order._version.cache_clear()
        self.assertEqual(order.turn_end_event_order(fight, actor_id=-200), (1037, 1002))
        # Warm immutable lookup does not consult the changed active pointer.
        with patch.object(
            order, "_database", side_effect=AssertionError("condition-time DB query")
        ):
            self.assertEqual(
                order.turn_end_event_order(fight, actor_id=-200), (1037, 1002)
            )
            self.assertEqual(
                order.turn_end_event_order(SimpleNamespace(), actor_id=-200),
                (1002, 1037),
            )
