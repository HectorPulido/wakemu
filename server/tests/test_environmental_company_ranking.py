"""User-declared character winner slots through genuine owned company actions."""
import struct
import unittest

from wakfu_server.objectives import environmental_company as company
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_storage as storage


class EnvironmentalCompanyRankingPostgresTests(unittest.TestCase):
    def test_real_company_resource_race_one_and_two_character_slots_main_first(self):
        # One isolated schema, two declared races, one genuinely committed
        # resource action. No fabricated completion fact or winner injection.
        from test_environmental_company import EnvironmentalCompanyPostgresTests
        from wakfu_server import resource_collect

        fixture = EnvironmentalCompanyPostgresTests(
            methodName="test_actual_harvest_credits_loaded_players_once_globally_and_never_replays"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        flora = fixture.flora
        store = fixture.store
        members = [flora.character["id"], fixture.hero["id"], fixture.low["id"]]
        now_ms = int(flora.clock[0] * 1000)
        authority = "user-declared:each-character-occupies-one-winner-slot:2026-10-22"
        with store.connection() as db:
            self.assertEqual(
                company.loaded_ids(db, flora.account, members[0]), tuple(members[1:])
            )
            for winners in (1, 2):
                key = f"character-race-{winners}"
                db.execute(
                    "INSERT INTO environmental_runtime_profiles "
                    "(profile_key,version,family,mode,map_id,region_id,duration_ms,anchor_ms,"
                    "level_min,level_max,authority,source_sha256,catalog_revision) "
                    "VALUES(%s,1,'resource_collect','race',%s,%s,60000,%s,1,245,%s,%s,%s)",
                    (
                        key,
                        flora.map_id,
                        flora.region_id,
                        now_ms - 1000,
                        authority,
                        "0" * 64,
                        "1" * 64,
                    ),
                )
                db.execute(
                    "INSERT INTO environmental_profile_evaluation VALUES(%s,1,%s,%s,%s,%s)",
                    (key, "first_completion", winners, "commit_order", authority),
                )
                db.execute(
                    "INSERT INTO environmental_profile_objectives VALUES "
                    "(%s,1,'collect','resource_collect',60,100,3,'interaction',1)",
                    (key,),
                )
                db.execute(
                    "INSERT INTO environmental_profile_rewards VALUES "
                    "(%s,1,0,'xp',NULL,1,%s)",
                    (key, authority),
                )
                db.execute(
                    "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true "
                    "WHERE profile_key=%s",
                    (key,),
                )
        admitted = fixture.refresh()
        self.assertEqual(len(admitted["instances"]), 2)
        resource = flora._insert_resource(
            flora.region_cells[0], resource_uid=700199, stage=3
        )
        with store.connection() as db:
            events = {
                r["profile_key"]: r["instance_id"]
                for r in db.execute(
                    "SELECT profile_key,instance_id FROM environmental_event_instances"
                ).fetchall()
            }
            for event in events.values():
                storage.register_memberships(
                    db,
                    event,
                    [
                        dict(
                            entity_kind="resource",
                            entity_id=resource["resource_uid"],
                            reference=60,
                            source_key="test-real-character-race-resource",
                        )
                    ],
                )
                self.assertEqual(
                    [
                        r["character_id"]
                        for r in db.execute(
                            "SELECT character_id FROM environmental_participants WHERE instance_id=%s "
                            "AND eligible ORDER BY character_id",
                            (event,),
                        ).fetchall()
                    ],
                    sorted(members),
                )
        ticket = flora._resource_ticket(resource, 100)
        flora._advance_harvest()
        result = resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))
        self.assertTrue(result["applied"])
        self.assertEqual(len(result["environmental_updates"]), 3)

        def assert_durable_ranking(db):
            for winners in (1, 2):
                event = events[f"character-race-{winners}"]
                rows = db.execute(
                    "SELECT character_id,position,display_rank,rewarded "
                    "FROM environmental_event_rankings WHERE instance_id=%s ORDER BY position",
                    (event,),
                ).fetchall()
                self.assertEqual(
                    [
                        (
                            r["character_id"],
                            r["position"],
                            r["display_rank"],
                            r["rewarded"],
                        )
                        for r in rows
                    ],
                    [
                        (identity, index, index, True)
                        for index, identity in enumerate(members[:winners], 1)
                    ],
                )
                self.assertEqual(
                    db.execute(
                        "SELECT state FROM environmental_event_instances "
                        "WHERE instance_id=%s",
                        (event,),
                    ).fetchone()["state"],
                    "completed",
                )
                participants = db.execute(
                    "SELECT character_id,completed_at_ms FROM environmental_participants "
                    "WHERE instance_id=%s ORDER BY character_id",
                    (event,),
                ).fetchall()
                self.assertEqual(
                    {
                        r["character_id"]
                        for r in participants
                        if r["completed_at_ms"] is not None
                    },
                    set(members[:winners]),
                )
                entitlements = db.execute(
                    "SELECT character_id FROM environmental_reward_entitlements "
                    "WHERE instance_id=%s ORDER BY character_id",
                    (event,),
                ).fetchall()
                self.assertEqual(
                    {r["character_id"] for r in entitlements}, set(members[:winners])
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM environmental_fact_receipts "
                        "WHERE instance_id=%s",
                        (event,),
                    ).fetchone()["n"],
                    winners,
                )

        with store.connection() as db:
            assert_durable_ranking(db)
        # Successful physical-action replay cannot allocate another placement.
        self.assertFalse(
            resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))[
                "applied"
            ]
        )
        # Reopening storage preserves the admitted session's fixture clock;
        # using wall time would expire this otherwise genuine owned lease.
        reopened = flora.reopen()
        reopened.clock = store.clock
        with reopened.connection() as db:
            before_xp = {
                r["character_id"]: r["xp"]
                for r in db.execute(
                    "SELECT character_id,xp FROM character_progression WHERE character_id=ANY(%s)",
                    (members,),
                ).fetchall()
            }
        settled = service.refresh(
            reopened,
            flora.account,
            flora.generation,
            members[0],
            location=fixture.environment.location,
            now_ms=int(flora.clock[0] * 1000),
        )
        self.assertEqual(len(settled["rewards"]["delivered"]), 2)
        self.assertEqual(len(settled["hero_rewards"][members[1]]["delivered"]), 1)
        self.assertEqual(settled["hero_rewards"][members[2]]["delivered"], [])
        repeated = service.refresh(
            reopened,
            flora.account,
            flora.generation,
            members[0],
            location=fixture.environment.location,
            now_ms=int(flora.clock[0] * 1000),
        )
        self.assertEqual(repeated["rewards"]["delivered"], [])
        self.assertTrue(
            all(not reward["delivered"] for reward in repeated["hero_rewards"].values())
        )
        with reopened.connection() as db:
            assert_durable_ranking(db)
            after_xp = {
                r["character_id"]: r["xp"]
                for r in db.execute(
                    "SELECT character_id,xp FROM character_progression WHERE character_id=ANY(%s)",
                    (members,),
                ).fetchall()
            }
        self.assertEqual(
            [after_xp[identity] - before_xp[identity] for identity in members],
            [2, 1, 0],
        )
