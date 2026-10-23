"""Actual persistent group retirement on finite developer encounter boundaries."""
import unittest
from test_item_test_spawns_postgres import NativeItemTestSpawnsPostgresTests
from wakfu_server import item_test_spawns
from wakfu_server.monsters import reference, owned_instance
from wakfu_server.npc_actor_identity import allocate_block


class DeveloperTestGroupBoundaryTests(NativeItemTestSpawnsPostgresTests):
    def _leased_pair(self):
        result = self._use()
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            identity = allocate_block(db, 1)
            member = owned_instance(
                4,
                reference(4)["min_level"],
                -identity,
                map_id=1134,
                instance_id=0,
                x=20,
                y=20,
                z=0,
            )
            ordinary = self.groups.register_transaction(db, 1134, 0, identity, [member])
        test_lease, _ = self.groups.claim(result["key"], self.generation, fight)
        ordinary_lease, _ = self.groups.claim(ordinary, self.generation, fight)
        return result["key"], ordinary, test_lease, ordinary_lease, fight

    def test_finite_groups_retire_on_loss_session_release_and_startup_recovery(self):
        for boundary in ("finish", "release", "recover"):
            with self.subTest(boundary=boundary):
                (
                    test_key,
                    normal_key,
                    test_lease,
                    normal_lease,
                    fight,
                ) = self._leased_pair()
                if boundary == "finish":
                    self.assertTrue(self.groups.finish(test_lease, defeated=False))
                    self.assertTrue(self.groups.finish(normal_lease, defeated=False))
                    self.assertFalse(self.groups.finish(test_lease, defeated=False))
                elif boundary == "release":
                    released = self.groups.release_session(self.generation)
                    self.assertEqual([normal_key], [row["key"] for row in released])
                else:
                    self.assertEqual(2, self.groups.recover_reservations())
                with self.store.connection() as db:
                    dummy = db.execute(
                        "SELECT g.status,g.fight_id,t.ended_at FROM combat_groups g "
                        "JOIN developer_item_test_groups t USING(map_id,instance_id,group_id) "
                        "WHERE g.map_id=%s AND g.instance_id=%s AND g.group_id=%s",
                        test_key,
                    ).fetchone()
                    normal = db.execute(
                        "SELECT status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                        normal_key,
                    ).fetchone()
                    self.assertEqual("defeated", dummy["status"])
                    self.assertIsNone(dummy["fight_id"])
                    self.assertIsNotNone(dummy["ended_at"])
                    self.assertEqual("available", normal["status"])
                    # No explicit classifier ran before the tested boundary.
                    self.assertIsNotNone(
                        db.execute(
                            "SELECT 1 FROM developer_item_test_fights WHERE fight_id=%s",
                            (fight,),
                        ).fetchone()
                    )
                    self.assertTrue(item_test_spawns.is_fight(db, fight))
                with self.assertRaisesRegex(ValueError, "Finite developer"):
                    self.groups.respawn(test_key)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(
        [
            DeveloperTestGroupBoundaryTests(
                "test_finite_groups_retire_on_loss_session_release_and_startup_recovery"
            )
        ]
    )
