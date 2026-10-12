"""PostgreSQL regressions for ecology-admin combat roster recovery."""

from postgres_case import PostgresCase


class EcologyAdminMigrationTests(PostgresCase):
    def test_genesis_migration_adds_limits_without_changing_other_reproduction_policy(
        self,
    ):
        with self.store.connection() as db:
            reproduction = db.execute(
                "SELECT value FROM settings WHERE name='monster_reproduction'"
            ).fetchone()["value"]
            genesis = db.execute(
                "SELECT value FROM settings WHERE name='monster_genesis'"
            ).fetchone()["value"]
        self.assertEqual(reproduction["max_zone_members"], 500)
        self.assertEqual(reproduction["max_zone_groups"], 100)
        self.assertEqual(reproduction["interval_ms"], 60000)
        self.assertEqual(reproduction["birth_probability"], 0.05)
        self.assertEqual(reproduction["birth_stage_decay"], 0.5)
        self.assertEqual(reproduction["new_group_probability"], 0.5)
        self.assertEqual(reproduction["max_members"], 8)
        self.assertEqual(
            genesis,
            {"groups_per_region": 10, "min_members": 2, "max_members": 5},
        )

    def insert_group(self, group_id, ids):
        members = [
            {"id": monster_id, "ref": 1, "level": 1, "x": 10 + index, "y": 20, "z": 0}
            for index, monster_id in enumerate(ids)
        ]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) "
                "VALUES(1134,0,%s,%s::jsonb,'available')",
                (group_id, __import__("json").dumps(members)),
            )

    def test_admin_removed_members_stay_removed_when_fight_releases(self):
        self.insert_group(801, [-8101, -8102, -8103])
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET ecology_admin_removed_ids='[-8102]'::jsonb "
                "WHERE map_id=1134 AND instance_id=0 AND group_id=801"
            )
            db.execute(
                "UPDATE combat_groups SET status='available',generation=NULL,fight_id=NULL "
                "WHERE map_id=1134 AND instance_id=0 AND group_id=801"
            )
            row = db.execute(
                "SELECT members,status,ecology_admin_removed_ids FROM combat_groups "
                "WHERE map_id=1134 AND instance_id=0 AND group_id=801"
            ).fetchone()
        self.assertEqual([member["id"] for member in row["members"]], [-8101, -8103])
        self.assertEqual(row["status"], "available")
        self.assertEqual(row["ecology_admin_removed_ids"], [-8102])

    def test_removing_every_member_defeats_group_and_retains_tombstone_roster(self):
        self.insert_group(802, [-8201, -8202])
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET ecology_admin_removed_ids='[-8201,-8202]'::jsonb "
                "WHERE map_id=1134 AND instance_id=0 AND group_id=802"
            )
            db.execute(
                "UPDATE combat_groups SET status='available',generation=NULL,fight_id=NULL "
                "WHERE map_id=1134 AND instance_id=0 AND group_id=802"
            )
            row = db.execute(
                "SELECT members,status,defeated_at FROM combat_groups "
                "WHERE map_id=1134 AND instance_id=0 AND group_id=802"
            ).fetchone()
        self.assertEqual([member["id"] for member in row["members"]], [-8201, -8202])
        self.assertEqual(row["status"], "defeated")
        self.assertIsNotNone(row["defeated_at"])

    def test_unmarked_group_release_is_unchanged(self):
        self.insert_group(803, [-8301, -8302])
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET status='available',generation=NULL,fight_id=NULL "
                "WHERE map_id=1134 AND instance_id=0 AND group_id=803"
            )
            row = db.execute(
                "SELECT members,status,ecology_admin_removed_ids FROM combat_groups "
                "WHERE map_id=1134 AND instance_id=0 AND group_id=803"
            ).fetchone()
        self.assertEqual([member["id"] for member in row["members"]], [-8301, -8302])
        self.assertEqual(row["status"], "available")
        self.assertEqual(row["ecology_admin_removed_ids"], [])
