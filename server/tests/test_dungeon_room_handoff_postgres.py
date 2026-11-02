"""Real nested-savepoint recovery with the production durable group adapter."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import psycopg
from psycopg.rows import dict_row

from wakfu_server import dungeon_room_handoff, dungeon_runtime


@unittest.skipUnless(
    os.environ.get("WAKFU_POSTGRES_TEST_URL"), "Isolated PostgreSQL required"
)
class RoomHandoffPostgresTests(unittest.TestCase):
    def test_partial_group_rollback_preserves_committed_win_then_registers_once(self):
        from postgres_case import isolated_test_url
        from wakfu_server.combat_group_store import PersistentGroups

        options = dict(row_factory=dict_row)
        password = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        if password:
            options["password"] = Path(password).read_text().strip()
        with psycopg.connect(isolated_test_url(), **options) as db:
            # Session-local tables avoid migrations, source data or runtime rows.
            for statement in (
                "CREATE TEMP TABLE dungeon_room_runs(instance_id bigint PRIMARY KEY,current_room integer,status text,revision integer)",
                "CREATE TEMP TABLE dungeon_room_encounters(instance_id bigint,fight_id bigint,status text,encounter_scope text,result_revision integer,result jsonb)",
                "CREATE TEMP TABLE npc_actor_identity_aliases(map_id integer,instance_id bigint,group_id bigint,old_actor_id bigint,new_actor_id bigint)",
                "CREATE TEMP TABLE combat_groups(map_id integer,instance_id bigint,group_id bigint,members jsonb,status text,PRIMARY KEY(map_id,instance_id,group_id))",
                "CREATE TEMP TABLE combat_group_members(map_id integer,instance_id bigint,monster_id bigint,group_id bigint,PRIMARY KEY(map_id,instance_id,monster_id))",
                "CREATE TEMP TABLE dungeon_room_spawn_receipts(instance_id bigint,room_order integer,asset_map_id integer,group_id bigint)",
                "CREATE TEMP TABLE earned_reward(amount integer)",
            ):
                db.execute(statement)
            db.execute("INSERT INTO dungeon_room_runs VALUES(31,2,'active',7)")
            result = dict(victory=True, completed=False, current_room=2, revision=7)
            db.execute(
                "INSERT INTO dungeon_room_encounters VALUES(31,91,'victory','main',7,%s::jsonb)",
                (json.dumps(result),),
            )
            db.execute("INSERT INTO earned_reward VALUES(100)")
            db.commit()

            @contextmanager
            def connection():
                yield db

            groups = PersistentGroups(SimpleNamespace(connection=connection))
            members = [
                dict(
                    id=-200,
                    ref=5525,
                    level=1,
                    map_id=1134,
                    x=-7,
                    y=-7,
                    z=-1,
                    instance_id=31,
                )
            ]

            def hydrate(*args, fail=False):
                # Wire appearance/catalog publication is independent of this
                # transaction test. Keep actual group ownership validation and
                # production registration SQL, inject only encoded appearance.
                with patch(
                    "wakfu_server.combat_monster_world.world_actor",
                    return_value=b"fixture",
                ):
                    groups.register_transaction(db, 1134, 31, 501, members)
                db.execute(
                    "INSERT INTO dungeon_room_spawn_receipts VALUES(31,2,1134,501)"
                )
                if fail:
                    raise ValueError("Spawn publication is temporarily incomplete")

            def prepare(now):
                return dungeon_room_handoff.prepare(
                    db,
                    groups,
                    instance_id=31,
                    fight_id=91,
                    map_id=1134,
                    geometry_provider=lambda identity: {},
                    now=now,
                )

            with patch.object(
                dungeon_runtime,
                "ensure_current_room",
                side_effect=lambda *args: hydrate(*args, fail=True),
            ):
                self.assertFalse(prepare(100)["ready"])
            db.commit()
            for table in (
                "combat_groups",
                "combat_group_members",
                "dungeon_room_spawn_receipts",
            ):
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"], 0
                )
            self.assertEqual(
                db.execute(
                    "SELECT sum(amount) AS amount FROM earned_reward"
                ).fetchone()["amount"],
                100,
            )
            receipt = db.execute(
                "SELECT result FROM dungeon_room_encounters"
            ).fetchone()["result"]
            self.assertTrue(receipt["victory"])
            self.assertEqual(receipt["room_hydration"]["state"], "pending")
            # PersistentGroups has no in-memory roster cache to survive rollback.
            self.assertNotIn("groups", vars(groups))
            with patch.object(
                dungeon_runtime, "ensure_current_room", side_effect=hydrate
            ) as spawn:
                self.assertTrue(prepare(102)["ready"])
                self.assertTrue(prepare(103)["ready"])
                spawn.assert_called_once()
            db.commit()
            for table in (
                "combat_groups",
                "combat_group_members",
                "dungeon_room_spawn_receipts",
            ):
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"], 1
                )
            self.assertEqual(
                db.execute(
                    "SELECT sum(amount) AS amount FROM earned_reward"
                ).fetchone()["amount"],
                100,
            )


if __name__ == "__main__":
    unittest.main()
