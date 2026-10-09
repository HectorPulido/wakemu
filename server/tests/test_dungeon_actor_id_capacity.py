"""Expanded room identities never overlap old or new sequence allocations."""
from pathlib import Path
from postgres_case import PostgresCase
from wakfu_server.maps.dungeon_capacity import (
    DUNGEON_ACTOR_ID_STRIDE,
    MAX_DUNGEON_MONSTERS,
)


class DungeonActorIdCapacityTests(PostgresCase):
    def test_migrated_sequence_reserves_disjoint_actor_blocks(self):
        with self.store.connection() as db:

            def allocate():
                return db.execute(
                    "SELECT nextval('dungeon_room_group_ids') AS id"
                ).fetchone()["id"]

            first, second = allocate(), allocate()
            self.assertEqual(second - first, DUNGEON_ACTOR_ID_STRIDE)
            self.assertFalse(
                set(range(first, first + MAX_DUNGEON_MONSTERS))
                & set(range(second, second + MAX_DUNGEON_MONSTERS))
            )

    def test_upgrade_advances_beyond_previous_eight_actor_block(self):
        with self.store.connection() as db:
            db.execute("ALTER SEQUENCE dungeon_room_group_ids INCREMENT BY 8")
            legacy = db.execute(
                "SELECT nextval('dungeon_room_group_ids') AS id"
            ).fetchone()["id"]
            migration = (
                Path(__file__).resolve().parents[1]
                / "migrations/076_dungeon_actor_id_capacity.sql"
            )
            db.execute(migration.read_text())
            current = db.execute(
                "SELECT nextval('dungeon_room_group_ids') AS id"
            ).fetchone()["id"]
            self.assertEqual(current - legacy, DUNGEON_ACTOR_ID_STRIDE)
            self.assertFalse(
                set(range(legacy, legacy + 8))
                & set(range(current, current + MAX_DUNGEON_MONSTERS))
            )
