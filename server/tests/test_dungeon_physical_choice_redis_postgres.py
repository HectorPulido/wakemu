"""Focused PostgreSQL/Redis QA for private139 post-COMMIT position staging."""
import copy
import json
import os
from pathlib import Path
import uuid
from unittest.mock import patch

from postgres_case import PostgresCase
from dungeon_physical_choice_fixture import PhysicalChoiceFixture


class P1PositionStagingPostgresTests(PhysicalChoiceFixture, PostgresCase):
    def setUp(self):
        super().setUp()
        from wakfu_server.position_redis import Journal, RedisPositions
        import redis

        if (
            self._testMethodName
            == "test_queued_growth_candidate_cannot_advance_a_dungeon_owned_rock"
        ):
            from dungeon_resource_fixture import (
                PhysicalChoiceFixture as ResourceFixture,
            )

            recipe = json.loads(
                (
                    Path(__file__).parent
                    / "fixtures"
                    / "dungeon139"
                    / "resource-prepare-input.json"
                ).read_text()
            )["prepare_kwargs"]
            ResourceFixture.build_choice_fixture(
                self,
                configuration_override=dict(
                    compiled_plan=recipe["plan"],
                    topology=recipe["topology"],
                    route=recipe["route"],
                    provenance=recipe["provenance"],
                    level_policy=recipe["level_policy"],
                ),
            )
        else:
            self.build_choice_fixture()
        redis_url = os.environ.get("WAKFU_REDIS_TEST_URL") or os.environ.get(
            "WAKFU_REDIS_URL"
        )
        if not redis_url:
            self.skipTest("Local Redis URL is required for this isolated journal test")
        self.redis = redis.Redis.from_url(
            redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        self.redis.ping()
        self.namespace = "wakfu:test:p1-staged-choice:" + uuid.uuid4().hex
        self.addCleanup(self.redis.delete, self.namespace)
        self.journal = Journal(self.redis, namespace=self.namespace)
        self.positions = RedisPositions(
            self.store,
            lease_active=lambda *key: key in self.live_leases,
            journal=self.journal,
        )
        for member in self.members:
            member["character"] = self.store.character(
                member["account"], member["character"]["id"]
            )
            self.positions.attach(
                member["account"], member["generation"], member["character"]
            )

    def _member_key(self, index=0):
        member = self.members[index]
        return member, (
            member["account"],
            member["generation"],
            member["character"]["id"],
        )

    def _make_clean_pending_ack(self, index=0):
        member, key = self._member_key(index)
        start = self.positions.entries[key]["current"]
        moved = self.positions.move(
            *key,
            start,
            dict(
                x=start["x"] + 1,
                y=start["y"],
                z=start["z"],
                direction=start["direction"],
            ),
        )
        returned = self.positions.move(
            *key,
            moved,
            dict(
                x=start["x"], y=start["y"], z=start["z"], direction=start["direction"]
            ),
        )
        self.assertFalse(self.positions.entries[key]["dirty"])
        self.assertIn(key, self.positions.mirrors)
        self.assertIn(key, self.positions.pending_acks)
        self.assertEqual(returned["x"], start["x"])
        self.assertEqual(len(list(self.journal.records())), 1)
        return member, key, start

    def _selected_endpoint(self, index=0, path_key=None):
        member = self.members[index]
        witness = next(
            row
            for row in self.input_fixture["physical_selection_witnesses"]
            if row["path_key"] == (path_key or ("west" if index % 2 == 0 else "east"))
        )
        return member, witness["movement"]["end_position"]

    def _choice_without_preview(self, index=0, path_key=None):
        from wakfu_server.dungeon_physical_choice import commit_movement

        member = self.members[index]
        witness = next(
            row
            for row in self.input_fixture["physical_selection_witnesses"]
            if row["path_key"] == (path_key or ("west" if index % 2 == 0 else "east"))
        )
        return commit_movement(
            self.store,
            self.positions,
            self.groups,
            member["account"],
            member["generation"],
            member["character"],
            copy.deepcopy(witness["movement"]),
            copy.deepcopy(witness["movement"]["start_position"]),
            geometry=lambda: self.geometry,
            preview_configuration=None,
        )

    def _assert_clean_at(self, key, expected):
        entry = self.positions.entries[key]
        self.assertFalse(entry["dirty"])
        self.assertEqual(entry["current"]["x"], expected["x"])
        self.assertEqual(entry["current"]["y"], expected["y"])
        self.assertEqual(entry["current"]["z"], expected["z"])
        self.assertEqual(
            entry["persisted"],
            {
                k: entry["current"][k]
                for k in ("map_id", "instance_id", "x", "y", "z", "direction")
            },
        )
        self.assertNotIn(key, self.positions.mirrors)
        self.assertNotIn(key, self.positions.pending_acks)

    def test_prior_redis_journal_is_flushed_and_acknowledged_before_choice(self):
        from wakfu_server import dungeon_physical_choice

        member, key = self._member_key()
        witness = next(
            row
            for row in self.input_fixture["physical_selection_witnesses"]
            if row["path_key"] == "west"
        )
        movement = copy.deepcopy(witness["movement"])
        original_steps = movement["steps"]
        start = self.positions.entries[key]["current"]
        first = original_steps[0]
        checkpoint = dict(
            x=start["x"] + first["dx"],
            y=start["y"] + first["dy"],
            z=start["z"] + first["dz"],
            direction=first["direction"],
        )
        self.positions.move(*key, start, checkpoint)
        self.assertTrue(self.positions.entries[key]["dirty"])
        self.assertEqual(len(list(self.journal.records())), 1)
        movement["start_position"] = dict(checkpoint)
        last = original_steps[-1]
        movement["steps"] = [last]
        expected = dict(
            x=checkpoint["x"] + last["dx"],
            y=checkpoint["y"] + last["dy"],
            z=checkpoint["z"] + last["dz"],
        )
        movement["end_position"] = expected
        expected["direction"] = last["direction"]

        # The read-only source classification must release its pool slot before
        # the Redis checkpoint and durable choice use it again.
        self.store.database.pool.resize(min_size=1, max_size=1)
        normal_flush = self.positions.flush
        flush_observations = []

        def observed_flush(**scope):
            result = normal_flush(**scope)
            persisted = self.store.character(
                member["account"], member["character"]["id"]
            )
            flush_observations.append(
                (persisted["x"], persisted["y"], list(self.journal.records()))
            )
            return result

        self.positions.flush = observed_flush
        result = dungeon_physical_choice.commit_movement(
            self.store,
            self.positions,
            self.groups,
            member["account"],
            member["generation"],
            member["character"],
            movement,
            checkpoint,
            geometry=lambda: self.geometry,
            preview_configuration=None,
        )
        self.positions.flush = normal_flush
        self.assertEqual(flush_observations, [(checkpoint["x"], checkpoint["y"], [])])
        self.assertEqual(result["character"]["x"], expected["x"])
        self.assertEqual(result["character"]["y"], expected["y"])
        self.assertEqual(list(self.journal.records()), [])
        self._assert_clean_at(key, result["character"])
        self.assertEqual(
            self.choice_snapshot()["run"]["branch_key"], result["branch_key"]
        )
        saved = self.store.character(member["account"], member["character"]["id"])
        self.assertEqual(
            (saved["x"], saved["y"], saved["z"]),
            (expected["x"], expected["y"], expected["z"]),
        )

        # A normal movement and flush remain usable after canonical adoption.
        moved = self.positions.move(
            *key,
            result["character"],
            dict(
                x=expected["x"] + 1,
                y=expected["y"],
                z=expected["z"],
                direction=expected["direction"],
            ),
        )
        self.positions.flush(account_id=member["account"])
        self.assertEqual(
            self.store.character(member["account"], member["character"]["id"])["x"],
            moved["x"],
        )
        self.assertEqual(list(self.journal.records()), [])

    def test_redis_ack_failure_preserves_prior_journal_and_rejects_choice(self):
        member, key, baseline = self._make_clean_pending_ack()
        original_ack = self.journal.ack
        before = self.choice_snapshot()

        def fail_ack(*args, **kwargs):
            raise OSError("isolated ACK failure")

        self.journal.ack = fail_ack
        try:
            with self.assertRaises(OSError):
                self.move_choice(member_index=0)
        finally:
            self.journal.ack = original_ack
        self.assertEqual(
            self.choice_snapshot()["run"]["branch_key"], before["run"]["branch_key"]
        )
        self.assertEqual(
            self.store.character(member["account"], member["character"]["id"])["x"],
            baseline["x"],
        )
        self.assertEqual(len(list(self.journal.records())), 1)
        self.assertIn(key, self.positions.mirrors)
        self.assertIn(key, self.positions.pending_acks)

        result = self.move_choice(member_index=0)
        self.assertEqual(result["branch_key"], "west")
        self.assertEqual(list(self.journal.records()), [])
        self._assert_clean_at(key, result["character"])

    def test_move_between_preflush_and_stage_is_rejected_with_recoverable_journal(self):
        from wakfu_server.position_buffer import PositionOwnerBusy

        member, key = self._member_key()
        baseline = copy.deepcopy(self.positions.entries[key]["current"])
        ordinary_flush = self.positions.flush

        def raced_flush(**scope):
            result = ordinary_flush(**scope)
            if scope.get("account_id") == member["account"]:
                current = self.positions.entries[key]["current"]
                self.positions.move(
                    *key,
                    current,
                    dict(
                        x=current["x"] + 1,
                        y=current["y"],
                        z=current["z"],
                        direction=current["direction"],
                    ),
                )
            return result

        self.positions.flush = raced_flush
        with self.assertRaises(PositionOwnerBusy):
            self.move_choice(member_index=0)
        self.positions.flush = ordinary_flush
        self.assertIsNone(self.choice_snapshot()["run"]["branch_key"])
        self.assertEqual(
            self.store.character(member["account"], member["character"]["id"])["x"],
            baseline["x"],
        )
        self.assertTrue(self.positions.entries[key]["dirty"])
        self.assertEqual(len(list(self.journal.records())), 1)

    def test_sql_rollback_after_persist_fault_keeps_checkpoint_and_old_choice(self):
        member, key = self._member_key()
        baseline = copy.deepcopy(self.positions.entries[key]["current"])
        from wakfu_server.position_staged_move import StagedMove

        original_persist = StagedMove.persist

        def persist_then_fail(staged, db):
            original_persist(staged, db)
            raise RuntimeError("injected pre-commit interruption")

        with patch.object(StagedMove, "persist", persist_then_fail):
            with self.assertRaisesRegex(RuntimeError, "pre-commit interruption"):
                self.move_choice(member_index=0)
        self.assertIsNone(self.choice_snapshot()["run"]["branch_key"])
        self.assertEqual(list(self.journal.records()), [])
        self._assert_clean_at(key, baseline)
        self.assertEqual(
            self.store.character(member["account"], member["character"]["id"])["x"],
            baseline["x"],
        )

        # A failed choice does not lose the preceding checkpoint. A retry can
        # select the route after the transient database error has gone away.
        result = self.move_choice(member_index=0)
        self.assertEqual(result["branch_key"], "west")
        self._assert_clean_at(key, result["character"])

    def test_unrelated_ordinary_movement_does_not_flush_position_journal(self):
        member, key, baseline = self._make_clean_pending_ack()
        witness = next(
            row
            for row in self.input_fixture["physical_selection_witnesses"]
            if row["path_key"] == "west"
        )
        movement = copy.deepcopy(witness["movement"])
        first = movement["steps"][0]
        movement["steps"] = [dict(dx=0, dy=1, dz=0, direction=3)]
        first = movement["steps"][0]
        movement["end_position"] = dict(
            x=movement["start_position"]["x"] + first["dx"],
            y=movement["start_position"]["y"] + first["dy"],
            z=movement["start_position"]["z"] + first["dz"],
        )
        self.positions.flush = lambda **_scope: self.fail(
            "selector=None must not flush"
        )
        from wakfu_server.dungeon_physical_choice import commit_movement

        result = commit_movement(
            self.store,
            self.positions,
            self.groups,
            member["account"],
            member["generation"],
            member["character"],
            movement,
            movement["start_position"],
            geometry=lambda: self.geometry,
            preview_configuration=self.config,
            unlocked_room=2,
        )
        self.assertIsNone(result)
        self.assertEqual(len(list(self.journal.records())), 1)
        self.assertIn(key, self.positions.pending_acks)
        self.assertEqual(self.positions.entries[key]["current"], baseline)

    def test_post_commit_interruption_recovers_from_sql_without_redis_replay(self):
        member, key = self._member_key()
        expected_member, expected = self._selected_endpoint()
        self.assertIs(member, expected_member)
        from wakfu_server.position_staged_move import StagedMove

        def crash_after_sql_commit(_staged):
            raise RuntimeError("simulated interruption after SQL commit")

        with patch.object(StagedMove, "_accept", crash_after_sql_commit):
            with self.assertRaisesRegex(RuntimeError, "after SQL commit"):
                self.move_choice(member_index=0)
        self.assertEqual(self.choice_snapshot()["run"]["branch_key"], "west")
        saved = self.store.character(member["account"], member["character"]["id"])
        self.assertEqual(
            (saved["x"], saved["y"], saved["z"]),
            (expected["x"], expected["y"], expected["z"]),
        )
        self.assertEqual(list(self.journal.records()), [])
        # A fresh process-local registry binds to the committed SQL endpoint;
        # no Redis replay or rollback is needed after the commit boundary.
        fresh = type(self.positions)(
            self.store,
            lease_active=lambda *lease: lease in self.live_leases,
            journal=self.journal,
        )
        loaded = fresh.attach(member["account"], member["generation"], saved)
        self.assertEqual(
            (loaded["x"], loaded["y"], loaded["z"]),
            (expected["x"], expected["y"], expected["z"]),
        )
        self.assertEqual(list(self.journal.records()), [])

    def test_queued_growth_candidate_cannot_advance_a_dungeon_owned_rock(self):
        from wakfu_server import dungeon_resource_obstacles
        from wakfu_server.planting import RESOURCES
        from wakfu_server.planting_runtime import Plantings

        with self.store.connection() as db:
            rock = db.execute(
                "SELECT p.* FROM planted_resources p JOIN dungeon_resource_obstacles d USING(resource_uid) "
                "WHERE d.instance_id=%s ORDER BY d.obstacle_key LIMIT 1",
                (self.instance_id,),
            ).fetchone()
            self.assertIsNotNone(rock)
            row = dict(rock)
            # Seed a valid active native stage for this isolated stale-proposal
            # case; both ownership and planted-resource rows remain aligned.
            db.execute(
                "UPDATE dungeon_resource_obstacles SET current_stage=2 WHERE resource_uid=%s",
                (row["resource_uid"],),
            )
            db.execute(
                "UPDATE planted_resources SET stage=2 WHERE resource_uid=%s",
                (row["resource_uid"],),
            )
            row["stage"] = 2
            self.assertTrue(dungeon_resource_obstacles.owns(db, row["resource_uid"]))
            # A queued proposal from the general Ecology producer is represented
            # with a native resource definition and a matching disposable rule.
            # The ownership guard must win after the live row lock, before RNG,
            # stage mutation or an outbox write.
            db.execute(
                "INSERT INTO resource_growth_transitions(resource_reference,from_stage,to_stage,delay_ms,probability) "
                "VALUES(%s,%s,4,1000,0.5) ON CONFLICT(resource_reference,from_stage) "
                "DO UPDATE SET to_stage=EXCLUDED.to_stage,delay_ms=1000,probability=0.5",
                (row["resource_reference"], row["stage"]),
            )
        definition = RESOURCES[row["resource_reference"]]
        draws = []
        result = Plantings(self.store).apply_growth_candidates(
            [(row, definition, (4, 1000, 0.5))],
            random_draw=lambda: draws.append(True) or 0.0,
        )
        self.assertEqual(result, {"applied": [], "capacity_skipped": []})
        self.assertEqual(draws, [])
        with self.store.connection() as db:
            current = db.execute(
                "SELECT stage FROM planted_resources WHERE resource_uid=%s",
                (row["resource_uid"],),
            ).fetchone()
            self.assertEqual(current["stage"], row["stage"])
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM planting_growth_outbox WHERE resource_uid=%s",
                    (row["resource_uid"],),
                ).fetchone()
            )
