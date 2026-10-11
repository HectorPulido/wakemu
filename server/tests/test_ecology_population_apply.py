"""Durable ecology expiry and startup-publication retry contracts."""
from types import SimpleNamespace
from threading import RLock
import unittest

from postgres_case import PostgresCase
from wakfu_server import ecology_population, monster_corpses, monster_initial_population
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.monsters import owned_instance


class EcologyPopulationApplyTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.groups = PersistentGroups(self.store)

    def _corpse(self):
        member = owned_instance(
            5525, 1, -201, map_id=1134, instance_id=7, x=-7, y=-7, z=-1
        )
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            monster_corpses.retain(
                db,
                SimpleNamespace(
                    id=fight_id,
                    phase="finished",
                    actors={-201: SimpleNamespace(hp=0, controlled=False)},
                ),
                (member,),
            )
            corpse_id = db.execute(
                "SELECT actor_id FROM monster_corpses WHERE fight_id=%s", (fight_id,)
            ).fetchone()["actor_id"]
            db.execute(
                "UPDATE monster_corpses SET created_at=created_at-INTERVAL '2 hours', "
                "expires_at=expires_at-INTERVAL '2 hours' WHERE actor_id=%s",
                (corpse_id,),
            )
        with self.store.connection() as db:
            return dict(monster_corpses.due_expiries(db)[0], kind="corpse_expiry")

    def _corpse_row(self, actor_id):
        with self.store.connection() as db:
            return db.execute(
                "SELECT * FROM monster_corpses WHERE actor_id=%s", (actor_id,)
            ).fetchone()

    def test_expiry_prepare_is_read_only_and_failed_emit_retries(self):
        proposal = self._corpse()
        actor_id = proposal["actor_id"]
        self.assertFalse(self._corpse_row(actor_id)["expiry_published"])

        with self.assertRaisesRegex(RuntimeError, "delivery failed"):
            with self.store.connection() as db, db.transaction():
                self.assertEqual(
                    monster_corpses.publish_expiry(
                        db,
                        proposal,
                        lambda *_: (_ for _ in ()).throw(
                            RuntimeError("delivery failed")
                        ),
                    ),
                    "applied",
                )
        self.assertFalse(self._corpse_row(actor_id)["expiry_published"])

        sent = []
        with self.store.connection() as db, db.transaction():
            self.assertEqual(
                monster_corpses.publish_expiry(
                    db, proposal, lambda *args: sent.append(args)
                ),
                "applied",
            )
        self.assertEqual(len(sent), 1)
        self.assertTrue(self._corpse_row(actor_id)["expiry_published"])
        with self.store.connection() as db, db.transaction():
            self.assertEqual(
                monster_corpses.publish_expiry(
                    db, proposal, lambda *_: self.fail("duplicate emit")
                ),
                "stale",
            )

    def test_stale_expiry_proposal_never_emits_or_acknowledges(self):
        proposal = self._corpse()
        actor_id = proposal["actor_id"]
        proposal["expires_at"] = "2000-01-01T00:00:00+00:00"
        with self.store.connection() as db, db.transaction():
            self.assertEqual(
                monster_corpses.publish_expiry(
                    db, proposal, lambda *_: self.fail("stale emit")
                ),
                "stale",
            )
        self.assertFalse(self._corpse_row(actor_id)["expiry_published"])

    def test_initial_population_prepared_plan_is_idempotent_and_publication_retries(
        self,
    ):
        plan = monster_initial_population.configured_plans()[0]
        prepared = monster_initial_population.prepare_zone(self.store, plan)
        self.assertIsNotNone(prepared)
        proposal = dict(prepared, kind="initial_population", world_epoch="boot-a")
        self.assertEqual(
            ecology_population.apply(
                self.store,
                self.groups,
                SimpleNamespace(lock=RLock()),
                object(),
                proposal,
                world_epoch="boot-a",
            ),
            "applied",
        )
        with self.store.connection() as db:
            publication = db.execute(
                "SELECT * FROM monster_initial_population_publication WHERE map_id=%s "
                "AND instance_id=%s AND region_id=%s",
                tuple(plan[key] for key in ("map_id", "instance_id", "region_id")),
            ).fetchone()
        pending = dict(publication, kind="initial_publish", world_epoch="boot-a")

        with self.assertRaisesRegex(RuntimeError, "delivery failed"):
            monster_initial_population.publish_prepared(
                self.store,
                pending,
                lambda *_: (_ for _ in ()).throw(RuntimeError("delivery failed")),
            )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT published_at FROM monster_initial_population_publication "
                    "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
                    tuple(plan[key] for key in ("map_id", "instance_id", "region_id")),
                ).fetchone()["published_at"]
            )

        sent = []
        self.assertEqual(
            monster_initial_population.publish_prepared(
                self.store, pending, lambda *args: sent.append(args)
            ),
            "applied",
        )
        self.assertEqual(len(sent), 1)
        self.assertEqual([packet[0] for packet in sent[0][2]], [12304, 12608])
        self.assertEqual(
            monster_initial_population.publish_prepared(
                self.store, pending, lambda *_: self.fail("duplicate emit")
            ),
            "stale",
        )

    def test_stale_world_epoch_cannot_acquire_live_locks(self):
        class LockProbe:
            def __init__(self):
                self.entered = False

            def __enter__(self):
                self.entered = True
                return self

            def __exit__(self, *_):
                return False

        groups, harvests = LockProbe(), LockProbe()
        result = ecology_population.apply(
            self.store,
            groups,
            harvests,
            object(),
            {"kind": "corpse_expiry", "world_epoch": "old"},
            world_epoch="new",
        )
        self.assertEqual(result, "stale")
        self.assertFalse(groups.entered)
        self.assertFalse(harvests.entered)


if __name__ == "__main__":
    unittest.main()
