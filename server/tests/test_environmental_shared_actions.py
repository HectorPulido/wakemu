"""Real group leases credit every winning owner and advance the world once."""
from dataclasses import replace
from types import SimpleNamespace

from wakfu_server import health_store
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.achievements import combat_adapter
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives import environmental_gameplay as gameplay
from test_environmental_group_wins import EnvironmentalGroupWinTests


class EnvironmentalSharedActionTests(EnvironmentalGroupWinTests):
    def collaborators(self, required):
        account = self.store.register("environmental-other-owner", "test-password")[
            "id"
        ]
        other = self.store.create_character(account, "Other Winner")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, other["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (self.map_id, self.world_instance, *self.points[0], other["id"]),
            )
        other = health_store.initialize(self.store, account, generation, other["id"])
        self.world.join(generation, object(), other)
        self.other, self.other_generation = other, generation
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES('shared-group',1,'group_defeat','collaborative',%s,%s,60000,%s,1,245,'test-only',%s,%s)",
                (self.map_id, self.region, self.now_ms - 1000, "0" * 64, "1" * 64),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES('shared-group',1,'win','group_defeat',2643,NULL,NULL,'interaction',%s)",
                (required,),
            )
            db.execute(
                "INSERT INTO environmental_profile_group_composition VALUES('shared-group',1,2643,5008,2,'test-only')"
            )
            db.execute(
                "INSERT INTO environmental_profile_bindings VALUES('shared-group',1,'existing_declared_groups','test-only')"
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES('shared-group',1,0,'xp',NULL,100,'test-only')"
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key='shared-group'"
            )
        first = self.refresh()["instances"][0]["instance_id"]
        from wakfu_server.objectives import environmental_service

        environmental_service.refresh(
            self.store, account, generation, other["id"], location=self.location
        )
        return first

    def group(self, identity):
        originals = [
            owned_instance(
                5008,
                REFERENCES[5008]["min_level"],
                -identity * 100 - index,
                map_id=self.map_id,
                instance_id=self.world_instance,
                x=point[0],
                y=point[1],
                z=point[2],
            )
            for index, point in enumerate(self.points[:2])
        ]
        self.registry.register(self.map_id, self.world_instance, identity, originals)
        return originals

    def win(self, group_id, originals):
        members = [self.character, self.other]
        with self.store.connection() as db:
            fid = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES('active','pve') RETURNING id"
            ).fetchone()["id"]
            for member in members:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                    (fid, member["id"], member["account_id"]),
                )
        lease, _ = self.registry.claim(
            (self.map_id, self.world_instance, group_id), self.generation, fid
        )
        actor = lambda controlled, team, hp, owner=0: SimpleNamespace(
            controlled=controlled, team=team, hp=hp, owner_id=owner
        )
        actors = {m["id"]: actor(True, 0, 1, m["account_id"]) for m in members}
        actors.update({m["id"]: actor(False, 1, 0) for m in originals})
        fight = SimpleNamespace(
            id=fid,
            phase="finished",
            winner=0,
            actors=actors,
            native_summon_registrations={},
        )
        participants = [
            dict(account_id=m["account_id"], character_id=m["id"]) for m in members
        ]
        scene = dict(
            map_id=self.map_id, instance_id=self.world_instance, group_lease=lease
        )
        with self.store.connection() as db:
            for member, generation in (
                (self.character, self.generation),
                (self.other, self.other_generation),
            ):
                self.store.lock_character(
                    db, member["account_id"], generation, member["id"]
                )
            self.assertTrue(self.registry.finish(lease, defeated=True, db=db))
            db.execute("UPDATE combat_fights SET status='finished' WHERE id=%s", (fid,))
            result = combat_adapter.settle_participants(
                db,
                self.store,
                fight,
                participants,
                originals,
                environmental_scene=scene,
            )
            replay = combat_adapter.settle_participants(
                db,
                self.store,
                fight,
                participants,
                originals,
                environmental_scene=scene,
            )
            self.assertEqual(replay["environmental_updates"], ())
        return result

    def test_one_original_group_never_counts_twice_for_two_winning_owners(self):
        originals = self.group(777)
        second = self.group(778)
        event = self.collaborators(required=2)
        result = self.win(777, originals)
        self.assertEqual(len(result["environmental_updates"]), 2)
        with self.store.connection() as db:
            self.assertEqual(storage._progress(db, dict(instance_id=event)), {"win": 1})
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_shared_actions"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_fact_receipts"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT state FROM environmental_event_instances"
                ).fetchone()["state"],
                "active",
            )
            # Core-ledger malformed batch: inconsistent projections roll back
            # every personal/shared insert before the next real group settles.
            fact = gameplay.GameplayFact(
                "group_defeated",
                "fight:999:group:777",
                self.account,
                self.character["id"],
                self.map_id,
                self.world_instance,
                "group",
                777,
                2643,
                int(self.store.clock() * 1000),
                region_id=self.region,
                fight_id=999,
            )
            with self.assertRaisesRegex(
                ValueError, "between participants"
            ), db.transaction():
                gameplay.consume(
                    db,
                    [
                        fact,
                        replace(
                            fact,
                            character_id=self.other["id"],
                            account_id=self.other["account_id"],
                            quantity=2,
                        ),
                    ],
                )
            self.assertEqual(storage._progress(db, dict(instance_id=event)), {"win": 1})
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_fact_receipts"
                ).fetchone()["n"],
                2,
            )
        self.win(778, second)
        with self.store.connection() as db:
            self.assertEqual(storage._progress(db, dict(instance_id=event)), {"win": 2})
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                2,
            )

    def test_terminal_original_group_rewards_every_winning_owner_in_same_batch_once(
        self,
    ):
        originals = self.group(777)
        event = self.collaborators(required=1)
        self.win(777, originals)
        with self.store.connection() as db:
            self.assertEqual(storage._progress(db, dict(instance_id=event)), {"win": 1})
            rows = db.execute(
                "SELECT character_id FROM environmental_reward_entitlements ORDER BY character_id"
            ).fetchall()
            self.assertEqual(
                [r["character_id"] for r in rows],
                sorted([self.character["id"], self.other["id"]]),
            )
            self.assertEqual(
                db.execute(
                    "SELECT state FROM environmental_event_instances"
                ).fetchone()["state"],
                "completed",
            )
        from wakfu_server.objectives import environmental_service

        for member, generation in (
            (self.character, self.generation),
            (self.other, self.other_generation),
        ):
            first = environmental_service.refresh(
                self.store,
                member["account_id"],
                generation,
                member["id"],
                location=self.location,
            )
            self.assertEqual(len(first["rewards"]["delivered"]), 1)
            self.assertEqual(
                environmental_service.refresh(
                    self.store,
                    member["account_id"],
                    generation,
                    member["id"],
                    location=self.location,
                )["rewards"]["delivered"],
                [],
            )
