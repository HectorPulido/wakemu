from concurrent.futures import ThreadPoolExecutor
import json
import math
import unittest
from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server import monster_reproduction, npc_actor_identity
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import REFERENCES, owned_instance


class MonsterReproductionTests(PostgresCase):
    def _register_monster(
        self, map_id=1134, instance_id=0, group_id=99001, monster_id=-99001
    ):
        member = owned_instance(
            2,
            REFERENCES[2]["min_level"],
            monster_id,
            map_id=map_id,
            x=0,
            y=0,
            z=0,
        )
        key = PersistentGroups(self.store).register(
            map_id, instance_id, group_id, [member]
        )
        return key, member

    def _receipt(
        self,
        map_id,
        instance_id,
        monster_id,
        cycle,
        group_id=99001,
        *,
        child_id=None,
        child_group_id=None,
        child=None
    ):
        with self.store.connection() as db:
            return db.execute(
                "INSERT INTO monster_reproduction_receipts"
                "(map_id,instance_id,monster_id,cycle,parent_group_id,parent_reference,"
                "child_id,child_group_id,child,draw,probability,policy) "
                "VALUES(%s,%s,%s,%s,%s,2,%s,%s,%s,0.05,0.05,%s) RETURNING *",
                (
                    map_id,
                    instance_id,
                    monster_id,
                    cycle,
                    group_id,
                    child_id,
                    child_group_id,
                    Jsonb(child) if child is not None else None,
                    Jsonb({"birth_probability": 0.05, "birth_stage_decay": 0.5}),
                ),
            ).fetchone()

    def _set_policy(self, value):
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_reproduction'",
                (Jsonb(value),),
            )

    def test_database_policy_defaults_and_inclusive_bounds(self):
        self.assertEqual(
            {
                "interval_ms": 60000,
                "birth_probability": 0.05,
                "birth_stage_decay": 0.5,
                "new_group_probability": 0.5,
                "max_members": 8,
                "max_zone_members": 5000,
                "max_zone_groups": 1000,
            },
            monster_reproduction.policy(self.store),
        )
        self._set_policy(
            {
                "interval_ms": 1000,
                "birth_probability": 0,
                "birth_stage_decay": 0.5,
                "new_group_probability": 1,
                "max_members": 1,
                "max_zone_members": 128,
                "max_zone_groups": 32,
            }
        )
        self.assertEqual(1, monster_reproduction.policy(self.store)["max_members"])
        self._set_policy(
            {
                "interval_ms": 86400000,
                "birth_probability": 1,
                "birth_stage_decay": 0.5,
                "new_group_probability": 0,
                "max_members": 8,
                "max_zone_members": 128,
                "max_zone_groups": 32,
            }
        )
        self.assertEqual(
            86400000, monster_reproduction.policy(self.store)["interval_ms"]
        )

    def test_policy_rejects_missing_shape_bool_and_out_of_range_values(self):
        with self.store.connection() as db:
            db.execute("DELETE FROM settings WHERE name='monster_reproduction'")
        with self.assertRaisesRegex(ValueError, "Invalid monster reproduction policy"):
            monster_reproduction.policy(self.store)

        valid = {
            "interval_ms": 60000,
            "birth_probability": 0.05,
            "birth_stage_decay": 0.5,
            "new_group_probability": 0.5,
            "max_members": 8,
            "max_zone_members": 128,
            "max_zone_groups": 32,
        }
        invalid_values = [
            {},
            {**valid, "extra": 1},
            {**valid, "interval_ms": True},
            {**valid, "interval_ms": 999},
            {**valid, "interval_ms": 86400001},
            {**valid, "max_members": True},
            {**valid, "max_members": 0},
            {**valid, "max_members": 9},
            {**valid, "max_zone_members": True},
            {**valid, "max_zone_members": 0},
            {**valid, "max_zone_members": 100001},
            {**valid, "max_zone_groups": False},
            {**valid, "max_zone_groups": 0},
            {**valid, "max_zone_groups": 100001},
            {**valid, "birth_probability": True},
            {**valid, "birth_probability": -0.01},
            {**valid, "birth_probability": 1.01},
            {**valid, "birth_stage_decay": True},
            {**valid, "birth_stage_decay": -0.01},
            {**valid, "birth_stage_decay": 1.01},
            {**valid, "new_group_probability": False},
        ]
        for invalid in invalid_values:
            with self.subTest(invalid=invalid):
                self._set_policy(invalid)
                with self.assertRaises(ValueError):
                    monster_reproduction.policy(self.store)

    def test_policy_rejects_nonfinite_probability_loaded_from_jsonb(self):
        # PostgreSQL numeric JSON accepts large finite exponents; Python's JSON
        # loader converts this value to +inf, which must fail policy validation.
        raw = json.dumps(
            {
                "interval_ms": 60000,
                "birth_probability": 0.05,
                "birth_stage_decay": 0.5,
                "new_group_probability": 0.5,
                "max_members": 8,
                "max_zone_members": 128,
                "max_zone_groups": 32,
            }
        ).replace('"birth_probability": 0.05', '"birth_probability": 1e999')
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s::jsonb WHERE name='monster_reproduction'",
                (raw,),
            )
        with self.assertRaises(ValueError):
            monster_reproduction.policy(self.store)

    def test_birth_probability_includes_base_forms_and_softly_decays_by_group_size(
        self,
    ):
        configuration = monster_reproduction.policy(self.store)
        base = monster_reproduction.birth_probability(2, configuration, group_size=1)
        small = monster_reproduction.birth_probability(4, configuration, group_size=1)
        crowded = monster_reproduction.birth_probability(4, configuration, group_size=8)
        self.assertGreater(base, 0.0)
        self.assertGreater(small, 0.0)
        self.assertGreater(crowded, 0.0)
        self.assertLess(crowded, small)
        self.assertEqual(0.0, monster_reproduction.birth_probability(44, configuration))
        self.assertEqual(
            0.0, monster_reproduction.birth_probability(999999, configuration)
        )

    def test_identity_sequence_is_lua_exact_and_skips_claimed_legacy_ids(self):
        # Legacy random IDs overlap this range; the allocator skips occupied
        # actor blocks instead of assuming the namespaces are disjoint.
        legacy_id = -npc_actor_identity.MINIMUM
        self._register_monster(monster_id=legacy_id)
        with self.store.connection() as db:
            magnitude, actor_id = monster_reproduction.allocate_identity(db)
        self.assertGreaterEqual(
            magnitude, npc_actor_identity.MINIMUM + npc_actor_identity.BLOCK_SIZE
        )
        self.assertLessEqual(magnitude, npc_actor_identity.MAXIMUM)
        self.assertEqual(-magnitude, actor_id)
        self.assertNotEqual(legacy_id, actor_id)
        self.assertTrue(npc_actor_identity.lua_exact_identity(actor_id))

    def test_sequence_allocation_is_not_reused_after_transaction_rollback(self):
        allocated = None
        with self.assertRaisesRegex(RuntimeError, "force rollback"):
            with self.store.connection() as db:
                allocated = monster_reproduction.allocate_identity(db)
                raise RuntimeError("force rollback")
        with self.store.connection() as db:
            next_value = monster_reproduction.allocate_identity(db)
        self.assertGreater(next_value[0], allocated[0])
        self.assertEqual(-next_value[0], next_value[1])

    def test_concurrent_allocations_are_unique_positive_group_and_negative_actor_ids(
        self,
    ):
        def allocate(_):
            with self.store.connection() as db:
                return monster_reproduction.allocate_identity(db)

        with ThreadPoolExecutor(max_workers=8) as pool:
            identities = list(pool.map(allocate, range(32)))
        magnitudes = [group_id for group_id, _actor_id in identities]
        actor_ids = [actor_id for _group_id, actor_id in identities]
        self.assertEqual(32, len(set(magnitudes)))
        self.assertEqual(32, len(set(actor_ids)))
        self.assertTrue(all(group_id > 0 for group_id in magnitudes))
        self.assertTrue(all(actor_id < 0 for actor_id in actor_ids))
        self.assertEqual({-group_id for group_id in magnitudes}, set(actor_ids))
        self.assertTrue(
            all(
                npc_actor_identity.MINIMUM <= group_id <= npc_actor_identity.MAXIMUM
                for group_id in magnitudes
            )
        )
        self.assertTrue(
            all(
                npc_actor_identity.lua_exact_identity(actor_id)
                for actor_id in actor_ids
            )
        )
        self.assertTrue(all(math.isfinite(float(group_id)) for group_id in magnitudes))

    def test_timer_cascades_with_member_but_historical_receipt_is_retained(self):
        key, member = self._register_monster()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_reproduction_timers"
                "(map_id,instance_id,monster_id,reference,remaining_ms) "
                "VALUES(%s,%s,%s,%s,60000)",
                (*key[:2], member["id"], member["ref"]),
            )
        self._receipt(*key[:2], member["id"], 1, key[2])
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM combat_group_members WHERE map_id=%s AND instance_id=%s "
                "AND monster_id=%s",
                (*key[:2], member["id"]),
            )
            timer_count = db.execute(
                "SELECT count(*) AS count FROM monster_reproduction_timers "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s",
                (*key[:2], member["id"]),
            ).fetchone()["count"]
            receipt_count = db.execute(
                "SELECT count(*) AS count FROM monster_reproduction_receipts "
                "WHERE map_id=%s AND instance_id=%s AND monster_id=%s",
                (*key[:2], member["id"]),
            ).fetchone()["count"]
        self.assertEqual(0, timer_count)
        self.assertEqual(1, receipt_count)

    def test_receipt_requires_child_id_and_group_id_as_a_pair(self):
        self._receipt(1134, 0, -99101, 1, 99101)
        for child_id, child_group_id in ((-5, None), (None, 5)):
            with self.subTest(child_id=child_id, child_group_id=child_group_id):
                with self.assertRaises(Exception):
                    self._receipt(
                        1134,
                        0,
                        -99102,
                        1,
                        99101,
                        child_id=child_id,
                        child_group_id=child_group_id,
                    )

    def test_outbox_rejects_missing_receipt_and_ack_is_group_specific(self):
        with self.store.connection() as db:
            with self.assertRaises(Exception):
                db.execute(
                    "INSERT INTO monster_reproduction_outbox"
                    "(map_id,instance_id,monster_id,cycle,group_id,revision,new_group) "
                    "VALUES(1134,0,-99201,1,99201,1,false)"
                )
        child = owned_instance(
            6, REFERENCES[6]["min_level"], -99202, map_id=1134, x=1, y=0, z=0
        )
        self._receipt(
            1134,
            0,
            -99201,
            1,
            99201,
            child_id=-99202,
            child_group_id=99202,
            child=child,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO monster_reproduction_outbox"
                "(map_id,instance_id,monster_id,cycle,group_id,revision,new_group) "
                "VALUES(1134,0,-99201,1,99201,3,false),"
                "(1134,0,-99201,1,99202,1,true)"
            )
            db.execute(
                "UPDATE monster_reproduction_outbox SET published=true "
                "WHERE map_id=1134 AND instance_id=0 AND monster_id=-99201 "
                "AND cycle=1 AND group_id=99201"
            )
            rows = db.execute(
                "SELECT group_id,published,new_group FROM monster_reproduction_outbox "
                "WHERE map_id=1134 AND instance_id=0 AND monster_id=-99201 AND cycle=1 "
                "ORDER BY group_id"
            ).fetchall()
        self.assertEqual(
            [(99201, True, False), (99202, False, True)],
            [(row["group_id"], row["published"], row["new_group"]) for row in rows],
        )


if __name__ == "__main__":
    unittest.main()
