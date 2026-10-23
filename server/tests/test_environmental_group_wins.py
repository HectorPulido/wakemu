"""Actual durable group admission/lease plus authenticated win/hero adapters."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from postgres_case import PostgresCase
from wakfu_server.world import World
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.planting_cells import cells
from wakfu_server.combat_group_store import PersistentGroups
from wakfu_server.achievements import combat_adapter
from wakfu_server.objectives import environmental_groups as groups
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives import environmental_service as service


class EnvironmentalGroupPresenceTests(unittest.TestCase):
    def test_no_bound_group_work_without_live_map_or_admitted_lease(self):
        db = Mock()
        event = dict(map_id=1134, world_instance_id=17)
        with patch.object(presence, "_world", None):
            self.assertEqual(groups.bind_available(db, event), ())
            self.assertEqual(
                groups.winning_facts(
                    db,
                    receipt=dict(fight_id=1),
                    source_scene=dict(
                        map_id=1134,
                        instance_id=17,
                        group_lease=((1134, 17, 999), "lease", 1, 1),
                    ),
                    account_id=1,
                    character_id=1,
                    occurred_at_ms=100,
                ),
                (),
            )
        self.assertEqual(
            groups.winning_facts(
                db,
                receipt=dict(fight_id=1),
                source_scene={},
                account_id=1,
                character_id=1,
                occurred_at_ms=100,
            ),
            (),
        )
        db.execute.assert_not_called()
        world = World(lambda _: b"", lambda _: b"", lambda *_: None)
        world.join(
            "live",
            object(),
            dict(id=1, account_id=1, map_id=1134, instance_id=17, x=0, y=0, z=0),
        )
        with patch.object(presence, "_world", world):
            self.assertEqual(
                groups.bind_available(db, dict(event, state="proposed")), ()
            )
        db.execute.assert_not_called()


class EnvironmentalGroupWinTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("environmental-group", "test-password")["id"]
        self.character = self.store.create_character(self.account, "Group Winner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.map_id, self.world_instance, self.region = 1134, 17, 79001
        points = [
            (x, y, r["z"])
            for (x, y), rows in cells(self.map_id).items()
            for r in rows
            if r["region_id"] == self.region
        ]
        self.points = list(dict.fromkeys(points))[:4]
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (
                    self.map_id,
                    self.world_instance,
                    *self.points[0],
                    self.character["id"],
                ),
            )
        self.character = self.store.character(self.account, self.character["id"])
        self.world = World(lambda _: b"", lambda _: b"", lambda *_: None)
        self.world.join(self.generation, object(), self.character)
        live = patch.object(presence, "_world", self.world)
        live.start()
        self.addCleanup(live.stop)
        self.registry = PersistentGroups(self.store)
        self.now_ms = int(self.store.clock() * 1000)
        self.location = dict(
            map_id=self.map_id, instance_id=self.world_instance, region_id=self.region
        )

    def profile(self):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES('group-test',1,'group_defeat','solo',%s,%s,60000,%s,1,245,'test-only',%s,%s)",
                (self.map_id, self.region, self.now_ms - 1000, "0" * 64, "1" * 64),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES('group-test',1,'win','group_defeat',2643,NULL,NULL,'interaction',1)"
            )
            db.execute(
                "INSERT INTO environmental_profile_group_composition VALUES('group-test',1,2643,5008,2,'test-only')"
            )
            db.execute(
                "INSERT INTO environmental_profile_bindings VALUES('group-test',1,'existing_declared_groups','test-only')"
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES('group-test',1,0,'xp',NULL,100,'test-only')"
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key='group-test'"
            )

    def refresh(self):
        return service.refresh(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            location=self.location,
        )

    def create_group(self):
        originals = [
            owned_instance(
                5008,
                REFERENCES[5008]["min_level"],
                -900000 - index,
                map_id=self.map_id,
                instance_id=self.world_instance,
                x=point[0],
                y=point[1],
                z=point[2],
            )
            for index, point in enumerate(self.points[:2])
        ]
        self.registry.register(self.map_id, self.world_instance, 777, originals)
        return originals

    def finish(self, originals, *, partial=False):
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES('active','pve') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, self.character["id"], self.account),
            )
        lease, members = self.registry.claim(
            (self.map_id, self.world_instance, 777), self.generation, fight_id
        )
        actor = lambda controlled, team, hp, owner=0: SimpleNamespace(
            controlled=controlled, team=team, hp=hp, owner_id=owner
        )
        actors = {self.character["id"]: actor(True, 0, 1, self.account)}
        actors.update(
            {
                m["id"]: actor(False, 1, 10 if partial and index == 1 else 0)
                for index, m in enumerate(members)
            }
        )
        actors[-999999] = actor(
            False, 1, 0
        )  # A dynamic summon never joins the original group.
        fight = SimpleNamespace(
            id=fight_id,
            phase="finished",
            winner=0,
            actors=actors,
            native_summon_registrations={-999999: object()},
        )
        scene = dict(
            map_id=self.map_id, instance_id=self.world_instance, group_lease=lease
        )
        with self.store.connection() as db:
            self.store.lock_character(
                db, self.account, self.generation, self.character["id"]
            )
            self.assertTrue(self.registry.finish(lease, defeated=True, db=db))
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            first = combat_adapter.settle_participants(
                db,
                self.store,
                fight,
                [dict(account_id=self.account, character_id=self.character["id"])],
                originals,
                environmental_scene=scene,
            )
        return fight, scene, first

    def test_declared_real_group_binds_automatically_and_win_counts_once_not_per_monster(
        self,
    ):
        originals = self.create_group()
        self.profile()
        event = self.refresh()["instances"][0]["instance_id"]
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_group_members"
                ).fetchone()["n"],
                2,
            )
            self.assertTrue(
                groups.bind(
                    db,
                    event,
                    group_id=777,
                    group_reference=2643,
                    source_key="existing-group:777:0",
                )
            )
            with self.assertRaisesRegex(ValueError, "composition"):
                groups.bind(
                    db,
                    event,
                    group_id=777,
                    group_reference=999999,
                    source_key="wrong-template",
                )
        fight, scene, result = self.finish(originals)
        self.assertEqual(len(result["environmental_updates"]), 1)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT entity_kind,quantity FROM environmental_fact_receipts"
            ).fetchone()
            self.assertEqual((row["entity_kind"], row["quantity"]), ("group", 1))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                1,
            )
            replay = combat_adapter.settle_participants(
                db,
                self.store,
                fight,
                [dict(account_id=self.account, character_id=self.character["id"])],
                originals,
                environmental_scene=scene,
            )
            self.assertEqual(replay["environmental_updates"], ())
        self.assertEqual(len(self.refresh()["rewards"]["delivered"]), 1)
        self.assertEqual(self.refresh()["rewards"]["delivered"], [])

    def test_partial_original_win_and_stale_lease_cannot_be_promoted_to_group_victory(
        self,
    ):
        originals = self.create_group()
        self.profile()
        self.refresh()
        fight, scene, result = self.finish(originals, partial=True)
        self.assertEqual(result["environmental_updates"], ())
        with self.store.connection() as db:
            receipt = db.execute(
                "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                (self.character["id"], "fight:" + str(fight.id)),
            ).fetchone()["payload"]
            self.assertEqual(len(receipt["original_monsters"]), 1)
            forged = dict(
                receipt, original_monsters=[[m["id"], m["ref"]] for m in originals]
            )
            key, generation, fid, rev = scene["group_lease"]
            self.assertEqual(
                groups.winning_facts(
                    db,
                    receipt=forged,
                    source_scene=dict(
                        scene, group_lease=(key, generation, fid, rev + 1)
                    ),
                    account_id=self.account,
                    character_id=self.character["id"],
                    occurred_at_ms=int(self.store.clock() * 1000),
                ),
                (),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_fact_receipts"
                ).fetchone()["n"],
                0,
            )
        self.assertEqual(self.refresh()["rewards"]["delivered"], [])
