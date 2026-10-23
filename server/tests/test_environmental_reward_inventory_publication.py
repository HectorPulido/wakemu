"""An earned reward must hydrate the physical bag, not only SQL/build registry."""
from types import SimpleNamespace
import struct
import unittest

from wakfu_server import heroes
from wakfu_server.inventory import bags
from wakfu_server.inventory_items import grant
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents
from wakfu_server.planting import SEEDS


class EnvironmentalRewardInventoryPublicationTests(unittest.TestCase):
    def test_owned_main_and_hero_physical_stacks_publish_absolute_bags_after_failed_send_and_reconnect(
        self,
    ):
        from test_environmental_company import EnvironmentalCompanyPostgresTests

        fixture = EnvironmentalCompanyPostgresTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        store, f = fixture.store, fixture.flora
        main, hero = f.character["id"], fixture.hero["id"]
        heroes.remove(store, f.account, f.generation, main, fixture.low["id"])
        units = {}
        for identity in (main, hero):
            actual = store.character(f.account, identity)
            base = next(c for c in actual["inventory_containers"] if c["kind"] == 0)
            self.assertEqual((base["reference"], base["capacity"]), (2175, 30))
            units[identity] = grant(
                store,
                f.account,
                f.generation,
                identity,
                reference=20605,
                quantity=2,
                container=base["uid"],
                slot=19,
                allowed_references={20605},
            )
        key = "physical-environmental-reward"
        with store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES(%s,1,'resource_plant','collaborative',%s,%s,60000,%s,1,245,'test-only claim publication boundary',%s,%s)",
                (
                    key,
                    f.map_id,
                    f.region_id,
                    int(f.clock[0] * 1000) - 1000,
                    "0" * 64,
                    "1" * 64,
                ),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES "
                "(%s,1,'plant','resource_plant',60,%s,2,'interaction',1)",
                (key, SEEDS[4275]["action_id"]),
            )
            db.execute(
                "INSERT INTO environmental_profile_bindings VALUES(%s,1,'committed_planting','test-only')",
                (key,),
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES(%s,1,0,'xp',NULL,100,'test-only'),"
                "(%s,1,1,'item',20605,5,'test-only')",
                (key, key),
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key=%s",
                (key,),
            )
        fixture.refresh()
        before = {
            identity: store.character(f.account, identity) for identity in (main, hero)
        }
        prepared, committed = fixture.plant("physical-bag-claim")
        self.assertTrue(committed["environmental_updates"])
        self.assertTrue(
            fixture.flora._plant(prepared, "physical-bag-claim")["duplicate"]
        )
        template, roster = fixture.native_template()
        batches, available = [], [False]

        def send(*args):
            batches.append(args[-1])
            return available[0]

        world = SimpleNamespace(
            scope_presence=fixture.environment.world.scope_presence, send_batch_to=send
        )
        cursor = SelectedEnvironmentalEvents(
            hero_template=template, roster_template=roster
        )

        def refresh(connection=cursor, generation=None):
            return connection.refresh(
                store,
                world,
                f.account,
                generation or f.generation,
                main,
                location=fixture.environment.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=int(f.clock[0] * 1000),
            )

        def assert_balances():
            current = {
                identity: store.character(f.account, identity)
                for identity in (main, hero)
            }
            with store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_claim_receipts"
                    ).fetchone()["n"],
                    2,
                )
                for identity in (main, hero):
                    physical = db.execute(
                        "SELECT * FROM inventory_items WHERE character_id=%s AND reference=20605",
                        (identity,),
                    ).fetchall()
                    self.assertEqual(len(physical), 1)
                    self.assertEqual(
                        (
                            physical[0]["uid"],
                            physical[0]["container"],
                            physical[0]["slot"],
                            physical[0]["quantity"],
                        ),
                        (units[identity]["uid"], units[identity]["container"], 19, 7),
                    )
                    self.assertEqual(
                        current[identity]["xp"], before[identity]["xp"] + 100
                    )
            return current

        def assert_physical_packets(batch, current):
            opcodes = [op for op, _ in batch]
            self.assertNotIn(
                12470, opcodes, "Retry must not apply additive stack deltas"
            )
            self.assertNotIn(
                12471, opcodes, "Retry must not insert an already committed UID again"
            )
            self.assertNotIn(
                13613,
                opcodes,
                "Retry publishes absolute XP, not an additive earned notification",
            )
            selected_bags = [
                body for op, body in batch if op == 13713 and body[8] == 35
            ]
            self.assertEqual(len(selected_bags), 1)
            self.assertEqual(struct.unpack(">qB", selected_bags[0][:9]), (main, 35))
            self.assertEqual(selected_bags[0][9:], bags(current[main]))
            main_item = struct.pack(">hqih", 19, units[main]["uid"], 20605, 7)
            self.assertIn(main_item, selected_bags[0][9:])
            hero_entities = [
                body
                for op, body in batch
                if op == 13046
                and struct.unpack_from(">q", body)[0] == hero
                and body[10] == 10
            ]
            self.assertEqual(len(hero_entities), 1)
            hero_bags = bags(current[hero])
            self.assertIn(hero_bags, hero_entities[0][10:])
            self.assertIn(
                struct.pack(">hqih", 19, units[hero]["uid"], 20605, 7), hero_bags
            )
            self.assertNotIn(main_item, hero_bags)
            self.assertEqual(
                [struct.unpack_from(">q", body)[0] for body in selected_bags], [main]
            )

        self.assertFalse(refresh())
        current = assert_balances()
        assert_physical_packets(batches[-1], current)
        with store.connection() as db:
            self.assertGreater(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_publication_outbox "
                    "WHERE acknowledged_at_ms IS NULL"
                ).fetchone()["n"],
                0,
            )
        # Disconnect before ACK; the new owned lease must replay committed
        # physical state, retaining UIDs and quantities and never granting twice.
        original_generation = f.generation
        fixture.environment.world.leave(main, original_generation)
        generation = store.begin_session(
            f.account, previous_generation=original_generation
        )
        store.select_character(f.account, generation, main)
        fixture.environment.world.join(
            generation, object(), store.character(f.account, main)
        )
        available[0] = True
        reconnect = SelectedEnvironmentalEvents(
            hero_template=template, roster_template=roster
        )
        self.assertTrue(refresh(reconnect, generation))
        current = assert_balances()
        assert_physical_packets(batches[-1], current)
        self.assertFalse(refresh(reconnect, generation))
        assert_balances()
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_publication_outbox "
                    "WHERE acknowledged_at_ms IS NULL"
                ).fetchone()["n"],
                0,
            )
