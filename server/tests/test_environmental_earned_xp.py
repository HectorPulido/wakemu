"""Earned environmental XP freezes the canonical rate for each owned player."""
import struct
import unittest
from unittest.mock import patch

from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives import environmental_xp


class EnvironmentalEarnedXpTests(unittest.TestCase):
    def test_owned_main_and_hero_freeze_rate_before_claim_rollback_and_reconnect(self):
        from test_environmental_company import EnvironmentalCompanyPostgresTests
        from wakfu_server import resource_collect
        from wakfu_server.achievements import rewards

        fixture = EnvironmentalCompanyPostgresTests(
            "test_actual_harvest_credits_loaded_players_once_globally_and_never_replays"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        flora, store = fixture.flora, fixture.store
        main, hero = flora.character["id"], fixture.hero["id"]
        excluded = fixture.low["id"]
        identities = [main, hero, excluded]
        account = flora.account
        now = int(flora.clock[0] * 1000)
        key, authority, base = (
            "earned-rate-race",
            "test:owned-earned-rate-boundary",
            12345,
        )
        with store.connection() as db:
            active = db.execute(
                "SELECT v.* FROM combat_reward_policy_active a JOIN combat_reward_policy_versions v USING(version) WHERE a.singleton"
            ).fetchone()
            self.assertEqual(active["xp_rate_bp"], 100000)
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,family,mode,map_id,region_id,duration_ms,anchor_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES(%s,1,'resource_collect','race',%s,%s,60000,%s,1,245,%s,%s,%s)",
                (
                    key,
                    flora.map_id,
                    flora.region_id,
                    now - 1000,
                    authority,
                    "0" * 64,
                    "1" * 64,
                ),
            )
            db.execute(
                "INSERT INTO environmental_profile_evaluation VALUES(%s,1,'first_completion',2,'commit_order',%s)",
                (key, authority),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES(%s,1,'collect','resource_collect',60,100,3,'interaction',1)",
                (key,),
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES(%s,1,0,'xp',NULL,%s,%s)",
                (key, base, authority),
            )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key=%s",
                (key,),
            )
        admitted = fixture.refresh()
        self.assertEqual(len(admitted["instances"]), 1)
        resource = flora._insert_resource(
            flora.region_cells[0], resource_uid=700299, stage=3
        )
        with store.connection() as db:
            event = db.execute(
                "SELECT instance_id FROM environmental_event_instances WHERE profile_key=%s",
                (key,),
            ).fetchone()["instance_id"]
            storage.register_memberships(
                db,
                event,
                [
                    dict(
                        entity_kind="resource",
                        entity_id=resource["resource_uid"],
                        reference=60,
                        source_key="earned-rate-actual-resource",
                    )
                ],
            )
        ticket = flora._resource_ticket(resource, 100)
        flora._advance_harvest()
        self.assertTrue(
            resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))[
                "applied"
            ]
        )

        def xp(current_store):
            with current_store.connection() as db:
                return {
                    row["character_id"]: row["xp"]
                    for row in db.execute(
                        "SELECT character_id,xp FROM character_progression WHERE character_id=ANY(%s)",
                        (identities,),
                    ).fetchall()
                }

        before = xp(store)
        with store.connection() as db:
            frozen = db.execute(
                "SELECT * FROM environmental_entitlement_xp_rates ORDER BY character_id"
            ).fetchall()
            self.assertEqual({row["character_id"] for row in frozen}, {main, hero})
            for row in frozen:
                self.assertEqual(
                    (
                        row["base_xp"],
                        row["xp_rate_bp"],
                        row["awarded_xp"],
                        row["policy_version"],
                    ),
                    (base, 100000, base * 10, active["version"]),
                )
            components = db.execute(
                "SELECT quantity FROM environmental_reward_components WHERE kind='xp'"
            ).fetchall()
            self.assertEqual([row["quantity"] for row in components], [base, base])
            # Publish another immutable operator policy after entitlement creation.
            db.execute(
                "INSERT INTO combat_reward_policy_versions(version,xp_rate_bp,kamas_rate_bp,conquest_rate_bp) VALUES(999,20000,10000,10000)"
            )
            db.execute(
                "UPDATE combat_reward_policy_active SET version=999 WHERE singleton"
            )
        self.assertEqual(xp(store), before, "Earning must not deliver XP")
        grant = rewards._xp

        def grant_then_fail(*args, **kwargs):
            grant(*args, **kwargs)
            raise rewards.RewardCapacity("declared post-XP delivery failure")

        with store.connection() as db, patch.object(
            rewards, "_xp", side_effect=grant_then_fail
        ):
            result = storage.claim_pending(
                db, store, account_id=account, character_id=main, now_ms=now + 10000
            )
            self.assertTrue(result["capacity_pending"])
        self.assertEqual(xp(store), before)
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements WHERE claimed_at_ms IS NULL"
                ).fetchone()["n"],
                2,
            )
        reopened = flora.reopen()
        reopened.clock = store.clock
        for current_store in (reopened, reopened):
            with current_store.connection() as db:
                for identity in identities:
                    storage.claim_pending(
                        db,
                        current_store,
                        account_id=account,
                        character_id=identity,
                        now_ms=now + 20000,
                    )
        after = xp(reopened)
        self.assertEqual(
            after,
            {
                identity: value + (base * 10 if identity in (main, hero) else 0)
                for identity, value in before.items()
            },
        )
        with reopened.connection() as db:
            receipts = db.execute(
                "SELECT character_id,owner_xp FROM environmental_claim_receipts ORDER BY character_id"
            ).fetchall()
            self.assertEqual(
                {row["character_id"]: row["owner_xp"] for row in receipts},
                {main: base * 10, hero: base * 10},
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_entitlement_xp_rates"
                ).fetchone()["n"],
                2,
            )
        self.assertFalse(
            resource_collect.complete(store, ticket, struct.pack(">Bh", 2, 3))[
                "applied"
            ]
        )
        self.assertEqual(xp(reopened), after)
        self.assertEqual(environmental_xp.scaled(1, 0), 0)
        for invalid in (True, -1, 100000000000):
            with self.assertRaises(ValueError):
                environmental_xp.scaled(base, invalid)
