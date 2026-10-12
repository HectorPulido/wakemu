"""PostgreSQL contract for partial-region ecology removal and stale work fences."""

import importlib
import importlib.util
import json
import sys
import types
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.combat_group_store import PersistentGroups


def _load_domain_with_native_boundaries_stubbed():
    modules = {
        "wakfu_server.monster_initial_population": types.SimpleNamespace(REGIONS={}),
        "wakfu_server.territory_cells": types.SimpleNamespace(
            region_at=lambda _map, x, _y: 7 if x < 20 else 8
        ),
        "wakfu_server.monsters": types.SimpleNamespace(
            reference=lambda ref: {"family_id": 70, "name": f"Fixture {ref}"},
            owned_instance=lambda *_a, **_k: None,
        ),
        "wakfu_server.planting": types.SimpleNamespace(
            RESOURCES={}, SEEDS={}, decode=lambda _body: {}
        ),
    }
    with patch.dict(sys.modules, modules):
        path = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server"
            / "maps"
            / "ecology_admin.py"
        )
        spec = importlib.util.spec_from_file_location(
            "wakfu_server._ecology_admin_test_subject", path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


ecology_admin = _load_domain_with_native_boundaries_stubbed()


class EcologyAdminDomainPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.group_id = 9001
        self.members = [
            {"id": -9101, "ref": 701, "level": 1, "x": 5, "y": 6, "z": 0},
            {"id": -9102, "ref": 702, "level": 1, "x": 50, "y": 60, "z": 0},
        ]
        with self.store.connection() as db:
            with db.transaction():
                db.execute(
                    "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) "
                    "VALUES(1134,0,%s,%s::jsonb,'available')",
                    (self.group_id, __import__("json").dumps(self.members)),
                )
                for member in self.members:
                    db.execute(
                        "INSERT INTO combat_group_members(map_id,instance_id,group_id,monster_id) "
                        "VALUES(1134,0,%s,%s)",
                        (self.group_id, member["id"]),
                    )
                    db.execute(
                        "INSERT INTO monster_maturation_timers(map_id,instance_id,monster_id,reference,remaining_ms) "
                        "VALUES(1134,0,%s,%s,1000)",
                        (member["id"], member["ref"]),
                    )
                    db.execute(
                        "INSERT INTO monster_reproduction_timers(map_id,instance_id,monster_id,reference,remaining_ms) "
                        "VALUES(1134,0,%s,%s,1000)",
                        (member["id"], member["ref"]),
                    )
                    db.execute(
                        "INSERT INTO monster_maturation_receipts(map_id,instance_id,monster_id,cycle,group_id,from_reference,to_reference,draw,policy) "
                        "VALUES(1134,0,%s,1,%s,%s,%s,0.5,'{}'::jsonb)",
                        (member["id"], self.group_id, member["ref"], member["ref"] + 1),
                    )
                    db.execute(
                        "INSERT INTO monster_maturation_outbox(map_id,instance_id,monster_id,cycle,group_id,revision) "
                        "VALUES(1134,0,%s,1,%s,0)",
                        (member["id"], self.group_id),
                    )
                    db.execute(
                        "INSERT INTO monster_reproduction_receipts(map_id,instance_id,monster_id,cycle,parent_group_id,parent_reference,draw,probability,policy) "
                        "VALUES(1134,0,%s,1,%s,%s,0.5,0.1,'{}'::jsonb)",
                        (member["id"], self.group_id, member["ref"]),
                    )
                    db.execute(
                        "INSERT INTO monster_reproduction_outbox(map_id,instance_id,monster_id,cycle,group_id,revision,new_group) "
                        "VALUES(1134,0,%s,1,%s,0,false)",
                        (member["id"], self.group_id),
                    )

    def test_nuke_partial_region_preserves_neighbor_timers_and_outboxes(self):
        combat_world = types.SimpleNamespace(
            remove_message=lambda ids: (12544, tuple(ids)),
            spawn_group=lambda members, *, group_id: (
                group_id,
                tuple(m["id"] for m in members),
            ),
        )
        planting_runtime = types.SimpleNamespace(state_packet=lambda *_a: None)
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.combat_monster_world": combat_world,
                "wakfu_server.planting_runtime": planting_runtime,
            },
        ), patch.object(ecology_admin, "_fence_initial"):
            with self.store.connection() as db:
                with db.transaction():
                    result = ecology_admin._nuke(db, 1134, 0, 7)

        self.assertEqual(
            (result["removed"], result["deferred"], result["cancelled"]), (1, 0, 0)
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT members,status,ecology_admin_removed_ids FROM combat_groups "
                "WHERE map_id=1134 AND instance_id=0 AND group_id=%s",
                (self.group_id,),
            ).fetchone()
            maturation = db.execute(
                "SELECT monster_id,published FROM monster_maturation_outbox ORDER BY monster_id"
            ).fetchall()
            reproduction = db.execute(
                "SELECT monster_id,published FROM monster_reproduction_outbox ORDER BY monster_id"
            ).fetchall()
            maturation_timers = db.execute(
                "SELECT monster_id FROM monster_maturation_timers ORDER BY monster_id"
            ).fetchall()
            reproduction_timers = db.execute(
                "SELECT monster_id FROM monster_reproduction_timers ORDER BY monster_id"
            ).fetchall()
            personal_receipts = db.execute(
                "SELECT count(*) AS count FROM personal_ecology_receipts"
            ).fetchone()["count"]

        self.assertEqual([m["id"] for m in row["members"]], [-9102])
        self.assertEqual(row["status"], "available")
        self.assertEqual(row["ecology_admin_removed_ids"], [-9101])
        self.assertEqual(maturation_timers, [{"monster_id": -9102}])
        self.assertEqual(reproduction_timers, [{"monster_id": -9102}])
        self.assertEqual(
            maturation,
            [
                {"monster_id": -9102, "published": False},
                {"monster_id": -9101, "published": True},
            ],
        )
        self.assertEqual(
            reproduction,
            [
                {"monster_id": -9102, "published": False},
                {"monster_id": -9101, "published": True},
            ],
        )
        self.assertEqual(personal_receipts, 0)

    def test_domain_authorization_reads_account_admin_flag_before_scope_work(self):
        account_id = self.store.register("ecology-domain-auth", "test-password")["id"]
        with self.store.connection() as db:
            character_id = db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
                "VALUES(%s,'Ecology Domain Auth','ecology domain auth',1,false,0,0,'[]','{}',100,100) RETURNING id",
                (account_id,),
            ).fetchone()["id"]
            character = db.execute(
                "SELECT id,account_id,map_id,instance_id,x,y,z FROM characters WHERE id=%s",
                (character_id,),
            ).fetchone()

        class Groups:
            import threading

            lock = threading.RLock()

        with self.assertRaisesRegex(ValueError, "administrator"):
            ecology_admin.execute(self.store, Groups(), character, "!nuke")

        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=TRUE WHERE id=%s", (account_id,))
        with patch.object(
            ecology_admin, "_scopes", side_effect=RuntimeError("authorized")
        ):
            with self.assertRaisesRegex(RuntimeError, "authorized"):
                ecology_admin.execute(self.store, Groups(), character, "!nuke")

    def test_mutation_audit_commits_exact_scope_without_packet_bytes(self):
        account_id = self.store.register("ecology-domain-audit", "test-password")["id"]
        with self.store.connection() as db:
            db.execute("UPDATE accounts SET is_admin=TRUE WHERE id=%s", (account_id,))
            character_id = db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
                "VALUES(%s,'Ecology Domain Audit','ecology domain audit',1,false,0,0,'[]','{}',100,100) RETURNING id",
                (account_id,),
            ).fetchone()["id"]
            character = db.execute(
                "SELECT id,account_id,map_id,instance_id,x,y,z FROM characters WHERE id=%s",
                (character_id,),
            ).fetchone()

        class Groups:
            import threading

            lock = threading.RLock()

        events = []

        @contextmanager
        def coordination(scope):
            events.append(("enter", scope))
            try:
                yield
            finally:
                events.append(("exit", scope))

        def publish(scope_result):
            with self.store.connection() as db:
                committed = db.execute(
                    "SELECT 1 FROM ecology_admin_operations WHERE id=%s",
                    (scope_result["operation_id"],),
                ).fetchone()
            self.assertIsNotNone(committed)
            events.append(("publish", scope_result["scopes"][0]))

        with patch.object(
            ecology_admin, "_scopes", return_value=[(1134, 0, 7)]
        ), patch.object(
            ecology_admin,
            "_nuke",
            return_value={
                "removed": 2,
                "deferred": 1,
                "cancelled": 3,
                "added": 0,
                "packets": [],
                "removed_groups": [
                    {"key": [1134, 0, 123], "actor_ids": [-1, -2, -3], "deferred": 1}
                ],
            },
        ):
            result = ecology_admin.execute(
                self.store,
                Groups(),
                character,
                "!nuke",
                coordination=lambda _scope: coordination(_scope),
                publish=publish,
            )

        self.assertIsInstance(result["operation_id"], int)
        with self.store.connection() as db:
            audit = db.execute(
                "SELECT account_id,character_id,command,outcome FROM ecology_admin_operations WHERE id=%s",
                (result["operation_id"],),
            ).fetchone()
        self.assertEqual(
            (audit["account_id"], audit["character_id"], audit["command"]),
            (account_id, character_id, "!nuke"),
        )
        self.assertEqual(audit["outcome"]["removed"], 2)
        self.assertEqual(audit["outcome"]["scopes"], [[1134, 0, 7]])
        self.assertNotIn("location_packets", audit["outcome"])
        self.assertEqual(
            events,
            [
                ("enter", (1134, 0, 7)),
                ("publish", (1134, 0, 7)),
                ("exit", (1134, 0, 7)),
            ],
        )

    def test_world_seed_reconciliation_accepts_admin_tombstoned_seed_member(self):
        key = (1134, 0, 9301)
        survivor = {"id": -9302, "ref": 701, "level": 1, "x": 5, "y": 6, "z": 0}
        removed = {"id": -9301, "ref": 701, "level": 1, "x": 7, "y": 8, "z": 0}
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status,ecology_admin_removed_ids) "
                "VALUES(1134,0,%s,%s::jsonb,'available','[-9301]'::jsonb)",
                (key[2], json.dumps([survivor])),
            )

        class SeedValidator:
            def register(self, *_args):
                return key

        identity_repair = types.SimpleNamespace(
            actor_aliases=lambda _db, _key: {},
            aliased_members=lambda members, _aliases: members,
        )
        groups = PersistentGroups(self.store)
        with patch("wakfu_server.combat_group_store.Groups", SeedValidator), patch.dict(
            sys.modules, {"wakfu_server.npc_actor_identity_repair": identity_repair}
        ):
            self.assertEqual(groups.register_seed(*key, [removed, survivor]), key)

    def test_release_session_returns_only_surviving_roster_and_respawn_rejects_tombstone(
        self,
    ):
        fight_members = [
            {"id": -9401, "ref": 701, "level": 1, "x": 5, "y": 6, "z": 0},
            {"id": -9402, "ref": 701, "level": 1, "x": 7, "y": 8, "z": 0},
        ]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status,generation,fight_id,ecology_admin_removed_ids) "
                "VALUES(1134,0,9401,%s::jsonb,'fighting','ecology-release-generation',%s,'[-9401]'::jsonb)",
                (json.dumps(fight_members), fight_id),
            )

        groups = PersistentGroups(self.store)
        released = groups.release_session("ecology-release-generation")
        self.assertEqual(len(released), 1)
        self.assertEqual(released[0]["key"], (1134, 0, 9401))
        self.assertEqual([member["id"] for member in released[0]["members"]], [-9402])

        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status,ecology_admin_removed_ids) "
                "VALUES(1134,0,9402,%s::jsonb,'defeated','[-9403]'::jsonb)",
                (json.dumps([dict(fight_members[0], id=-9403)]),),
            )
        with self.assertRaisesRegex(ValueError, "Administratively removed"):
            groups.respawn((1134, 0, 9402))

    def test_genesis_reaches_target_once_then_is_idempotent(self):
        region = {
            "monster_capacity": 64,
            "monster_families": [{"family_id": 70}],
        }
        allocation_index = [0]
        actor_id = [9200]
        budget_calls = []

        def plan_groups(
            _map,
            _region,
            counts,
            _occupied,
            *,
            group_counts,
            target_groups,
            min_members,
            max_members,
            capacity,
            max_groups,
            member_budget,
            prepared=None,
        ):
            self.assertEqual(
                (target_groups, min_members, max_members, capacity), (10, 2, 5, 64)
            )
            budget_calls.append((max_groups, member_budget))
            self.assertLessEqual(max_groups, 100)
            self.assertLessEqual(member_budget, 500)
            remaining = max(0, target_groups - sum(group_counts.values()))
            groups = []
            for group_index in range(remaining):
                size = 2 + group_index % 4
                chunk = []
                for member_index in range(size):
                    ordinal = allocation_index[0]
                    allocation_index[0] += 1
                    chunk.append(
                        {
                            "reference": 701 + ordinal % 2,
                            "level": 1,
                            "x": group_index * 6 + member_index,
                            "y": group_index * 3,
                            "z": 0,
                        }
                    )
                groups.append(chunk)
            return groups

        def allocate(_db, count):
            value = actor_id[0]
            actor_id[0] += count
            return value

        def owned_instance(ref, level, monster_id, **position):
            return {"id": monster_id, "ref": ref, "level": level, **position}

        class Groups:
            def register_transaction(self, db, map_id, instance_id, group_id, members):
                db.execute(
                    "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) "
                    "VALUES(%s,%s,%s,%s::jsonb,'available')",
                    (map_id, instance_id, group_id, json.dumps(members)),
                )
                for member in members:
                    db.execute(
                        "INSERT INTO combat_group_members(map_id,instance_id,group_id,monster_id) "
                        "VALUES(%s,%s,%s,%s)",
                        (map_id, instance_id, group_id, member["id"]),
                    )
                return (map_id, instance_id, group_id)

        group_api = Groups()
        planner = types.SimpleNamespace(plan_groups=plan_groups)
        identity = types.SimpleNamespace(allocate_block=allocate)
        combat_world = types.SimpleNamespace(
            spawn_group=lambda members, *, group_id: (
                group_id,
                tuple(m["id"] for m in members),
            )
        )
        prepared = {"candidates": {70: (dict(reference=701), dict(reference=702))}}
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.ecology_admin_planner": planner,
                "wakfu_server.npc_actor_identity": identity,
                "wakfu_server.combat_monster_world": combat_world,
            },
        ), patch.dict(ecology_admin.REGIONS, {(1134, 7): region}), patch.object(
            ecology_admin, "reference", lambda _ref: {"family_id": 70}
        ), patch.object(
            ecology_admin, "owned_instance", owned_instance
        ), patch.object(
            ecology_admin, "_fence_initial"
        ), patch.object(
            ecology_admin, "region_at", return_value=7
        ):
            with self.store.connection() as db:
                with db.transaction():
                    db.execute(
                        "DELETE FROM combat_groups WHERE map_id=1134 AND instance_id=0 AND group_id=%s",
                        (self.group_id,),
                    )
                    first = ecology_admin._genesis(
                        db, group_api, 1134, 0, 7, prepared=prepared
                    )
                with db.transaction():
                    second = ecology_admin._genesis(
                        db, group_api, 1134, 0, 7, prepared=prepared
                    )

        self.assertEqual(len(first["created_groups"]), 10)
        self.assertEqual(first["added"], sum(2 + index % 4 for index in range(10)))
        self.assertEqual(
            {group["size"] for group in first["created_groups"]}, {2, 3, 4, 5}
        )
        self.assertEqual(
            {ref for group in first["created_groups"] for ref in group["references"]},
            {701, 702},
        )
        self.assertEqual(second["added"], 0)
        self.assertEqual(budget_calls, [(100, 500), (90, 467)])
        with self.store.connection() as db:
            groups = db.execute(
                "SELECT members FROM combat_groups WHERE map_id=1134 AND instance_id=0 AND group_id!=%s ORDER BY group_id",
                (self.group_id,),
            ).fetchall()
        self.assertEqual(len(groups), 10)
        self.assertEqual(
            sorted(len(row["members"]) for row in groups),
            sorted(2 + index % 4 for index in range(10)),
        )
