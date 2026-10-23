"""Durable connected-time snapshots cannot mutate combat or session clocks."""
from types import SimpleNamespace
from postgres_case import PostgresCase
from test_consumable_session_lifecycle import ConsumableSessionLifecycleTests


class ConsumableCombatSnapshotTests(PostgresCase):
    fixture = ConsumableSessionLifecycleTests.fixture
    rows = ConsumableSessionLifecycleTests.rows

    def test_reconnect_snapshot_uses_paused_clock_without_live_or_sql_mutation(self):
        from wakfu_server.consumable_buffs import enter_combat
        from wakfu_server.consumable_combat_snapshot import online_snapshot_view
        from wakfu_server.combat_state_ledger import StateLedger, RunningState

        account, generation, main, _hero = self.fixture()
        with self.store.connection() as db:
            row = enter_combat(self.store, db, main["id"], 77, generation=generation)[0]
        ledger = StateLedger(main["id"])
        ledger._entries = (
            RunningState(
                uid=9001,
                reference=row["state_id"],
                level=row["level"],
                caster_id=main["id"],
                target_id=main["id"],
                duration=-1,
                clock_actor="target",
                tick_at_turn_end=False,
                effect_ids=(),
                realtime_duration=row["duration_ms"],
                retained=True,
                timer=None,
                realtime_deadline_ms=1900000,
                realtime_in_combat=True,
            ),
        )
        actor = SimpleNamespace(
            id=main["id"], owner_id=account, controlled=True, state_ledger=ledger
        )
        fight = SimpleNamespace(
            id=77,
            actors={main["id"]: actor},
            native_consumable_initializations={
                main["id"]: (
                    {
                        "world_uid": row["uid"],
                        "combat_uid": 9001,
                        "state_id": row["state_id"],
                        "clock": "online",
                    },
                )
            },
        )
        self.store.clock = lambda: 1002
        self.store.clear_character(account, generation)
        self.store.clock = lambda: 10000
        before = self.rows(account)
        old_entry = ledger.entries[0]
        view = online_snapshot_view(self.store, fight, main["id"], now_ms=10000000)
        self.assertEqual(
            view.actors[main["id"]].state_ledger.entries[0].realtime_deadline_ms,
            10898000,
        )
        self.assertIs(fight.actors[main["id"]].state_ledger.entries[0], old_entry)
        self.assertEqual(self.rows(account), before)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        from wakfu_server.consumable_world_lifecycle import synchronize

        synchronize(
            self.store,
            account,
            generation,
            self.store.character(account, main["id"]),
            mode="resume",
        )
        self.store.clock = lambda: 10003
        before = self.rows(account)
        view = online_snapshot_view(self.store, fight, main["id"], now_ms=10003000)
        self.assertEqual(
            view.actors[main["id"]].state_ledger.entries[0].realtime_deadline_ms,
            10898000,
        )
        self.assertEqual(self.rows(account), before)
        self.assertIs(fight.actors[main["id"]].state_ledger.entries[0], old_entry)
        fight.native_consumable_initializations[main["id"]][0]["world_uid"] += 10000
        with self.assertRaisesRegex(
            ValueError, "durable consumable snapshot authority"
        ):
            online_snapshot_view(self.store, fight, main["id"], now_ms=10003000)
