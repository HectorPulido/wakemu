"""Native completion preserves Active; reset and known period expiry clear it."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import dungeon_achievement_authority as authority
from wakfu_server import dungeon_criteria
from wakfu_server.achievements import lifecycle, storage, mission_progress


def state(**updates):
    result = dict(
        variables={},
        running=[],
        completed=[],
        objectives=[],
        tracking=[],
        recent=[],
        completion_dates={},
        active=[],
        active_periods={},
    )
    result.update(updates)
    return result


class IndependentActiveTests(unittest.TestCase):
    def test_unknown_completed_history_rejects_active_and_negation_until_explicit_reset(
        self,
    ):
        value = state(completed=[12], active_unknown=[12])
        predicates = authority.queries_from_state(value)
        for expression in ("IsAchievementActive(12)", "not IsAchievementActive(12)"):
            with self.subTest(expression=expression), self.assertRaisesRegex(
                ValueError, "independent achievement active"
            ):
                dungeon_criteria.evaluate(None, expression, queries=predicates)
        self.assertFalse(predicates["IsAchievementRunning"](12))
        self.assertTrue(predicates["IsAchievementComplete"](12))
        self.assertEqual(lifecycle.active_ids(value), set())
        lifecycle.reset(value, 12)
        self.assertEqual(value["active_unknown"], [])
        self.assertFalse(authority.queries_from_state(value)["IsAchievementActive"](12))
        self.assertTrue(
            authority.queries_from_state(value)["IsAchievementComplete"](12)
        )

    def test_active_complete_and_running_are_independent_and_preview_is_not_authority(
        self,
    ):
        value = state(active=[2160], completed=[2160], completion_dates={"2160": 100})
        predicates = authority.queries_from_state(value)
        self.assertTrue(predicates["IsAchievementActive"](2160))
        self.assertTrue(predicates["IsAchievementComplete"](2160))
        self.assertFalse(predicates["IsAchievementRunning"](2160))
        self.assertTrue(
            dungeon_criteria.evaluate(
                None,
                "IsAchievementActive(2160) and not IsAchievementComplete(2161)",
                queries=predicates,
            )
        )
        value["active"] = []
        self.assertFalse(
            authority.queries_from_state(value)["IsAchievementActive"](2160)
        )
        self.assertTrue(
            authority.queries_from_state(value)["IsAchievementComplete"](2160)
        )
        legacy = dict(running=[], completed=[2160], objectives=[])
        with self.assertRaisesRegex(ValueError, "independent achievement active"):
            authority.queries_from_snapshot(legacy)["IsAchievementActive"](2160)

    def test_actual_acceptance_completion_and_explicit_reset_preserve_separate_flags(
        self,
    ):
        native = dict(
            d=2160,
            native_class="aJM",
            aqb=False,
            cjI="",
            cjJ=[dict(d=4279, ckc="", cke="", ckf=[])],
            cjK=[],
        )
        before = state(running=[2160])
        mission_progress.auto_track(before, 2160)
        after, _, _, completed = mission_progress.advance_objective(
            before, native, 4279, character={"id": 7}, store=None, now_ms=100
        )
        self.assertEqual(completed, [2160])
        self.assertEqual(after["active"], [2160])
        self.assertEqual(after["running"], [])
        self.assertEqual(after["completed"], [2160])
        lifecycle.reset(after, 2160)
        predicates = authority.queries_from_state(after)
        self.assertFalse(predicates["IsAchievementActive"](2160))
        self.assertFalse(predicates["IsAchievementRunning"](2160))
        self.assertTrue(predicates["IsAchievementComplete"](2160))

    def test_expired_and_missing_acceptance_clock_never_authorize_an_anchored_period(
        self,
    ):
        value = state(
            active=[9],
            running=[9],
            active_periods={
                "9": dict(anchor_ms=1000, period_seconds=10, accepted_at_ms=1001)
            },
        )
        self.assertTrue(
            authority.queries_from_state(value, now_ms=2000)["IsAchievementActive"](9)
        )
        self.assertFalse(
            authority.queries_from_state(value, now_ms=21000)["IsAchievementActive"](9)
        )
        self.assertFalse(
            authority.queries_from_state(value, now_ms=21000)["IsAchievementRunning"](9)
        )
        value["active_periods"]["9"]["accepted_at_ms"] = None
        self.assertEqual(lifecycle.active_ids(value, now_ms=2000), set())
        with self.assertRaisesRegex(ValueError, "acceptance clock"):
            authority.queries_from_state(value, now_ms=2000)["IsAchievementActive"](9)
        with self.assertRaisesRegex(ValueError, "acceptance clock"):
            dungeon_criteria.evaluate(
                None,
                "not IsAchievementActive(9)",
                queries=authority.queries_from_state(value, now_ms=2000),
            )


class IndependentActivePostgresTests(PostgresCase):
    def owner(self):
        with self.store.connection() as db:
            account = db.execute(
                "INSERT INTO accounts(username,username_key,salt,password_hash) VALUES('activeproof','activeproof',%s,%s) RETURNING id",
                (bytes(16), b"test-hash"),
            ).fetchone()["id"]
            return db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) VALUES(%s,'Active Proof','active proof',8,false,0,0,'[]','{}',60,60) RETURNING id",
                (account,),
            ).fetchone()["id"]

    def test_atomic_accept_complete_reload_reset_and_rollback(self):
        identity = self.owner()
        with self.store.connection() as db:
            before = storage.load_locked(db, identity)
            before["running"] = [2160]
            mission_progress.auto_track(before, 2160)
            storage.store(db, identity, before)
        native = dict(
            d=2160,
            native_class="aJM",
            aqb=False,
            cjI="",
            cjJ=[dict(d=4279, ckc="", cke="", ckf=[])],
            cjK=[],
        )
        with self.store.connection() as db:
            before = storage.load_locked(db, identity)
            after, *_ = mission_progress.advance_objective(
                before,
                native,
                4279,
                character={"id": identity},
                store=self.store,
                now_ms=100,
            )
            storage.store(db, identity, after)
        with self.store.connection() as db:
            after = storage.load_locked(db, identity)
            self.assertEqual(after["active"], [2160])
            self.assertEqual(after["completed"], [2160])
            with db.transaction(force_rollback=True):
                reset = deepcopy(after)
                lifecycle.reset(reset, 2160)
                storage.store(db, identity, reset)
                self.assertFalse(
                    authority.queries_from_state(storage.load_locked(db, identity))[
                        "IsAchievementActive"
                    ](2160)
                )
        self.assertTrue(
            authority.queries(self.store, identity)["IsAchievementActive"](2160)
        )
        self.assertFalse(
            authority.queries(self.store, identity)["IsAchievementRunning"](2160)
        )
        with self.store.connection() as db:
            final = storage.load_locked(db, identity)
            lifecycle.reset(final, 2160)
            storage.store(db, identity, final)
        self.assertFalse(
            authority.queries(self.store, identity)["IsAchievementActive"](2160)
        )
        self.assertTrue(
            authority.queries(self.store, identity)["IsAchievementComplete"](2160)
        )

    def test_legacy_backfill_uses_nonperiodic_owned_completion_not_preview_or_missing_clock(
        self,
    ):
        identity = self.owner()
        revision = "c" * 64
        legacy = state(
            running=[10],
            completed=[11, 12, 13],
            completion_dates={"11": 100, "13": 100},
        )
        legacy.pop("active")
        legacy.pop("active_periods")
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,4)",
                (revision, Jsonb({"fixture": "activehistory"}), b"active"),
            )
            for q in [10, 11, 12, 13]:
                native = dict(
                    d=q,
                    native_class="aJM",
                    cjT=1000 if q == 13 else 0,
                    cjU=10 if q == 13 else 0,
                )
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                    (revision, q, Jsonb({"native": native})),
                )
            db.execute(
                "INSERT INTO character_achievement_progress(character_id,state) VALUES(%s,%s)",
                (identity, Jsonb(legacy)),
            )
            db.execute(
                "UPDATE character_achievement_authority SET snapshot=%s WHERE character_id=%s",
                (
                    Jsonb(
                        {
                            key: legacy[key]
                            for key in ["running", "completed", "objectives"]
                        }
                    ),
                    identity,
                ),
            )
            db.execute(
                (
                    Path(__file__).parents[1]
                    / "migrations/380_independent_achievement_active_flags.sql"
                ).read_text()
            )
            migrated = storage.load_locked(db, identity)
            self.assertEqual(migrated["active"], [10, 11])
            self.assertTrue(
                authority.queries_from_state(migrated)["IsAchievementActive"](11)
            )
            self.assertEqual(migrated["active_unknown"], [12, 13])
            for unknown in (12, 13):
                with self.assertRaisesRegex(
                    ValueError, "independent achievement active"
                ):
                    authority.queries_from_state(migrated)["IsAchievementActive"](
                        unknown
                    )
            self.assertEqual(migrated["completed"], [11, 12, 13])
            self.assertEqual(migrated["objectives"], [])


if __name__ == "__main__":
    unittest.main()
