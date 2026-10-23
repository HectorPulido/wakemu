"""Distinct ranked result UI stays pending until its owned hero is selected."""
import struct
from types import SimpleNamespace
import unittest

from wakfu_server import resource_collect
from wakfu_server.characters import heroes
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents


class EnvironmentalCompanyResultDeliveryTests(unittest.TestCase):
    def test_ranked_hero_completed_result_survives_main_ack_switch_failed_send_and_reconnect(
        self,
    ):
        from test_environmental_company import EnvironmentalCompanyPostgresTests
        from test_environmental_reward_bands import (
            EnvironmentalRewardBandPostgresTests,
            SOURCE,
        )

        fixture = EnvironmentalCompanyPostgresTests(
            methodName="test_actual_harvest_credits_loaded_players_once_globally_and_never_replays"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store, f = fixture.store, fixture.flora
        main, hero = f.character["id"], fixture.hero["id"]
        heroes.remove(store, f.account, f.generation, main, fixture.low["id"])
        with store.connection() as db:
            self.native = [
                dict(r)
                for r in db.execute(
                    "SELECT r.reward_id,d.primary_result_index,"
                    "d.primary_reward_list,r.native_text FROM environmental_native_rewards_raw r "
                    "JOIN environmental_native_reward_display d USING(source_key,scenario_id,reward_id) "
                    "WHERE r.source_key=%s AND r.scenario_id=-2247 AND d.primary_reward_list "
                    "ORDER BY d.primary_result_index",
                    (SOURCE,),
                )
            ]
            key = "owned-hero-result"
            EnvironmentalRewardBandPostgresTests._profile(self, db, key, seal=False)
            # Native rank bands are real; scope/action/threshold1 are explicit
            # component premises, not an original full scenario victory claim.
            db.execute(
                "UPDATE environmental_runtime_profiles SET map_id=%s,region_id=%s,level_min=1,"
                "duration_ms=60000,anchor_ms=%s WHERE profile_key=%s",
                (f.map_id, f.region_id, int(f.clock[0] * 1000) - 1000, key),
            )
            db.execute(
                "UPDATE environmental_profile_objectives SET target_reference=60,action_id=100,"
                "resource_step=3,unit='interaction',required_quantity=1 WHERE profile_key=%s",
                (key,),
            )
            db.execute(
                "INSERT INTO environmental_profile_evaluation VALUES "
                "(%s,1,'score_at_deadline',1,'character_id','test-declared native rank-result component')",
                (key,),
            )
            for state, ordinal in (
                ("proposed", 0),
                ("active", 1),
                ("completed", 2),
                ("expired", 3),
                ("cancelled", 3),
            ):
                db.execute(
                    "INSERT INTO environmental_profile_publication_states VALUES(%s,1,%s,%s)",
                    (key, state, ordinal),
                )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key=%s",
                (key,),
            )
        event = fixture.refresh()["instances"][0]["instance_id"]
        resources = [
            f._insert_resource(point, resource_uid=700301 + index, stage=3)
            for index, point in enumerate(f.region_cells[:2])
        ]
        with store.connection() as db:
            storage.register_memberships(
                db,
                event,
                [
                    dict(
                        entity_kind="resource",
                        entity_id=r["resource_uid"],
                        reference=60,
                        source_key="two-real-owned-company-harvests",
                    )
                    for r in resources
                ],
            )
            before_xp = {
                r["character_id"]: r["xp"]
                for r in db.execute(
                    "SELECT character_id,xp FROM character_progression WHERE character_id=ANY(%s)",
                    ([main, hero],),
                )
            }
            deadline = db.execute(
                "SELECT deadline_ms FROM environmental_event_instances WHERE instance_id=%s",
                (event,),
            ).fetchone()["deadline_ms"]
        first = f._resource_ticket(resources[0], 100)
        f._advance_harvest()
        self.assertTrue(
            resource_collect.complete(store, first, struct.pack(">Bh", 2, 3))["applied"]
        )
        # A real company change makes the second physical action main-only,
        # giving genuinely distinct scores instead of injecting ranking rows.
        heroes.remove(store, f.account, f.generation, main, hero)
        second = f._resource_ticket(resources[1], 100)
        f._advance_harvest()
        self.assertTrue(
            resource_collect.complete(store, second, struct.pack(">Bh", 2, 3))[
                "applied"
            ]
        )
        heroes.add(store, f.account, f.generation, main, hero)
        template, roster = fixture.native_template()
        batches = []
        world = SimpleNamespace(
            scope_presence=fixture.environment.world.scope_presence,
            send_batch_to=lambda *args: batches.append(args[-1]) or True,
        )
        now = deadline + 1
        selected = SelectedEnvironmentalEvents(
            hero_template=template, roster_template=roster
        )
        self.assertTrue(
            selected.refresh(
                store,
                world,
                f.account,
                f.generation,
                main,
                location=fixture.environment.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=now,
            )
        )

        def result(packets):
            bodies = [body for opcode, body in packets if opcode == 13263]
            self.assertEqual(len(bodies), 1)
            body = bodies[0]
            challenge, secondary, length = struct.unpack_from(">iib", body)
            winner = body[9 : 9 + length].decode()
            score, raw_rank, primary_index = struct.unpack_from(
                ">ihi", body, 9 + length
            )
            return challenge, secondary, winner, score, raw_rank, primary_index

        self.assertEqual(result(batches[-1]), (-2247, 0, f.character["name"], 2, 0, 0))
        updates = [
            body
            for opcode, body in batches[-1]
            if opcode == 13046 and struct.unpack(">q", body[:8])[0] == hero
        ]
        self.assertEqual([body[10] for body in updates], [10, 3])
        with store.connection() as db:
            ranking = db.execute(
                "SELECT character_id,score,display_rank FROM environmental_event_rankings "
                "WHERE instance_id=%s ORDER BY position",
                (event,),
            ).fetchall()
            self.assertEqual(
                [(r["character_id"], r["score"], r["display_rank"]) for r in ranking],
                [(main, 2, 1), (hero, 1, 2)],
            )
            completed = {
                r["character_id"]: r["acknowledged_at_ms"]
                for r in db.execute(
                    "SELECT character_id,acknowledged_at_ms FROM environmental_publication_outbox WHERE instance_id=%s AND kind='completed'",
                    (event,),
                )
            }
            self.assertIsNotNone(completed[main])
            self.assertIsNone(completed[hero])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts c "
                    "JOIN environmental_reward_entitlements e USING(entitlement_id) "
                    "WHERE e.instance_id=%s",
                    (event,),
                ).fetchone()["n"],
                2,
            )
            claimed = db.execute(
                "SELECT acknowledged_at_ms FROM environmental_publication_outbox "
                "WHERE instance_id=%s AND character_id=%s AND kind='claimed'",
                (event, hero),
            ).fetchone()
            self.assertIsNotNone(claimed["acknowledged_at_ms"])
            paid_xp = {
                r["character_id"]: r["xp"]
                for r in db.execute(
                    "SELECT character_id,xp FROM character_progression WHERE character_id=ANY(%s)",
                    ([main, hero],),
                )
            }
            expected = [
                r["base_xp"]
                for r in db.execute(
                    "SELECT base_xp FROM environmental_native_reward_display "
                    "WHERE source_key=%s AND scenario_id=-2247 AND primary_reward_list ORDER BY primary_result_index",
                    (SOURCE,),
                )
            ]
            self.assertEqual(
                [paid_xp[main] - before_xp[main], paid_xp[hero] - before_xp[hero]],
                expected[:2],
            )
        # Repeated leader polls cannot ACK or borrow the hero's distinct result.
        batches.clear()
        selected.refresh(
            store,
            world,
            f.account,
            f.generation,
            main,
            location=fixture.environment.location,
            ready=True,
            checkpoint=lambda: None,
            now_ms=now + 1,
        )
        self.assertFalse(
            any(opcode == 13263 for batch in batches for opcode, _ in batch)
        )
        switched = heroes.switch_main(store, f.account, f.generation, main, hero)
        self.assertTrue(switched["applied"])
        actual_hero = store.character(f.account, hero)
        fixture.environment.world.leave(main, f.generation)
        fixture.environment.world.join(f.generation, object(), actual_hero)
        batches.clear()
        world.send_batch_to = lambda *args: batches.append(args[-1]) or False
        hero_connection = SelectedEnvironmentalEvents(
            hero_template=template, roster_template=roster
        )
        self.assertFalse(
            hero_connection.refresh(
                store,
                world,
                f.account,
                f.generation,
                hero,
                location=fixture.environment.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=now + 2,
            )
        )
        self.assertEqual(result(batches[-1]), (-2247, 0, f.character["name"], 2, 1, 1))
        with store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT acknowledged_at_ms FROM environmental_publication_outbox "
                    "WHERE instance_id=%s AND character_id=%s AND kind='completed'",
                    (event, hero),
                ).fetchone()["acknowledged_at_ms"]
            )
        reopened = f.reopen()
        reopened.clock = store.clock
        generation = reopened.begin_session(f.account, previous_generation=f.generation)
        reopened.select_character(f.account, generation, hero)
        fixture.environment.world.leave(hero, f.generation)
        fixture.environment.world.join(
            generation, object(), reopened.character(f.account, hero)
        )
        world.send_batch_to = lambda *args: batches.append(args[-1]) or True
        resumed = SelectedEnvironmentalEvents(
            hero_template=template, roster_template=roster
        )
        self.assertTrue(
            resumed.refresh(
                reopened,
                world,
                f.account,
                generation,
                hero,
                location=fixture.environment.location,
                ready=True,
                checkpoint=lambda: None,
                now_ms=now + 3,
            )
        )
        self.assertEqual(result(batches[-1]), (-2247, 0, f.character["name"], 2, 1, 1))
        with reopened.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT acknowledged_at_ms FROM environmental_publication_outbox "
                    "WHERE instance_id=%s AND character_id=%s AND kind='completed'",
                    (event, hero),
                ).fetchone()["acknowledged_at_ms"]
            )
            self.assertEqual(
                {
                    r["character_id"]: r["xp"]
                    for r in db.execute(
                        "SELECT character_id,xp FROM character_progression WHERE character_id=ANY(%s)",
                        ([main, hero],),
                    )
                },
                paid_xp,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts c "
                    "JOIN environmental_reward_entitlements e USING(entitlement_id) WHERE e.instance_id=%s",
                    (event,),
                ).fetchone()["n"],
                2,
            )
        batches.clear()
        resumed.refresh(
            reopened,
            world,
            f.account,
            generation,
            hero,
            location=fixture.environment.location,
            ready=True,
            checkpoint=lambda: None,
            now_ms=now + 4,
        )
        self.assertFalse(
            any(opcode == 13263 for batch in batches for opcode, _ in batch)
        )
