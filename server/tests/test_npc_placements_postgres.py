"""Fresh migration seed, dynamic dialogue exclusion and idempotent SQL gate."""
import os
from pathlib import Path

from postgres_case import PostgresCase
from wakfu_server.maps import npc_placements
from wakfu_server.storage.postgres import migrate
from test_npc_placements import EXPECTED


class NpcPlacementsPostgresTests(PostgresCase):
    def test_ten_source_positions_five_dynamic_exclusions_and_repeat_migrate(self):
        with self.store.connection() as db:
            stored = db.execute(
                "SELECT actor_id,reference_id,map_id,instance_id,x,y,z,direction,name_es,visual_id,level,native_action_ids,source_sha256,source_frame "
                "FROM world_native_npc_placements ORDER BY actor_id"
            ).fetchall()
            self.assertEqual(len(stored), 10)
            actual = {
                row["actor_id"]: tuple(
                    row[key]
                    for key in (
                        "reference_id",
                        "map_id",
                        "instance_id",
                        "x",
                        "y",
                        "z",
                        "direction",
                        "name_es",
                        "visual_id",
                        "level",
                        "native_action_ids",
                        "source_sha256",
                        "source_frame",
                    )
                )
                for row in stored
            }
            expected = {
                row["actor_id"]: tuple(
                    row[key]
                    for key in (
                        "reference_id",
                        "map_id",
                        "instance_id",
                        "x",
                        "y",
                        "z",
                        "direction",
                        "name_es",
                        "visual_id",
                        "level",
                        "native_action_ids",
                        "source_sha256",
                        "source_frame",
                    )
                )
                for row in (dict(row, instance_id=0) for row in EXPECTED)
            }
            self.assertEqual(actual, expected)

            all_ids = tuple(expected)
            existing = db.execute(
                "SELECT actor_id FROM world_dialogue_npcs WHERE actor_id=ANY(%s)",
                (list(all_ids),),
            ).fetchall()
            dialogue_ids = {row["actor_id"] for row in existing}
            expected_dialogue = {row["actor_id"] for row in EXPECTED[:5]}
            self.assertEqual(dialogue_ids, expected_dialogue)

            columns = {
                row["column_name"]
                for row in db.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema=current_schema() AND table_name='world_native_npc_placements'"
                ).fetchall()
            }
            self.assertNotIn("dialogue_root", columns)
            self.assertNotIn("action_ids", columns)

            by_map = {}
            for map_id in sorted({row["map_id"] for row in EXPECTED}):
                by_map.update(
                    {
                        row["actor_id"]: row
                        for row in npc_placements.load_scene(db, map_id, 0)
                    }
                )
                self.assertEqual(npc_placements.load_scene(db, map_id, 1), ())
            expected_position_only = {row["actor_id"] for row in EXPECTED[5:]}
            self.assertEqual(set(by_map), expected_position_only)
            self.assertTrue(dialogue_ids.isdisjoint(by_map))
            self.assertTrue(
                all(
                    "dialogue_root" not in row and "action_ids" not in row
                    for row in by_map.values()
                )
            )

            # Even quarantined/disabled dialogue rows keep their actor identity
            # out of the position-only loader until the dialogue row is removed.
            disabled = next(row for row in EXPECTED[:5] if row["reference_id"] == 5461)
            db.execute(
                "UPDATE world_dialogue_npcs SET enabled=false WHERE actor_id=%s",
                (disabled["actor_id"],),
            )
            self.assertNotIn(
                disabled["actor_id"],
                {
                    row["actor_id"]
                    for row in npc_placements.load_scene(db, disabled["map_id"], 0)
                },
            )

            migrations = Path(
                os.environ.get(
                    "WAKFU_MIGRATIONS_TEST_DIR",
                    Path(__file__).resolve().parents[1] / "migrations",
                )
            )
            self.assertEqual(migrate(db, migrations), 0)
            count = db.execute(
                "SELECT count(*) AS n FROM world_native_npc_placements"
            ).fetchone()["n"]
            self.assertEqual(count, 10)
