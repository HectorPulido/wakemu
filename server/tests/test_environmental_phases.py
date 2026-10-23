"""Explicit proposal/active/cancel clocks and ownership-aware cleanup plans."""
from dataclasses import replace
import unittest

from wakfu_server.objectives import environmental_runtime as rules
from wakfu_server.objectives import environmental_storage as storage
from test_environmental_durable_lifecycle import EnvironmentalDurableLifecycleTests


class EnvironmentalClockTests(unittest.TestCase):
    def test_proposal_boundaries_do_not_extend_active_or_repeat_expired_one_shots(self):
        kwargs = dict(
            duration_ms=60, anchor_ms=100, recurrence_period_ms=120, proposal_ms=10
        )
        expected = {
            89: None,
            90: (0, 100, 160, "proposed"),
            99: (0, 100, 160, "proposed"),
            100: (0, 100, 160, "active"),
            159: (0, 100, 160, "active"),
            160: None,
            209: None,
            210: (1, 220, 280, "proposed"),
            220: (1, 220, 280, "active"),
        }
        for now, window in expected.items():
            with self.subTest(now=now):
                self.assertEqual(rules.admission_window(now, **kwargs), window)
        self.assertIsNone(
            rules.admission_window(160, **dict(kwargs, recurrence_period_ms=None))
        )
        self.assertIsNone(rules.admission_window(99, **dict(kwargs, proposal_ms=0)))


class EnvironmentalPhaseTests(EnvironmentalDurableLifecycleTests):
    def phased_profile(self):
        # Build the normal fixture unsealed so every publication state is frozen
        # alongside the same profile; never mutate sealed content.
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO environmental_runtime_profiles "
                "(profile_key,version,native_scenario_id,family,mode,map_id,region_id,duration_ms,"
                "anchor_ms,proposal_ms,level_min,level_max,authority,source_sha256,catalog_revision) "
                "VALUES('test-policy',1,-2311,'resource_collect','solo',527,17,60000,%s,10000,1,245,'test-only',%s,%s)",
                (self.now_ms + 5000, "0" * 64, "1" * 64),
            )
            db.execute(
                "INSERT INTO environmental_profile_objectives VALUES "
                "('test-policy',1,'collect','resource_collect',1337,3,1,'interaction',2)"
            )
            db.execute(
                "INSERT INTO environmental_profile_rewards VALUES ('test-policy',1,0,'xp',NULL,100,'test-only')"
            )
            db.execute(
                "INSERT INTO environmental_profile_publication VALUES ('test-policy',1,-2311,0,17,NULL,'remaining_ms','test-only')"
            )
            for state, ordinal in (
                ("proposed", 0),
                ("active", 1),
                ("completed", 2),
                ("expired", 2),
                ("cancelled", 2),
            ):
                db.execute(
                    "INSERT INTO environmental_profile_publication_states VALUES('test-policy',1,%s,%s)",
                    (state, ordinal),
                )
            db.execute(
                "UPDATE environmental_runtime_profiles SET sealed=true,enabled=true WHERE profile_key='test-policy'"
            )

    def test_proposal_activation_cancel_keeps_earned_rewards_and_separates_wild_cleanup(
        self,
    ):
        self.phased_profile()
        proposed = self.admit()["instances"][0]
        event = proposed["instance_id"]
        self.assertEqual(
            (
                proposed["state"],
                proposed["native_publication"]["state_ordinal"],
                proposed["native_publication"]["native_time"],
            ),
            ("proposed", 0, 5000),
        )
        with self.store.connection() as db:
            storage.register_memberships(
                db,
                event,
                [
                    dict(
                        entity_kind="resource",
                        entity_id=cid,
                        reference=1337,
                        source_key="fixture:" + str(cid),
                        spawn_owned=owned,
                    )
                    for cid, owned in ((700, False), (701, True))
                ],
            )
        self.assertEqual(self.consume(self.fact(700)), ())
        active = self.admit(now_ms=self.now_ms + 5001)["instances"][0]
        self.assertEqual(
            (active["state"], active["native_publication"]["state_ordinal"]),
            ("active", 1),
        )
        self.consume(replace(self.fact(700), occurred_at_ms=self.now_ms + 5002))
        self.consume(replace(self.fact(701), occurred_at_ms=self.now_ms + 5003))
        with self.store.connection() as db:
            self.assertTrue(
                storage.cancel(
                    db, event, reason="fixture cancellation", now_ms=self.now_ms + 5004
                )
            )
            self.assertFalse(
                storage.cancel(
                    db, event, reason="fixture cancellation", now_ms=self.now_ms + 5005
                )
            )
            actions = {
                r["entity_id"]: r["action"]
                for r in db.execute(
                    "SELECT * FROM environmental_cleanup_outbox"
                ).fetchall()
            }
            self.assertEqual(actions, {700: "release_membership", 701: "despawn_owned"})
        with self.assertRaisesRegex(ValueError, "changed on replay"):
            with self.store.connection() as db:
                storage.cancel(
                    db, event, reason="changed reason", now_ms=self.now_ms + 5006
                )
        self.assertEqual(
            len(self.admit(now_ms=self.now_ms + 5007)["rewards"]["delivered"]), 1
        )
        self.assertEqual(
            self.admit(now_ms=self.now_ms + 5008)["rewards"]["delivered"], []
        )

    def test_missed_proposal_expires_without_progress_or_rewards(self):
        self.phased_profile()
        event = self.admit()["instances"][0]["instance_id"]
        self.roster(event, [702])
        expired = self.admit(now_ms=self.now_ms + 65001)
        self.assertEqual(expired["instances"], [])
        self.assertEqual(expired["rewards"]["delivered"], [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT state FROM environmental_event_instances"
                ).fetchone()["state"],
                "expired",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_progress"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT action FROM environmental_cleanup_outbox"
                ).fetchone()["action"],
                "release_membership",
            )
