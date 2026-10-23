"""Character hydration reads durable consumables in AI read-only snapshots."""
from psycopg.errors import ReadOnlySqlTransaction
from psycopg.types.json import Jsonb
from unittest.mock import patch

from postgres_case import PostgresCase


class StoreConsumableReadonlyTests(PostgresCase):
    def test_character_hydrates_all_clock_kinds_without_writes_in_readonly_tx(self):
        account = self.store.register("readonly-food", "local-password")["id"]
        character = self.store.create_character(account, "Readonly Food")
        self.store.clock = lambda: 10.0

        states = (
            (7001, 1, "wall", 20_000, 15_000, None, None, None),
            (7002, 2, "online", 30_000, 7_000, None, "old-generation", 2_000),
            (7003, 3, "event", 0, 0, None, None, None),
            (7004, 4, "wall", 20_000, 9_000, None, None, None),
            (7005, 5, "wall", 20_000, 9_000, 77, None, None),
        )
        with self.store.connection() as db:
            for (
                state_id,
                item_ref,
                clock,
                duration,
                expires,
                combat_id,
                generation,
                anchor,
            ) in states:
                db.execute(
                    "INSERT INTO character_consumable_buffs "
                    "(character_id,state_id,level,source_item_ref,source_item_uid,clock,"
                    "duration_ms,remaining_ms,expires_ms,online_generation,online_anchor_ms,"
                    "combat_id,metadata) VALUES (%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        character["id"],
                        state_id,
                        item_ref,
                        8000 + item_ref,
                        clock,
                        duration,
                        expires if clock == "online" else 0,
                        expires if clock == "wall" else None,
                        generation,
                        anchor,
                        combat_id,
                        Jsonb({"metadata": {"fixture": True}}),
                    ),
                )
            before = db.execute(
                "SELECT uid,state_id,remaining_ms,expires_ms,online_generation,"
                "online_anchor_ms,combat_id FROM character_consumable_buffs "
                "WHERE character_id=%s ORDER BY state_id",
                (character["id"],),
            ).fetchall()

        # Reproduce the old FOR UPDATE hydration path without allowing any write.
        # It must fail under PostgreSQL's read-only guarantee, proving the test
        # would catch the AI turn regression that motivated this change.
        with self.store.connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            with patch(
                "wakfu_server.consumable_buffs.hydrated_states",
                side_effect=lambda store, tx, owner: __import__(
                    "wakfu_server.consumable_buffs", fromlist=["active_states"]
                ).active_states(store, tx, owner, generation=None, now_ms=10_000),
            ):
                with self.assertRaises(ReadOnlySqlTransaction):
                    self.store.character(account, character["id"], db)

        with self.store.connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            hydrated = self.store.character(account, character["id"], db)
            self.assertEqual(
                [
                    (row["state_id"], row["remaining_ms"])
                    for row in hydrated["consumable_states"]
                ],
                [(7001, 5_000), (7002, 7_000), (7003, 0), (7005, 1)],
            )
            after = db.execute(
                "SELECT uid,state_id,remaining_ms,expires_ms,online_generation,"
                "online_anchor_ms,combat_id FROM character_consumable_buffs "
                "WHERE character_id=%s ORDER BY state_id",
                (character["id"],),
            ).fetchall()
            self.assertEqual(after, before)
