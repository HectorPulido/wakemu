"""Shared event receipts, atomic rewards and reconnect against isolated SQL."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
import struct
import uuid

from postgres_case import PostgresCase
from wakfu_server import health_store
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives.environmental_gameplay import GameplayFact
from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents
from test_companion_equipment_postgres import CompanionEquipmentPostgresTests


class EnvironmentalDurableLifecycleTests(PostgresCase):
    _grant = CompanionEquipmentPostgresTests._grant
    _activate = CompanionEquipmentPostgresTests._activate

    def setUp(self):
        super().setUp()
        from wakfu_server.world import World
        from wakfu_server.objectives import environmental_presence

        self.presence_world = World(lambda _: b"", lambda _: b"", lambda *_: None)
        live = patch.object(environmental_presence, "_world", self.presence_world)
        live.start()
        self.addCleanup(live.stop)
        self.account, self.generation, self.character = self.owner()
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )
        self.now_ms = int(self.store.clock() * 1000)
        self.location = dict(map_id=527, instance_id=0, region_id=17)

    def owner(self):
        account = self.store.register("env-" + uuid.uuid4().hex[:12], "local-password")[
            "id"
        ]
        suffix = (
            uuid.uuid4().hex[:10].translate(str.maketrans("0123456789", "abcdefghij"))
        )
        character = self.store.create_character(account, "Env " + suffix)
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0 WHERE id=%s",
                (character["id"],),
            )
        character = health_store.initialize(
            self.store, account, generation, character["id"]
        )
        self.presence_world.join(generation, object(), character)
        return account, generation, character

    def profile(self, mode="solo", required=2, minimum=1, unit="interaction"):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,family,mode,map_id,region_id,duration_ms,recurrence_period_ms,anchor_ms,"
                "level_min,level_max,authority,source_sha256,catalog_revision,minimum_contribution) "
                "VALUES('test-policy',1,'resource_collect',%s,527,17,60000,120000,%s,1,245,'test-only',%s,%s,%s)",
                (mode, self.now_ms - 1000, "0" * 64, "1" * 64, minimum),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives "
                "(profile_key,version,objective_key,family,target_reference,action_id,resource_step,required_quantity,unit) "
                "VALUES('test-policy',1,'collect','resource_collect',1337,3,1,%s,%s)",
                (required, unit),
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES "
                "('test-policy',1,0,'xp',NULL,100,'test-only'),"
                "('test-policy',1,1,'item',11423,1,'test-only'),"
                "('test-policy',1,2,'kamas',NULL,7,'test-only')"
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key='test-policy'"
            )

    def admit(self, account=None, generation=None, character=None, now_ms=None):
        return service.refresh(
            self.store,
            account or self.account,
            generation or self.generation,
            (character or self.character)["id"],
            location=self.location,
            now_ms=self.now_ms if now_ms is None else now_ms,
        )

    def roster(self, instance_id, entities):
        with self.store.connection() as db:
            storage.register_memberships(
                db,
                instance_id,
                [
                    dict(
                        entity_kind="resource",
                        entity_id=n,
                        reference=1337,
                        source_key="test-spawn:" + str(n),
                    )
                    for n in entities
                ],
            )

    def fact(self, entity, *, account=None, character=None):
        return GameplayFact(
            "resource_collected",
            "harvest:" + str(entity),
            account or self.account,
            (character or self.character)["id"],
            527,
            0,
            "resource",
            entity,
            1337,
            self.now_ms + 1,
            region_id=17,
            action_id=3,
            before_step=1,
            after_step=0,
        )

    def consume(self, fact):
        with self.store.connection() as db:
            return storage.contribute(db, fact)

    def test_atomic_capacity_frozen_companions_failed_send_reconnect_and_next_cycle(
        self,
    ):
        from wakfu_server import companions
        from wakfu_server.achievements import rewards

        old, _ = self._activate()
        companions.add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", old["id"]),
        )
        self.profile()
        first = self.admit()["instances"][0]
        event = first["instance_id"]
        self.assertEqual(self.admit()["instances"][0]["instance_id"], event)
        self.roster(event, [101, 102])
        self.assertEqual(self.consume(replace(self.fact(101), instance_id=9)), ())
        self.assertEqual(self.consume(self.fact(999)), ())
        self.assertEqual(len(self.consume(self.fact(101))), 1)
        self.assertEqual(self.consume(self.fact(101)), ())
        with self.assertRaisesRegex(ValueError, "changed on replay"):
            self.consume(replace(self.fact(101), quantity=2))
        self.consume(self.fact(102))
        with self.store.connection() as db:
            entitlement = db.execute(
                "SELECT * FROM environmental_reward_entitlements"
            ).fetchone()
            self.assertIsNotNone(entitlement["companions_frozen_at_ms"])
            frozen = db.execute(
                "SELECT companion_id FROM environmental_entitlement_companions"
            ).fetchall()
            self.assertEqual([row["companion_id"] for row in frozen], [old["id"]])
            before_xp = db.execute(
                "SELECT xp FROM character_progression WHERE character_id=%s",
                (self.character["id"],),
            ).fetchone()["xp"]
            before_wallet = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (self.account,)
            ).fetchone()["kamas"]
        original = rewards.grant

        def capacity(db, store, character, reward, **kwargs):
            if reward["aeV"] == 5:
                raise rewards.RewardCapacity("test-full-inventory")
            return original(db, store, character, reward, **kwargs)

        with patch.object(rewards, "grant", side_effect=capacity):
            blocked = self.admit()["rewards"]
        self.assertEqual(blocked["capacity_pending"], [entitlement["entitlement_id"]])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["xp"],
                before_xp,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                0,
            )
        companions.remove_from_party(
            self.store, self.account, self.generation, self.character["id"], old["id"]
        )
        descriptor = next(
            row for row in companions.descriptors().values() if row["item_ref"] != 17878
        )
        item = self._grant(descriptor["item_ref"], slot=1)
        new = companions.use(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">iq", descriptor["action_id"], item["uid"]),
            in_fight=False,
        )["companion"]
        companions.add_to_party(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            struct.pack(">q", new["id"]),
        )
        connection = SelectedEnvironmentalEvents()
        batches = []
        world = SimpleNamespace(
            send_batch_to=lambda *args: batches.append(args[-1]) or False,
            scope_presence=self.presence_world.scope_presence,
        )
        self.assertFalse(
            connection.refresh(
                self.store,
                world,
                self.account,
                self.generation,
                self.character["id"],
                location=self.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=self.now_ms + 2,
            )
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (self.character["id"],),
                ).fetchone()["xp"],
                before_xp + 100,
            )
            self.assertEqual(
                db.execute(
                    "SELECT kamas FROM account_wallets WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["kamas"],
                before_wallet + 7,
            )
            xp = {
                row["id"]: row["xp"]
                for row in db.execute("SELECT id,xp FROM account_companions").fetchall()
            }
            self.assertEqual((xp[old["id"]], xp[new["id"]]), (150, 0))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertGreater(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_publication_outbox WHERE acknowledged_at_ms IS NULL"
                ).fetchone()["n"],
                0,
            )
        world.send_batch_to = lambda *args: batches.append(args[-1]) or True
        self.assertTrue(
            connection.refresh(
                self.store,
                world,
                self.account,
                self.generation,
                self.character["id"],
                location=self.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=self.now_ms + 3,
            )
        )
        self.assertIsNotNone(connection.claimed_character)
        self.assertNotIn(13613, [packet[0] for packet in batches[-1]])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_publication_outbox WHERE acknowledged_at_ms IS NULL"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                1,
            )
        next_cycle = self.admit(now_ms=self.now_ms + 120000)["instances"][0][
            "instance_id"
        ]
        self.assertNotEqual(next_cycle, event)
        self.assertEqual(
            self.consume(replace(self.fact(101), occurred_at_ms=self.now_ms + 120001)),
            (),
        )
        with self.assertRaises(ValueError):
            service.acknowledge(
                self.store,
                self.account,
                "replaced-lease",
                self.character["id"],
                ["invented"],
            )

    def test_shared_progress_rewards_only_real_contributors(self):
        other, lease, second = self.owner()
        unused, unused_lease, third = self.owner()
        self.profile(mode="collaborative", required=3)
        event = self.admit()["instances"][0]["instance_id"]
        self.assertEqual(
            self.admit(other, lease, second)["instances"][0]["instance_id"], event
        )
        self.admit(unused, unused_lease, third)
        self.roster(event, [201, 202, 203])
        self.consume(self.fact(201))
        self.consume(self.fact(202, account=other, character=second))
        self.consume(self.fact(203, account=other, character=second))
        with self.store.connection() as db:
            earned = db.execute(
                "SELECT account_id FROM environmental_reward_entitlements ORDER BY account_id"
            ).fetchall()
            self.assertEqual(
                [row["account_id"] for row in earned], sorted([self.account, other])
            )
            self.assertEqual(
                db.execute(
                    "SELECT state FROM environmental_event_instances WHERE instance_id=%s",
                    (event,),
                ).fetchone()["state"],
                "completed",
            )
            self.assertEqual(
                db.execute(
                    "SELECT sum(quantity) AS n FROM environmental_progress"
                ).fetchone()["n"],
                3,
            )
        self.assertEqual(len(self.admit()["rewards"]["delivered"]), 1)
        self.assertEqual(
            len(self.admit(other, lease, second)["rewards"]["delivered"]), 1
        )
        self.assertEqual(
            self.admit(unused, unused_lease, third)["rewards"]["delivered"], []
        )

    def test_concurrent_shared_completion_preserves_owner_lock_order(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        other, lease, second = self.owner()
        self.profile(mode="collaborative", required=3)
        event = self.admit()["instances"][0]["instance_id"]
        self.admit(other, lease, second)
        self.roster(event, [301, 302, 303, 304])
        self.consume(self.fact(301))
        self.consume(self.fact(302, account=other, character=second))
        owners_locked = Barrier(2)

        def finish(account, generation, character, entity):
            with self.store.connection() as db:
                db.execute("SET LOCAL lock_timeout='4s'")
                db.execute("SET LOCAL statement_timeout='7s'")
                service._lock_owner(
                    self.store, db, account, generation, character["id"]
                )
                owners_locked.wait(timeout=5)
                return storage.contribute(
                    db, self.fact(entity, account=account, character=character)
                )

        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [
                workers.submit(
                    finish, self.account, self.generation, self.character, 303
                ),
                workers.submit(finish, other, lease, second, 304),
            ]
            results = [future.result(timeout=15) for future in futures]
        self.assertEqual(sum(len(result) for result in results), 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_fact_receipts"
                ).fetchone()["n"],
                3,
            )
            self.assertEqual(
                db.execute(
                    "SELECT sum(quantity) AS n FROM environmental_progress"
                ).fetchone()["n"],
                3,
            )

    def test_shared_quantity_keeps_actual_contribution_when_it_crosses_the_target(self):
        other, lease, second = self.owner()
        self.profile(mode="collaborative", required=3, minimum=2, unit="quantity")
        event = self.admit()["instances"][0]["instance_id"]
        self.admit(other, lease, second)
        self.roster(event, [401, 402])
        self.consume(self.fact(401))
        self.consume(
            replace(self.fact(402, account=other, character=second), quantity=3)
        )
        with self.store.connection() as db:
            earned = db.execute(
                "SELECT account_id FROM environmental_reward_entitlements"
            ).fetchall()
            self.assertEqual([row["account_id"] for row in earned], [other])
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM environmental_progress WHERE character_id=%s",
                    (second["id"],),
                ).fetchone()["quantity"],
                3,
            )
