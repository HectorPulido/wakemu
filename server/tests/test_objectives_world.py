"""World objective projections stay current-period and nonblocking."""
from datetime import datetime, timezone
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server.custom_tasks import external
from wakfu_server.achievements import service as achievement_service
from wakfu_server.objectives import points, repository


def row(key, definition, revision=1):
    return {"key": key, "definition": definition, "revision": revision}


class ObjectivesWorldTests(unittest.TestCase):
    def test_finite_challenge_namespace_bypasses_ecology_without_database_or_policy_reads(
        self,
    ):
        from wakfu_server.objectives.challenges import (
            INSTANCE_MINIMUM,
            is_challenge_instance,
        )
        from wakfu_server.maps import (
            monster_active_clocks,
            monster_reproduction,
            monster_wander,
        )

        class NoDatabase:
            def connection(self):
                raise AssertionError("finite challenge must not touch persistence")

        challenge_id = INSTANCE_MINIMUM + 17
        self.assertTrue(is_challenge_instance(challenge_id))
        self.assertFalse(is_challenge_instance(0))
        self.assertFalse(is_challenge_instance(INSTANCE_MINIMUM - 1))
        self.assertFalse(is_challenge_instance(True))
        store = NoDatabase()
        self.assertEqual(
            monster_active_clocks.observe(
                store,
                1086,
                challenge_id,
                present=True,
                generation="g",
                now_ms=10,
                table="monster_maturation_timers",
                eligible_refs=set(),
                policy_provider=lambda _store: (_ for _ in ()).throw(
                    AssertionError("policy read")
                ),
            ),
            [],
        )

        class NoGroups:
            def __getattr__(self, name):
                raise AssertionError(f"challenge wander touched group registry: {name}")

        self.assertEqual(
            monster_wander.wander_location(
                NoGroups(),
                1086,
                challenge_id,
                [],
                [],
                lambda *_args: None,
            ),
            [],
        )
        self.assertTrue(monster_reproduction.dungeon_population(store, challenge_id))
        self.assertFalse(monster_reproduction.dungeon_population(store, 0))

        class EmptyDatabase:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def execute(self, *_args):
                return type("Rows", (), {"fetchone": lambda _self: None})()

        class OrdinaryStore:
            def connection(self):
                return EmptyDatabase()

        self.assertFalse(
            monster_reproduction.dungeon_population(OrdinaryStore(), 123456)
        )

    def test_hero_roster_guard_preserves_frozen_challenge_membership_and_public_command_fences(
        self,
    ):
        from wakfu_server.characters import hero_instance_membership
        from wakfu_server.objectives.challenges import INSTANCE_MINIMUM

        class NoDatabase:
            def execute(self, *_args):
                raise AssertionError(
                    "roster mutation should be rejected before database policy work"
                )

        leader = {"id": 1, "instance_id": INSTANCE_MINIMUM}
        hero = {"id": 2, "instance_id": INSTANCE_MINIMUM}
        with self.assertRaisesRegex(ValueError, "Leave the weekly challenge"):
            hero_instance_membership.reconcile(
                NoDatabase(), object(), 1, "g", leader, hero, joining=True
            )
        leader["instance_id"] = 0
        with self.assertRaisesRegex(ValueError, "Leave the weekly challenge"):
            hero_instance_membership.reconcile(
                NoDatabase(), object(), 1, "g", leader, hero, joining=False
            )

        source = (
            Path(__file__).resolve().parents[1] / "local_game_server.py"
        ).read_text()
        start = source.index(
            "    def execute_objectives_command(text, *, browser_action=None):"
        )
        end = source.index("    def publish_heroes(roster):", start)
        command = source[start:end]
        self.assertLess(
            command.index("authorize_command(STORE, account_id, text)"),
            command.index("external.enabled()"),
        )
        self.assertIn("loaded and character is not None and fight is None", command)
        self.assertIn("with POSITIONS.account_barrier(account_id)", command)
        self.assertIn(
            'STORE.lock_character(db, account_id, generation, character["id"], selected=True)',
            command,
        )
        self.assertIn('command == "!tasks"', command)
        self.assertIn('action == "weekly"', command)

    def test_snapshot_exposes_zero_and_multiobjective_progress_for_current_period(self):
        definitions = [
            row(
                "daily",
                {
                    "key": "daily",
                    "title": "Daily",
                    "description": "Do both",
                    "kind": "daily",
                    "enabled": True,
                    "schedule": {"type": "daily", "timezone": "UTC"},
                    "rewards": [],
                    "objectives": [
                        {"key": "kills", "event": "kill", "filters": {}, "target": 3},
                        {"key": "plant", "event": "plant", "filters": {}, "target": 1},
                    ],
                },
            ),
            row(
                "once",
                {
                    "key": "once",
                    "title": "First step",
                    "description": "One time",
                    "kind": "mission",
                    "enabled": True,
                    "schedule": {"type": "once", "timezone": "UTC"},
                    "rewards": [],
                    "objectives": [
                        {"key": "step", "event": "step", "filters": {}, "target": 1}
                    ],
                },
            ),
            row(
                "inactive-calendar",
                {
                    "key": "inactive-calendar",
                    "title": "Seasonal",
                    "description": "Only today",
                    "kind": "almanax",
                    "enabled": True,
                    "schedule": {
                        "type": "calendar",
                        "timezone": "UTC",
                        "dates": ["2026-10-16"],
                    },
                    "rewards": [],
                    "objectives": [
                        {"key": "step", "event": "step", "filters": {}, "target": 1}
                    ],
                },
            ),
            row(
                "disabled",
                {
                    "key": "disabled",
                    "title": "Disabled",
                    "description": "Hidden",
                    "kind": "task",
                    "enabled": False,
                    "schedule": {"type": "daily", "timezone": "UTC"},
                    "rewards": [],
                    "objectives": [
                        {"key": "step", "event": "step", "filters": {}, "target": 1}
                    ],
                },
            ),
        ]
        progress = [
            {
                "definition_key": "daily",
                "period_key": "2026-10-15",
                "counters": {"kills": 2, "plant": 0},
                "completed_at": None,
            },
            # A prior completed period must not make today's card complete.
            {
                "definition_key": "daily",
                "period_key": "2026-10-14",
                "counters": {"kills": 3, "plant": 1},
                "completed_at": datetime(2026, 10, 14, tzinfo=timezone.utc),
            },
        ]
        with patch.object(
            repository, "list_definitions", return_value=definitions
        ), patch.object(repository, "list_progress", return_value=progress), patch(
            "wakfu_server.objectives.assignments.ensure_for_character", return_value=0
        ), patch(
            "wakfu_server.objectives.assignments.visible_keys",
            return_value={"daily", "once"},
        ), patch(
            "wakfu_server.objectives.points.weights",
            return_value=points.DEFAULT_WEIGHTS,
        ):

            class SnapshotDb:
                def execute(self, *_args):
                    return type(
                        "Rows",
                        (),
                        {"fetchone": lambda _self: {"level": 10, "account_id": 7}},
                    )()

            snapshot = external.snapshot(
                SnapshotDb(), 5, now=datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
            )
        self.assertEqual([item["key"] for item in snapshot], ["daily", "once"])
        self.assertEqual(
            (snapshot[0]["count"], snapshot[0]["target"], snapshot[0]["completed"]),
            (2, 4, False),
        )
        self.assertIn("kills: 2/3", snapshot[0]["description"])
        self.assertIn("plant: 0/1", snapshot[0]["description"])
        self.assertEqual(
            (snapshot[1]["count"], snapshot[1]["target"], snapshot[1]["completed"]),
            (0, 1, False),
        )

    def test_local_mode_is_noop_and_external_mode_persists_server_fact_without_http(
        self,
    ):
        with patch.dict(
            os.environ, {"WAKFU_OBJECTIVES_MODE": "local"}, clear=False
        ), patch.object(
            repository,
            "enqueue",
            side_effect=AssertionError("local mode must not publish"),
        ):
            self.assertEqual(
                external.enqueue_fact(object(), 1, 2, "fight:8", {"kind": "test"}),
                {"replayed": False, "updated": [], "completed": []},
            )
        payload = {"kind": "test", "value": 5}
        with patch.dict(
            os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False
        ), patch("wakfu_server.custom_tasks.service._owner") as owner, patch.object(
            repository, "enqueue", return_value={"id": 17, "replayed": True}
        ) as enqueue:
            result = external.enqueue_fact(object(), 1, 2, "test:5", payload)
        owner.assert_called_once_with(unittest.mock.ANY, 1, 2, True)
        enqueue.assert_called_once_with(unittest.mock.ANY, 1, 2, "test:5", payload)
        self.assertEqual(result, {"replayed": True, "updated": [], "completed": []})

    def test_external_fact_hook_keeps_native_achievement_settlement_packets(self):
        character = {"id": 7, "account_id": 3, "map_id": 20}
        fight = type("Fight", (), {"id": 801})()
        now = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
        native_packet = (17777, b"native-achievement-update")
        event = {"fight_id": 801, "completed_dungeon_id": None}
        with (
            patch.object(achievement_service, "_owner"),
            patch.object(achievement_service, "_event", return_value=event),
            patch(
                "wakfu_server.achievements.storage.load_locked",
                return_value={"running": []},
            ),
            patch("wakfu_server.achievements.storage.record_event", return_value=True),
            patch(
                "wakfu_server.achievements.engine.advance",
                return_value=({"running": []}, [], [], []),
            ),
            patch(
                "wakfu_server.achievements.catalog.load",
                return_value={"definitions": {}},
            ),
            patch("wakfu_server.achievements.storage.store") as persist_native,
            patch(
                "wakfu_server.achievements.wire.changes", return_value=[native_packet]
            ),
            patch.object(achievement_service, "drain_rewards", return_value=[]),
            patch(
                "wakfu_server.achievements.storage.enqueue_notifications"
            ) as persist_notifications,
            patch("wakfu_server.custom_tasks.external.enqueue_fact") as enqueue_fact,
        ):
            result = achievement_service.settle(
                object(),
                type("Store", (), {"now": lambda _self: now})(),
                character,
                fight,
                [],
            )
        self.assertEqual(result["packets"], [native_packet])
        persist_native.assert_called_once()
        persist_notifications.assert_called_once()
        enqueue_fact.assert_called_once_with(
            unittest.mock.ANY,
            3,
            7,
            "combat-completed:801",
            {
                "kind": "combat_completed",
                "fight_id": 801,
                "fight_kind": "pve",
                "won": True,
                "map_id": 20,
                "dungeon_id": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
