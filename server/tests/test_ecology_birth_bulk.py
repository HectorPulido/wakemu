"""Batched births retain blocked seeds and use one durable mutation pass."""
import copy
import unittest
from unittest.mock import Mock, patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import ecology_plants, planting
from wakfu_server.planting_runtime import Plantings, monster_growth_member


def batch():
    reference = planting.SEEDS[30927]["resource_reference"]
    rows = []
    for uid in (101, 102, 103):
        resource = dict(
            resource_uid=uid,
            map_id=1134,
            instance_id=0,
            x=uid,
            y=2,
            z=0,
            resource_reference=reference,
            stage=1,
            creation_time=0,
        )
        rows.append(
            dict(
                kind="resource_growth",
                world_epoch="boot",
                expected=resource,
                transition=None,
                member=monster_growth_member(resource, planting.RESOURCES[reference]),
            )
        )
    return dict(kind="resource_growth_bulk", world_epoch="boot", resources=rows)


class BirthBulkValidationTests(unittest.TestCase):
    def test_invalid_batch_is_rejected_before_mutation(self):
        original = batch()
        invalid = []
        duplicate = copy.deepcopy(original)
        duplicate["resources"][1] = duplicate["resources"][0]
        invalid.append(duplicate)
        oversized = copy.deepcopy(original)
        oversized["resources"] = [original["resources"][0]] * 65
        invalid.append(oversized)
        foreign = copy.deepcopy(original)
        foreign["resources"][-1]["world_epoch"] = "previous"
        invalid.append(foreign)
        huge = copy.deepcopy(original)
        huge["padding"] = "x" * (224 * 1024)
        invalid.append(huge)
        wrong_location = copy.deepcopy(original)
        wrong_location["resources"][-1]["member"]["x"] += 1
        invalid.append(wrong_location)
        for proposal in invalid:
            with self.subTest(proposal_size=len(proposal["resources"])):
                runtime = Mock(ecology_world_epoch="boot", growth_seconds=30)
                runtime.store.clock.return_value = 1000
                with self.assertRaises(ValueError):
                    ecology_plants.apply(
                        runtime,
                        object(),
                        proposal,
                        authorize_spawn=lambda _: True,
                        publish=Mock(),
                    )
                runtime.apply_growth_candidates.assert_not_called()
                runtime.publish_growth.assert_not_called()

    def test_old_world_epoch_does_not_enter_live_authorization(self):
        runtime = Mock(ecology_world_epoch="new")
        authorize = Mock(side_effect=AssertionError("Stale plan entered world"))
        result = ecology_plants.apply(
            runtime, object(), batch(), authorize_spawn=authorize, publish=Mock()
        )
        self.assertEqual(result["reason"], "stale_world_epoch")
        runtime.apply_growth_candidates.assert_not_called()
        runtime.publish_growth.assert_not_called()


class BirthBulkPersistenceTests(PostgresCase):
    def test_partial_occupied_and_capacity_keep_exact_seeds_in_one_sql_pass(self):
        proposal = batch()
        with self.store.connection() as db:
            policy = db.execute(
                "SELECT value FROM settings WHERE name='monster_reproduction'"
            ).fetchone()["value"]
            policy.update(max_zone_members=1, max_zone_groups=1)
            db.execute(
                "UPDATE settings SET value=%s WHERE name='monster_reproduction'",
                (Jsonb(policy),),
            )
            for row in proposal["resources"]:
                db.execute(
                    "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    tuple(row["expected"].values()),
                )
        runtime = Plantings(self.store)
        runtime.ecology_world_epoch = "boot"
        self.store.clock = lambda: 1000
        with patch.object(
            runtime, "apply_growth_candidates", wraps=runtime.apply_growth_candidates
        ) as mutate, patch.object(
            runtime, "publish_growth", return_value=[]
        ) as publish:
            result = ecology_plants.apply(
                runtime,
                object(),
                proposal,
                authorize_spawn=lambda resource: resource["resource_uid"] != 101,
                publish=Mock(),
            )
        self.assertTrue(result["applied"])
        self.assertEqual(result["resource_failures"], [101, 103])
        self.assertEqual(mutate.call_count, 1)
        self.assertEqual(
            [item[0]["resource_uid"] for item in mutate.call_args.args[0]], [102, 103]
        )
        self.assertEqual(publish.call_args.kwargs["resource_uids"], [101, 102, 103])
        self.assertEqual(publish.call_args.kwargs["limit"], 64)
        with self.store.connection() as db:
            seeds = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM planted_resources ORDER BY resource_uid"
                ).fetchall()
            ]
            self.assertEqual(
                seeds, [proposal["resources"][index]["expected"] for index in (0, 2)]
            )
            outbox = db.execute(
                "SELECT resource_uid, published FROM planting_growth_outbox ORDER BY resource_uid"
            ).fetchall()
            self.assertEqual(
                [(row["resource_uid"], row["published"]) for row in outbox],
                [(102, False)],
            )
        # The same plan cannot consume another seed while its first unpublished
        # birth still reserves the map's only slot, including after reopening.
        reopened = Plantings(self.reopen())
        reopened.ecology_world_epoch = "boot"
        reopened.store.clock = lambda: 1000
        with patch.object(reopened, "publish_growth", return_value=[]):
            replay = ecology_plants.apply(
                reopened,
                object(),
                proposal,
                authorize_spawn=lambda resource: resource["resource_uid"] != 101,
                publish=Mock(),
            )
        self.assertEqual(replay["reason"], "capacity")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM planting_growth_outbox"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM planted_resources").fetchone()[
                    "n"
                ],
                2,
            )

    def test_blocked_first_sixty_four_do_not_starve_next_seed_or_reroll_after_restart(
        self,
    ):
        reference = planting.SEEDS[30927]["resource_reference"]
        resources = [
            dict(
                resource_uid=uid,
                map_id=1134,
                instance_id=0,
                x=uid,
                y=2,
                z=0,
                resource_reference=reference,
                stage=1,
                creation_time=0,
            )
            for uid in range(1, 66)
        ]
        with self.store.connection() as db:
            for row in resources:
                db.execute(
                    "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    tuple(row.values()),
                )
        occupied = {(1134, 0, row["x"], row["y"], row["z"]) for row in resources[:64]}
        snapshot = dict(world_epoch="cursor-test", now_ms=1000000)
        ecology_plants._CURSORS.pop("cursor-test", None)
        self.addCleanup(ecology_plants._CURSORS.pop, "cursor-test", None)
        self.assertEqual(
            ecology_plants._prepare_birth_batch(
                self.store, snapshot, [reference], 30, occupied
            ),
            [],
        )
        second = ecology_plants._prepare_birth_batch(
            self.store, snapshot, [reference], 30, occupied
        )
        self.assertEqual(
            [r["expected"]["resource_uid"] for r in second[0]["resources"]], [65]
        )
        first_member = second[0]["resources"][0]["member"]
        ecology_plants._CURSORS.pop("cursor-test", None)
        reopened = self.reopen()
        ecology_plants._prepare_birth_batch(
            reopened, snapshot, [reference], 30, occupied
        )
        restarted = ecology_plants._prepare_birth_batch(
            reopened, snapshot, [reference], 30, occupied
        )
        self.assertEqual(restarted[0]["resources"][0]["member"], first_member)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM planted_resources").fetchone()[
                    "n"
                ],
                65,
            )
