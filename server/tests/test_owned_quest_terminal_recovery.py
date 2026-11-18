"""A terminal recovery certificate requires real original enemy deaths and owner."""

import copy
from types import SimpleNamespace
import unittest
from wakfu_server.achievements.owned_quest_terminal_recovery import projection


class CertifiedTerminalProjectionTests(unittest.TestCase):
    def setUp(self):
        self.owner = dict(
            character_id=7, account_id=2, team=0, session_generation="owned"
        )
        self.monsters = [
            dict(id=-1, ref=3233),
            dict(id=-2, ref=3233),
            dict(id=-3, ref=3233),
        ]
        self.raw = dict(
            id=694,
            phase="finished",
            winner=0,
            actors={
                "7": dict(
                    id=7,
                    team=0,
                    owner_id=2,
                    controlled=True,
                    hp=100,
                    max_hp=150,
                    effect_stats={"36": 0},
                    position=[0, 0, 0],
                    effect_frozen=[1, 2],
                ),
                **{
                    str(r["id"]): dict(
                        id=r["id"], team=1, controlled=False, hp=0, max_hp=60
                    )
                    for r in self.monsters
                },
            },
            events=[
                *[dict(kind="death", actor_id=r["id"]) for r in self.monsters],
                dict(kind="finished", winner=0),
            ],
        )

    def project(self, raw=None):
        return projection(
            self.raw if raw is None else raw,
            fight_id=694,
            owner=self.owner,
            monsters=self.monsters,
            player_team=0,
        )

    def test_projection_preserves_genuine_winner_without_native_replay_or_map_attribute(
        self,
    ):
        raw = copy.deepcopy(self.raw)
        fight = self.project()
        self.assertEqual((fight.id, fight.phase, fight.winner), (694, "finished", 0))
        self.assertEqual(fight.actors[7].effect_stats, {36: 0})
        self.assertEqual(fight.actors[7].position, (0, 0, 0))
        self.assertEqual(fight.actors[7].effect_frozen, frozenset((1, 2)))
        self.assertFalse(hasattr(fight, "map_id"))
        self.assertEqual(self.raw, raw)
        self.assertTrue(all(fight.actors[r["id"]].hp == 0 for r in self.monsters))

    def test_active_defeated_summoned_companion_and_mismatched_fight_reject(self):
        variants = [
            dict(phase="active"),
            dict(winner=1),
            dict(id=695),
            dict(native_summon_registrations={"-4": {}}),
            dict(native_companion_sources={"-5": {}}),
            dict(checkpoint_schema=2),
        ]
        for delta in variants:
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                self.project(dict(self.raw, **delta))

    def test_operator_outcome_without_real_deaths_rejects(self):
        # !winfight sets HP zero and finished, but never creates actual enemy
        # death events. Those scalar fields alone cannot certify an earned win.
        with self.assertRaisesRegex(ValueError, "actual enemy deaths"):
            self.project(dict(self.raw, events=[dict(kind="finished", winner=0)]))

    def test_living_enemy_wrong_owner_and_foreign_actor_reject(self):
        for mutation in ["living", "owner", "foreign", "withdrawn_owner"]:
            raw = copy.deepcopy(self.raw)
            if mutation == "living":
                raw["actors"]["-1"]["hp"] = 1
            elif mutation == "owner":
                raw["actors"]["7"]["owner_id"] = 9
            elif mutation == "withdrawn_owner":
                raw["actors"]["7"]["hp"] = 0
            else:
                raw["actors"]["-4"] = dict(
                    id=-4, team=1, controlled=False, hp=0, max_hp=60
                )
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.project(raw)

    def test_malformed_history_and_actor_structures_reject_as_certificate_errors(self):
        cases = []
        for events in ([None], {"kind": "finished"}):
            cases.append(dict(self.raw, events=events))
        for field, value in (
            ("effect_stats", []),
            ("position", 4),
            ("effect_frozen", 4),
            ("state_ledger", []),
            ("team", None),
        ):
            raw = copy.deepcopy(self.raw)
            raw["actors"]["7"][field] = value
            cases.append(raw)
        raw = copy.deepcopy(self.raw)
        raw["actors"]["7"] = None
        cases.append(raw)
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.project(raw)


class CertifiedTerminalDigestFenceTests(unittest.TestCase):
    def setUp(self):
        CertifiedTerminalProjectionTests.setUp(self)
        self.candidate = dict(
            fight_status="aborted",
            fight_kind="pve",
            checkpoint_status="aborted",
            revision=10,
            snapshot=self.raw,
            instance_id=99,
            room_order=1,
            encounter_status="aborted",
            encounter_scope="main",
            player_team=0,
            context_route_key="owned",
            context_policy_version=1,
            start_map_id=891,
        )
        self.existing = None
        self.later = None
        self.writes = []
        selected = dict(
            schema="owned-quest-instance-v1",
            maximum_members=1,
            quest_id=2016,
            entry_objective=4079,
            victory_objective=4084,
            roster=[dict(reference=3233, count=3)],
            provenance="reviewed fixture",
        )
        self.config = dict(
            topology=dict(owned_quest_encounter=selected), route=dict(start_map_id=891)
        )
        from unittest.mock import patch

        manager = patch(
            "wakfu_server.dungeon_runtime_config.pinned_configuration",
            return_value=self.config,
        )
        manager.start()
        self.addCleanup(manager.stop)
        self.db = SimpleNamespace(execute=self.execute)

    def execute(self, sql, params=()):
        if sql.startswith("UPDATE"):
            self.writes.append((sql, params))
            raise AssertionError("Certificate fence allowed a mutation")
        if "SELECT f.status AS fight_status" in sql:
            row = self.candidate
        elif "SELECT p.*,false AS withdrawn" in sql:
            return SimpleNamespace(fetchall=lambda: [dict(self.owner, withdrawn=False)])
        elif "SELECT payload FROM character_achievement_events" in sql:
            row = self.existing
        elif "SELECT * FROM dungeon_room_runs" in sql:
            row = dict(status="active", current_room=self.candidate["room_order"])
        elif "fight_id>%s" in sql:
            self.later_params = params
            row = self.later
        else:
            raise AssertionError(sql)
        return SimpleNamespace(fetchone=lambda: row)

    def test_reviewed_abort_requires_exact_snapshot_digest_before_any_write(self):
        from wakfu_server.achievements.owned_quest_terminal_recovery import recover

        for digest in (None, "0" * 64):
            with self.subTest(digest=digest), self.assertRaisesRegex(
                ValueError, "reviewed abort digest"
            ):
                recover(None, self.db, 694, reviewed_aborted_sha256=digest)
        self.assertEqual(self.writes, [])

    def test_even_correct_digest_cannot_overwrite_a_later_attempt(self):
        from wakfu_server.achievements.owned_quest_terminal_recovery import recover
        from wakfu_server.fight_checkpoint_store import checkpoint_digest

        self.later = dict(present=1)
        with self.assertRaisesRegex(ValueError, "later encounter"):
            recover(
                None, self.db, 694, reviewed_aborted_sha256=checkpoint_digest(self.raw)
            )
        self.assertEqual(self.writes, [])

    def test_receipted_finished_replay_never_rewards_or_rebinds_again(self):
        from wakfu_server.achievements.owned_quest_terminal_recovery import recover
        from wakfu_server.fight_checkpoint_store import checkpoint_digest

        self.candidate["fight_status"] = "finished"
        self.existing = dict(
            payload=dict(
                checkpoint_sha256=checkpoint_digest(self.raw), fight_id=694, owner=7
            )
        )
        self.assertTrue(recover(None, self.db, 694)["replay"])
        self.assertEqual(self.writes, [])

    def test_later_attempt_fence_uses_exact_story_room_not_the_first_room(self):
        from wakfu_server.achievements.owned_quest_terminal_recovery import recover
        from wakfu_server.fight_checkpoint_store import checkpoint_digest

        self.candidate["room_order"] = 5
        self.config = story_configuration()
        self.later = dict(present=1)
        # Repoint the configured mock to the new five-room fixture.
        from unittest.mock import patch

        with patch(
            "wakfu_server.dungeon_runtime_config.pinned_configuration",
            return_value=self.config,
        ):
            with self.assertRaisesRegex(ValueError, "later encounter"):
                recover(
                    None,
                    self.db,
                    694,
                    reviewed_aborted_sha256=checkpoint_digest(self.raw),
                )
        self.assertEqual(self.later_params, (99, 5, 694))
        self.assertEqual(self.writes, [])


def story_configuration():
    return dict(
        route=dict(start_map_id=887),
        topology=dict(
            owned_story_controller=dict(
                schema="owned-story-controller-v1",
                id="test-five-room-story",
                map_id=887,
                maximum_members=1,
                admission=dict(
                    quest_id=2166, objective_id=4288, continuation_quest_id=2170
                ),
                provenance="explicit synthetic certificate fixture, not an official formation",
                steps=[
                    dict(
                        id=f"win-{order}",
                        kind="room_victory",
                        reference=order,
                        requires=[],
                        effects=[],
                        evidence="fixture",
                    )
                    for order in range(1, 6)
                ],
            )
        ),
        compiled_plan=dict(
            rooms=[
                dict(
                    order=order,
                    monsters=[dict(ref_id=3234 if order == 5 else 3237, count=1)],
                )
                for order in range(1, 6)
            ]
        ),
    )


class CertifiedStoryRosterTests(unittest.TestCase):
    def test_each_room_uses_only_its_frozen_original_roster(self):
        from wakfu_server.achievements.owned_quest_terminal_recovery import (
            reviewed_roster,
        )

        config = story_configuration()
        self.assertEqual(
            reviewed_roster(config, 1), dict(roster=[dict(reference=3237, count=1)])
        )
        self.assertEqual(
            reviewed_roster(config, 5), dict(roster=[dict(reference=3234, count=1)])
        )
        for bad in (0, True, 6):
            with self.subTest(room=bad), self.assertRaises(ValueError):
                reviewed_roster(config, bad)

    def test_missing_producer_duplicate_room_wrong_map_and_bad_roster_reject(self):
        from wakfu_server.achievements.owned_quest_terminal_recovery import (
            reviewed_roster,
        )

        for case in ("producer", "duplicate", "map", "roster"):
            config = story_configuration()
            if case == "producer":
                config["topology"]["owned_story_controller"]["steps"].pop()
            elif case == "duplicate":
                config["compiled_plan"]["rooms"].append(
                    copy.deepcopy(config["compiled_plan"]["rooms"][-1])
                )
            elif case == "map":
                config["route"]["start_map_id"] = 747
            else:
                config["compiled_plan"]["rooms"][-1]["monsters"][0]["count"] = True
            with self.subTest(case=case), self.assertRaises(ValueError):
                reviewed_roster(config, 5)


class CertifiedTerminalStartupIsolationTests(unittest.TestCase):
    def test_rejected_candidate_rolls_back_without_blocking_the_next_win(self):
        from contextlib import contextmanager
        from unittest.mock import patch
        from wakfu_server.achievements import owned_quest_terminal_recovery as recovery

        writes = []

        @contextmanager
        def savepoint():
            before = list(writes)
            try:
                yield
            except Exception:
                writes[:] = before
                raise

        db = SimpleNamespace(
            transaction=savepoint,
            execute=lambda *_: SimpleNamespace(
                fetchall=lambda: [dict(id=1), dict(id=2)]
            ),
        )

        def recover(_store, _db, identity):
            writes.append(identity)
            if identity == 1:
                raise ValueError("Malformed terminal certificate")
            return dict(fight_id=identity)

        with patch.object(
            recovery, "recover", side_effect=recover
        ) as called, self.assertLogs(recovery.__name__, level="WARNING") as logs:
            self.assertEqual(recovery.settle_startup(None, db), [dict(fight_id=2)])
        self.assertEqual(writes, [2])
        self.assertEqual(called.call_count, 2)
        self.assertIn("fight_id=1", logs.output[0])

    def test_database_and_unexpected_runtime_errors_are_not_silenced(self):
        from contextlib import nullcontext
        from unittest.mock import patch
        from psycopg import OperationalError
        from wakfu_server.achievements import owned_quest_terminal_recovery as recovery

        db = SimpleNamespace(
            transaction=nullcontext,
            execute=lambda *_: SimpleNamespace(fetchall=lambda: [dict(id=1)]),
        )
        for error in (
            OperationalError("Database unavailable"),
            RuntimeError("Unexpected implementation error"),
        ):
            with self.subTest(error=type(error).__name__), patch.object(
                recovery, "recover", side_effect=error
            ), self.assertRaises(type(error)):
                recovery.settle_startup(None, db)
