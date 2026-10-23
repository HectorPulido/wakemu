"""Exact event ownership fences ordinary ecology without erasing collisions."""
from copy import deepcopy
from threading import RLock
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import ecology_population, monster_active_clocks
from wakfu_server import monster_harvest_ecology, monster_population_capacity
from wakfu_server import (
    monster_population_cleanup,
    monster_removal_ecology,
    monster_reproduction,
)
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.objectives import environmental_group_population as population
from wakfu_server.objectives import environmental_service as service


class EnvironmentalOwnedGroupEcologyTests(unittest.TestCase):
    def test_owned_identity_excludes_ordinary_ecology_but_preserves_same_breed_wild_and_collision(
        self,
    ):
        from test_environmental_owned_group_population import (
            EnvironmentalOwnedGroupPopulationTests,
        )

        fixture = EnvironmentalOwnedGroupPopulationTests(
            methodName="test_real_atomic_owned_group_replay_lease_guard_and_foreign_group_preservation"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store, groups = fixture.store, fixture.groups
        foreign_event = fixture.profile()
        # Move the existing owned character through the public scope, then use
        # the same frozen source profile there. Public cleanup must be fenced
        # by ownership, not merely by the fixture's private-instance exclusion.
        fixture.world.leave(fixture.character["id"], fixture.generation)
        with store.connection() as db:
            db.execute(
                "UPDATE characters SET instance_id=0 WHERE id=%s",
                (fixture.character["id"],),
            )
        fixture.character = store.character(fixture.account, fixture.character["id"])
        fixture.world.join(fixture.generation, object(), fixture.character)
        admitted = service.refresh(
            store,
            fixture.account,
            fixture.generation,
            fixture.character["id"],
            location=dict(map_id=1134, instance_id=0, region_id=79001),
            now_ms=fixture.now,
        )
        event_id = next(
            e["instance_id"]
            for e in admitted["instances"]
            if e["profile_key"] == "owned-group"
        )
        with store.connection() as db:
            event = dict(
                db.execute(
                    "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                    (event_id,),
                ).fetchone()
            )
            owned_keys = population.populate(db, event, groups, now_ms=fixture.now)
            self.assertEqual(len(owned_keys), 1)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_owned_groups WHERE instance_id=%s",
                    (foreign_event["instance_id"],),
                ).fetchone()["n"],
                0,
            )
            owned = deepcopy(
                db.execute(
                    "SELECT members FROM combat_groups WHERE map_id=1134 "
                    "AND instance_id=0 AND group_id=%s",
                    (owned_keys[0][2],),
                ).fetchone()["members"]
            )
        reference = fixture.reference
        point = fixture.points[3]
        wild = owned_instance(
            reference,
            REFERENCES[reference]["min_level"],
            -990001,
            map_id=1134,
            instance_id=0,
            x=point[0],
            y=point[1],
            z=point[2],
        )
        wild_key = groups.register(1134, 0, 990001, [wild])
        owned_ids = {m["id"] for m in owned}
        self.assertEqual({m["ref"] for m in owned}, {wild["ref"]})
        family = REFERENCES[reference]["family_id"]

        def counts(db):
            state = ecology_population.snapshot(db, 1134, 0, kinds=("monster",))
            self.assertTrue(state["complete"])
            return state["regions"][79001]["monster"][family]

        def ecology_state(db):
            return dict(
                db.execute(
                    "SELECT ecology_value,ecology_revision FROM characters WHERE id=%s",
                    (fixture.character["id"],),
                ).fetchone()
            )

        with store.connection() as db:
            before = ecology_state(db)
            self.assertEqual(counts(db), 1)
            capacity = monster_population_capacity.snapshot(db, 1134, 0)
            self.assertEqual((capacity["members"], capacity["group_count"]), (1, 1))
            self.assertEqual({g["group_id"] for g in capacity["groups"]}, {wild_key[2]})
            # Supplied planner snapshots must obey the same ecological fence.
            supplied = list(
                db.execute(
                    "SELECT group_id,members FROM combat_groups WHERE map_id=1134 AND instance_id=0"
                )
            )
            self.assertEqual(
                monster_population_capacity.snapshot(db, 1134, 0, groups=supplied)[
                    "members"
                ],
                1,
            )
            physical = monster_population_capacity.physical_cells(db, 1134, 0)
            for member in owned + [wild]:
                self.assertIn(tuple(member[k] for k in ("x", "y", "z")), physical)
            self.assertEqual(
                monster_harvest_ecology.change(
                    db,
                    fixture.character["id"],
                    owned[0],
                    operation="event-owned-harvest",
                ),
                [],
            )
            self.assertEqual(ecology_state(db), before)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM personal_ecology_receipts"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_national_earning_receipts"
                ).fetchone()["n"],
                0,
            )

        configuration = dict(
            interval_ms=1000,
            birth_probability=1.0,
            birth_stage_decay=1.0,
            new_group_probability=0.0,
            max_members=8,
            max_zone_members=100,
            max_zone_groups=100,
        )
        # Seed a stale ordinary timer to prove the observer removes it as well
        # as refusing to create clocks for newly observed event-owned actors.
        with store.connection() as db:
            for table in ("monster_maturation_timers", "monster_reproduction_timers"):
                db.execute(
                    f"INSERT INTO {table}(map_id,instance_id,monster_id,reference,remaining_ms) "
                    "VALUES(1134,0,%s,%s,1000)",
                    (owned[0]["id"], reference),
                )
        for table in ("monster_maturation_timers", "monster_reproduction_timers"):
            monster_active_clocks.observe(
                store,
                1134,
                0,
                present=True,
                generation="owned-ecology-test",
                now_ms=fixture.now,
                table=table,
                eligible_refs={reference},
                policy_provider=lambda _: configuration,
            )
            with store.connection() as db:
                self.assertEqual(
                    {
                        r["monster_id"]
                        for r in db.execute(
                            f"SELECT monster_id FROM {table} WHERE map_id=1134 AND instance_id=0"
                        )
                    },
                    {wild["id"]},
                )
        draw = Mock(
            side_effect=AssertionError(
                "Owned actors must not consume an ordinary birth draw"
            )
        )
        ticket = dict(
            map_id=1134,
            instance_id=0,
            group_id=owned_keys[0][2],
            monster_id=owned[0]["id"],
            reference=reference,
            cycle=1,
        )
        self.assertIsNone(
            monster_reproduction.attempt(
                store,
                ticket,
                present=True,
                indexed={},
                draw=draw,
                group_draw=draw,
                choose=draw,
                configuration=configuration,
            )
        )
        draw.assert_not_called()
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM monster_reproduction_receipts"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM combat_groups WHERE map_id=1134 AND instance_id=0"
                ).fetchone()["n"],
                2,
            )

        # A deliberately stale cleanup proposal has already passed the native
        # surface classifier. Even then its exact owned group must be refused.
        harvests = SimpleNamespace(lock=RLock(), targets={})
        world = SimpleNamespace(emit_location_batch=Mock())
        proposal = dict(
            kind="cleanup_unassigned",
            world_epoch="owned-ecology-test",
            scope=[1134, 0],
            group_id=owned_keys[0][2],
            expected_members=owned,
            actor_ids=[m["id"] for m in owned],
        )
        with patch.object(
            monster_population_cleanup, "certified_unassigned", return_value=True
        ):
            result = monster_population_cleanup.apply(
                store,
                groups,
                harvests,
                world,
                proposal,
                world_epoch="owned-ecology-test",
            )
        self.assertEqual(result, {"status": "environmental_owned"})
        world.emit_location_batch.assert_not_called()
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT members FROM combat_groups WHERE map_id=1134 AND instance_id=0 "
                    "AND group_id=%s",
                    (owned_keys[0][2],),
                ).fetchone()["members"],
                owned,
            )

        def lease(key):
            with store.connection() as db:
                identity = db.execute(
                    "INSERT INTO combat_fights(status,fight_kind) VALUES('active','pve') RETURNING id"
                ).fetchone()["id"]
            return groups.claim(key, fixture.generation, identity)[0]

        owned_lease = lease(owned_keys[0])
        settled = monster_removal_ecology.finish(
            store,
            groups,
            owned_lease,
            character_id=fixture.character["id"],
            defeated=True,
        )
        self.assertEqual(settled, dict(applied=True, packets=[], receipts=[]))
        self.assertFalse(
            monster_removal_ecology.finish(
                store,
                groups,
                owned_lease,
                character_id=fixture.character["id"],
                defeated=True,
            )["applied"]
        )
        with store.connection() as db:
            self.assertEqual(ecology_state(db), before)
            self.assertEqual(counts(db), 1)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM personal_ecology_receipts"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_national_earning_receipts"
                ).fetchone()["n"],
                0,
            )
        # The same native breed remains ordinary when its identity is not owned:
        # a real lease finish runs normal ecological receipt generation.
        wild_result = monster_removal_ecology.finish(
            store,
            groups,
            lease(wild_key),
            character_id=fixture.character["id"],
            defeated=True,
        )
        self.assertTrue(wild_result["applied"])
        self.assertEqual(len(wild_result["receipts"]), 1)
        self.assertEqual(
            (
                wild_result["receipts"][0]["evidence"]["before_population"],
                wild_result["receipts"][0]["evidence"]["after_population"],
            ),
            (1, 0),
        )
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM personal_ecology_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                ecology_state(db)["ecology_revision"], before["ecology_revision"] + 1
            )
            self.assertEqual(
                {
                    r["monster_id"]
                    for r in db.execute(
                        "SELECT monster_id FROM "
                        "environmental_owned_group_members WHERE instance_id=%s",
                        (event_id,),
                    )
                },
                owned_ids,
            )
