"""Birth provenance is immutable and independent of a monster's family or drift."""
from copy import deepcopy
from unittest.mock import patch
import unittest

from postgres_case import PostgresCase
from psycopg.errors import RaiseException
from psycopg.types.json import Jsonb
from wakfu_server import monster_birth_home as homes
from wakfu_server import monster_idle_distribution_store as idle


class MonsterBirthHomeNativeCellTests(unittest.TestCase):
    def test_reported_tainela_walk_step_crosses_an_exact_birth_territory_boundary(self):
        self.assertEqual(homes.region_for_point(527, (-199, -67, 0)), 76101)
        self.assertEqual(homes.region_for_point(527, (-198, -67, 0)), 76001)


class MonsterBirthHomePostgresTests(PostgresCase):
    def test_unknown_defeated_positions_do_not_block_living_empty_scope_distribution(
        self,
    ):
        import random
        from test_monster_idle_distribution import grid

        scope = (999997, 0)
        living = dict(
            id=-9401,
            ref=4,
            level=10,
            hp=17,
            max_hp=99,
            map_id=scope[0],
            instance_id=0,
            x=0,
            y=0,
            z=0,
            team=1,
        )
        defeated = dict(living, id=-9402, hp=0, x=1000000, y=1000000)
        with self.store.connection() as db:
            for identity, status, member in (
                (9401, "available", living),
                (9402, "defeated", defeated),
            ):
                db.execute(
                    "INSERT INTO combat_groups(map_id,instance_id,group_id,status,members) "
                    "VALUES(%s,0,%s,%s,%s)",
                    (scope[0], identity, status, Jsonb([member])),
                )
            db.execute(
                "INSERT INTO monster_group_birth_homes(map_id,instance_id,group_id,"
                "region_id,source_kind,source_key,anchor) "
                "VALUES(%s,0,9401,11,'initial_population','living-proof','[0,0,0]')",
                (scope[0],),
            )

        def region(_map, point):
            if 0 <= point[0] < 8 and 0 <= point[1] < 8 and point[2] == 0:
                return 11
            raise ValueError("Unknown territory cell")

        # A missing historical birthplace must still be rejected when requested;
        # only the idle planner's living-group selection may exclude this row.
        with patch.object(homes, "region_for_point", side_effect=region):
            with self.assertRaisesRegex(ValueError, "Unknown territory cell"):
                homes.ensure_homes(
                    self.store, *scope, [dict(group_id=9402, members=[defeated])]
                )

        rng = random.Random(17)
        snapshot = dict(
            world_epoch="living-after-history",
            empty_scopes=[dict(map_id=scope[0], instance_id=0, empty_generation=1)],
        )
        with patch.object(homes, "region_for_point", side_effect=region), patch(
            "wakfu_server.combat_terrain.map_geometry", return_value=grid(8)
        ), patch(
            "wakfu_server.monster_idle_distribution.native_physical_radius",
            return_value=0,
        ), patch(
            "wakfu_server.monster_idle_distribution.random.Random", return_value=rng
        ):
            proposals = idle.prepare(self.store, snapshot)
            self.assertEqual(len(proposals), 1)
            self.assertTrue(idle.home_chunk_allowed(self.store, proposals[0]))
            moves = idle.read_chunk(self.store, proposals[0])
            self.assertEqual([move["group_id"] for move in moves], [9401])
            self.assertEqual(moves[0]["expected_members"], [living])
            self.assertNotEqual(moves[0]["moved_members"], [living])
            with patch(
                "wakfu_server.monster_idle_distribution.plan",
                side_effect=AssertionError("Durable empty episode was rerolled"),
            ):
                self.assertEqual(idle.prepare(self.store, snapshot), proposals)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT region_id FROM monster_group_birth_homes "
                    "WHERE group_id=9402"
                ).fetchone()
            )
            groups = {
                row["group_id"]: row
                for row in db.execute(
                    "SELECT group_id,status,members,revision FROM combat_groups ORDER BY group_id"
                )
            }
            self.assertEqual(groups[9401]["members"], [living])
            self.assertEqual(groups[9402]["members"], [defeated])
            self.assertEqual(groups[9402]["status"], "defeated")
            self.assertEqual([row["revision"] for row in groups.values()], [0, 0])

    def test_old_frozen_idle_plan_outside_home_is_cancelled_before_ecology_delivery(
        self,
    ):
        scope = (999998, 0)
        member = dict(
            id=-9301,
            ref=4,
            level=10,
            hp=17,
            max_hp=99,
            map_id=scope[0],
            instance_id=0,
            x=0,
            y=0,
            z=0,
            team=1,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_groups(map_id,instance_id,group_id,status,members) "
                "VALUES(%s,0,9301,'available',%s)",
                (scope[0], Jsonb([member])),
            )
            db.execute(
                "INSERT INTO monster_group_birth_homes(map_id,instance_id,group_id,"
                "region_id,source_kind,source_key,anchor) "
                "VALUES(%s,0,9301,11,'initial_population','old-proof','[0,0,0]')",
                (scope[0],),
            )
        invalid = dict(
            group_id=9301, expected_members=[member], moved_members=[dict(member, x=20)]
        )
        old_run = idle.freeze(
            self.store, epoch="frozen-home", scope=scope, generation=1, moves=[invalid]
        )
        snapshot = dict(
            world_epoch="frozen-home",
            empty_scopes=[dict(map_id=scope[0], instance_id=0, empty_generation=1)],
        )
        with patch.object(
            homes,
            "region_for_point",
            side_effect=lambda _map, p: 11 if p[0] < 10 else 22,
        ), patch(
            "wakfu_server.monster_idle_distribution.native_physical_radius",
            return_value=0,
        ), patch(
            "wakfu_server.monster_idle_distribution.plan",
            side_effect=AssertionError("Frozen episode must not be rerolled"),
        ):
            self.assertEqual(idle.prepare(self.store, snapshot), [])
            self.assertEqual(idle.prepare(self.store, snapshot), [])
            valid = dict(
                group_id=9301,
                expected_members=[member],
                moved_members=[dict(member, x=2)],
            )
            idle.freeze(
                self.store,
                epoch="frozen-home",
                scope=scope,
                generation=2,
                moves=[valid],
            )
            snapshot["empty_scopes"][0]["empty_generation"] = 2
            delivered = idle.prepare(self.store, snapshot)
            self.assertEqual(len(delivered), 1)
            self.assertEqual(delivered[0]["empty_generation"], 2)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM monster_idle_distribution_runs WHERE id=%s",
                    (old_run,),
                ).fetchone()["status"],
                "cancelled",
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM monster_idle_distribution_moves WHERE run_id=%s",
                    (old_run,),
                ).fetchone()["status"],
                "cancelled",
            )
            row = db.execute(
                "SELECT members,revision FROM combat_groups WHERE group_id=9301"
            ).fetchone()
            self.assertEqual(row["members"], [member])
            self.assertEqual(row["revision"], 0)
            self.assertEqual(
                db.execute(
                    "SELECT region_id FROM monster_group_birth_homes WHERE group_id=9301"
                ).fetchone()["region_id"],
                11,
            )

    def test_history_dead_parent_and_foreign_planting_win_over_current_position(self):
        map_id = 999999

        def member(identity, x, reference=4):
            return dict(
                id=-identity,
                ref=reference,
                level=10,
                hp=17,
                max_hp=99,
                map_id=map_id,
                instance_id=0,
                x=x,
                y=0,
                z=0,
                team=1,
            )

        parent = dict(group_id=9101, status="defeated", members=[member(9101, 20)])
        child = dict(group_id=9102, status="available", members=[member(9102, 25)])
        foreign = dict(
            group_id=9103,
            status="available",
            members=[member(9103, 22, reference=9999)],
        )
        unknown = dict(group_id=9104, status="available", members=[member(9104, 27)])
        genesis = dict(group_id=9105, status="available", members=[member(9105, 25)])
        all_groups = [parent, child, foreign, unknown, genesis]
        before = deepcopy(all_groups)
        with self.store.connection() as db:
            for group in all_groups:
                db.execute(
                    "INSERT INTO combat_groups(map_id,instance_id,group_id,status,members) "
                    "VALUES(%s,0,%s,%s,%s)",
                    (
                        map_id,
                        group["group_id"],
                        group["status"],
                        Jsonb(group["members"]),
                    ),
                )
            db.execute(
                "INSERT INTO monster_initial_population"
                "(map_id,instance_id,region_id,policy_version,group_id,initial_members) "
                "VALUES(%s,0,11,1,9101,%s)",
                (map_id, Jsonb([member(9101, 0)])),
            )
            db.execute(
                "INSERT INTO monster_reproduction_receipts"
                "(map_id,instance_id,monster_id,cycle,parent_group_id,parent_reference,child_id,"
                "child_group_id,child,draw,probability,policy) "
                "VALUES(%s,0,-9101,1,9101,4,-9102,9102,%s,0,1,'{}')",
                (map_id, Jsonb(member(9102, 21))),
            )
            resource = dict(map_id=map_id, instance_id=0, x=3, y=0, z=0)
            payload = dict(
                key=[map_id, 0, 9103], members=[member(9103, 3, reference=9999)]
            )
            db.execute(
                "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) "
                "VALUES(991003,%s,%s)",
                (Jsonb(resource), Jsonb(payload)),
            )
            db.execute(
                "INSERT INTO accounts(id,username,username_key,salt,password_hash) "
                "VALUES(9200,'home-probe','home-probe',%s,%s)",
                (bytes(16), b"test-hash"),
            )
            db.execute(
                "INSERT INTO characters(id,account_id,name,name_key,breed,sex,face,hair,"
                "colors,appearance,hp,max_hp) "
                "VALUES(9200,9200,'HomeProbe','homeprobe',1,false,0,0,'[]','{}',1,1)"
            )
            db.execute(
                "INSERT INTO ecology_admin_operations(account_id,character_id,command,outcome) "
                "VALUES(9200,9200,'!genesis',%s)",
                (
                    Jsonb(
                        dict(
                            scopes=[[map_id, 0, 11]],
                            created_groups=[dict(key=[map_id, 0, 9105])],
                        )
                    ),
                ),
            )

        region = lambda _map, point: 11 if point[0] < 10 else 22
        with patch.object(homes, "region_for_point", side_effect=region):
            result = homes.ensure_homes(
                self.store, map_id, 0, [child, foreign, unknown, genesis]
            )
        self.assertEqual(result, {9102: 11, 9103: 11, 9104: 22, 9105: 11})
        self.assertEqual(all_groups, before)
        self.assertEqual(homes.home_for_group(self.store, map_id, 0, 9101), 11)
        with self.store.connection() as db:
            ledger = {
                row["group_id"]: row
                for row in db.execute("SELECT * FROM monster_group_birth_homes")
            }
            actual = {
                row["group_id"]: row["members"]
                for row in db.execute("SELECT group_id,members FROM combat_groups")
            }
        self.assertEqual(actual, {g["group_id"]: g["members"] for g in before})
        self.assertEqual(ledger[9101]["source_kind"], "initial_population")
        self.assertEqual(ledger[9102]["source_kind"], "reproduction_parent")
        self.assertEqual(ledger[9102]["source_key"], "9101")
        self.assertEqual(ledger[9103]["source_kind"], "planting")
        self.assertEqual(ledger[9104]["source_kind"], "legacy_current_fallback")
        self.assertEqual(ledger[9104]["anchor"], [27, 0, 0])
        self.assertEqual(ledger[9105]["source_kind"], "genesis_scope")
        self.assertIsNone(ledger[9105]["anchor"])

        # Later movement and more observations cannot reinterpret birthplace.
        moved_unknown = [dict(unknown["members"][0], x=0)]
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_groups SET members=%s WHERE group_id=9104",
                (Jsonb(moved_unknown),),
            )
        refreshed = dict(unknown, members=moved_unknown)
        with patch.object(
            homes,
            "region_for_point",
            side_effect=AssertionError("Recorded home was recomputed"),
        ):
            self.assertEqual(
                homes.ensure_homes(
                    self.reopen(), map_id, 0, [child, foreign, refreshed, genesis]
                ),
                result,
            )
        with self.store.connection() as db:
            with self.assertRaisesRegex(RaiseException, "immutable"):
                with db.transaction():
                    db.execute(
                        "UPDATE monster_group_birth_homes SET region_id=99 WHERE group_id=9104"
                    )
        self.assertEqual(homes.home_for_group(self.store, map_id, 0, 9104), 22)
