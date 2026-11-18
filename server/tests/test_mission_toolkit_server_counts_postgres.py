"""Durable server-count thresholds for native direct objectives."""

from copy import deepcopy
from unittest.mock import patch
import unittest

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase

from wakfu_server.achievements import mission_toolkit as toolkit, storage
from wakfu_server.achievements import mission_toolkit_planner as planner


def native_quest(identity, objective_id, rewards=()):
    return {
        "d": identity,
        "native_class": "aJM",
        "aqb": False,
        "cjI": "",
        "cjJ": [{"d": objective_id, "ckc": "", "cke": "", "ckf": []}],
        "cjK": list(rewards),
        "cjU": 0,
        "cjL": 0,
        "getDuration": 0,
    }


def counted_profile(
    profile_id, quest_id, objective_id, *, threshold=5, reference=3599, map_id=777
):
    return {
        "version": 1,
        "id": profile_id,
        "evidence": ["Reviewed count-threshold integration fixture."],
        "bindings": [
            {
                "id": f"count-{profile_id}",
                "quest_id": quest_id,
                "objective_id": objective_id,
                "event": {"kind": "craft_completed", "reference": reference},
                "count": "quantity",
                "count_threshold": threshold,
                "maps": [map_id],
            }
        ],
        "links": [],
        "activations": [
            {
                "id": f"accept-{profile_id}",
                "quest_id": quest_id,
                "event": {"kind": "map_enter", "reference": map_id},
                "maps": [map_id],
            }
        ],
    }


class MissionToolkitServerCountPlannerTests(unittest.TestCase):
    def test_legacy_plan_keeps_four_values_and_counted_plan_returns_fifth_snapshot(
        self,
    ):
        quest_id, objective_id = 990001, 990011
        definition = native_quest(quest_id, objective_id)
        base = {
            "version": 1,
            "id": "planner-count-shape",
            "evidence": ["planner fixture"],
            "bindings": [
                {
                    "id": "direct",
                    "quest_id": quest_id,
                    "objective_id": objective_id,
                    "event": {"kind": "craft_completed", "reference": 3599},
                    "count": "operation",
                }
            ],
            "links": [],
            "activations": [],
        }
        state = {
            "variables": {},
            "objectives": [],
            "running": [quest_id],
            "completed": [],
            "tracking": [quest_id],
            "recent": [],
            "completion_dates": {},
        }
        character = {"id": 1, "map_id": 777}
        legacy = planner.plan(
            state,
            {quest_id: definition},
            base,
            {"kind": "craft_completed", "reference": 3599, "quantity": 1},
            character=character,
            store=None,
            now_ms=123,
        )
        self.assertEqual(len(legacy), 4)

        native_counter = deepcopy(definition)
        native_counter["cjJ"][0]["ckf"] = [
            {
                "ckm": 'GetAchievementVariable("fixture-990001") >= 2',
                "ckn": [990001],
            }
        ]
        variable_profile = deepcopy(base)
        variable_profile["bindings"][0]["variable_id"] = 990001
        variable_result = planner.plan(
            state,
            {quest_id: native_counter},
            variable_profile,
            {"kind": "craft_completed", "reference": 3599, "quantity": 1},
            character=character,
            store=None,
            now_ms=123,
        )
        self.assertEqual(len(variable_result), 4)
        self.assertEqual(variable_result[0]["variables"]["990001"], 1)
        native_override = deepcopy(variable_profile)
        native_override["bindings"][0]["count_threshold"] = 2
        with self.assertRaisesRegex(ValueError, "cannot replace a native counter"):
            planner.plan_counted(
                state,
                {quest_id: native_counter},
                native_override,
                {"kind": "craft_completed", "reference": 3599, "quantity": 1},
                character=character,
                store=None,
                now_ms=123,
                objective_counts={objective_id: 0},
            )

        counted = deepcopy(base)
        counted["bindings"][0]["count_threshold"] = 2
        with self.assertRaisesRegex(ValueError, "requires its durable count snapshot"):
            planner.plan(
                state,
                {quest_id: definition},
                counted,
                {"kind": "craft_completed", "reference": 3599, "quantity": 1},
                character=character,
                store=None,
                now_ms=123,
            )
        extended = planner.plan_counted(
            state,
            {quest_id: definition},
            counted,
            {"kind": "craft_completed", "reference": 3599, "quantity": 1},
            character=character,
            store=None,
            now_ms=123,
            objective_counts={objective_id: 0},
        )
        self.assertEqual(len(extended), 5)
        self.assertEqual(extended[4][objective_id], 1)


class MissionToolkitServerCountsPostgresTests(PostgresCase):
    def test_quantity_counts_replay_rollback_upgrade_conflict_and_completed_inertia(
        self,
    ):
        account = self.store.register("server-counts", "isolated-count-password")["id"]
        character = self.store.create_character(account, "Server Counts")
        character.update(map_id=777, instance_id=0)
        quest_id, objective_id = 930001, 930011
        reward = {"d": 930021, "aeV": 3, "ckl": [20008]}
        definition = native_quest(quest_id, objective_id, [reward])
        profile = counted_profile("server-counts-v1", quest_id, objective_id)

        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            db.execute(
                "UPDATE characters SET map_id=777,instance_id=0 WHERE id=%s",
                (character["id"],),
            )
            db.execute(
                "INSERT INTO native_emote_definitions(emote_id) VALUES(20008) ON CONFLICT DO NOTHING"
            )
            revision = "c" * 64
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    revision,
                    Jsonb({"fixture": "server objective counts"}),
                    b"count thresholds",
                    1,
                ),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                (revision, quest_id, Jsonb({"native": definition})),
            )
            toolkit.install(db, profile, activate=True)
            toolkit.settle(db, self.store, character, "start", "map_enter", 777)
            self.assertIn(quest_id, storage.load_locked(db, character["id"])["running"])

            # One producer event represents three crafted batches, not three output items.
            self.assertEqual(
                toolkit.settle(
                    db, self.store, character, "batch-3", "craft_completed", 3599, 3
                ),
                [],
            )
            self.assertEqual(
                toolkit.settle(
                    db, self.store, character, "batch-3", "craft_completed", 3599, 3
                ),
                [],
            )
            count = db.execute(
                "SELECT count FROM character_mission_objective_counts WHERE character_id=%s AND objective_id=%s",
                (character["id"], objective_id),
            ).fetchone()["count"]
            self.assertEqual(count, 3)
            self.assertNotIn(
                objective_id, storage.load_locked(db, character["id"])["objectives"]
            )

            toolkit.settle(
                db, self.store, character, "batch-4", "craft_completed", 3599, 1
            )
            self.assertEqual(
                db.execute(
                    "SELECT count FROM character_mission_objective_counts WHERE character_id=%s AND objective_id=%s",
                    (character["id"], objective_id),
                ).fetchone()["count"],
                4,
            )

            # The count and producer receipt are written before settlement; a failed reward rolls them back together.
            with self.assertRaisesRegex(ValueError, "injected reward failure"):
                with db.transaction():
                    with patch(
                        "wakfu_server.achievements.rewards.validate",
                        side_effect=ValueError("injected reward failure"),
                    ):
                        toolkit.settle(
                            db,
                            self.store,
                            character,
                            "batch-5",
                            "craft_completed",
                            3599,
                            1,
                        )
            self.assertEqual(
                db.execute(
                    "SELECT count FROM character_mission_objective_counts WHERE character_id=%s AND objective_id=%s",
                    (character["id"], objective_id),
                ).fetchone()["count"],
                4,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events WHERE character_id=%s AND event_key LIKE 'mission-toolkit:craft_completed:3599:%%'",
                    (character["id"],),
                ).fetchone()["n"],
                2,
            )
            self.assertNotIn(
                objective_id, storage.load_locked(db, character["id"])["objectives"]
            )

            upgraded = deepcopy(profile)
            upgraded["evidence"].append(
                "Count identity remains the native objective across profile publication upgrades."
            )
            metadata = toolkit.install(db, upgraded, activate=True)
            self.assertGreater(metadata["version"], 1)
            self.assertEqual(
                db.execute(
                    "SELECT count FROM character_mission_objective_counts WHERE character_id=%s AND objective_id=%s",
                    (character["id"], objective_id),
                ).fetchone()["count"],
                4,
            )

            toolkit.settle(
                db, self.store, character, "batch-5", "craft_completed", 3599, 1
            )
            state = storage.load_locked(db, character["id"])
            self.assertIn(objective_id, state["objectives"])
            self.assertIn(quest_id, state["completed"])
            self.assertEqual(
                db.execute(
                    "SELECT count FROM character_mission_objective_counts WHERE character_id=%s AND objective_id=%s",
                    (character["id"], objective_id),
                ).fetchone()["count"],
                5,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=%s AND reward_key=%s",
                    (character["id"], quest_id, str(reward["d"])),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                toolkit.settle(
                    db, self.store, character, "batch-5", "craft_completed", 3599, 1
                ),
                [],
            )

            # Upgrading a completed objective cannot restart its server count or re-award it.
            completed_upgrade = deepcopy(upgraded)
            completed_upgrade["evidence"].append("Post-completion profile revision.")
            toolkit.install(db, completed_upgrade, activate=True)
            toolkit.settle(
                db, self.store, character, "after-complete", "craft_completed", 3599, 3
            )
            self.assertEqual(
                db.execute(
                    "SELECT count FROM character_mission_objective_counts WHERE character_id=%s AND objective_id=%s",
                    (character["id"], objective_id),
                ).fetchone()["count"],
                5,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=%s AND reward_key=%s",
                    (character["id"], quest_id, str(reward["d"])),
                ).fetchone()["n"],
                1,
            )

            conflict = counted_profile(
                "server-counts-conflict",
                quest_id,
                objective_id,
                threshold=10,
                reference=3600,
                map_id=778,
            )
            with self.assertRaisesRegex(
                ValueError, "disagree on a server objective threshold"
            ):
                with db.transaction():
                    toolkit.install(db, conflict, activate=True)


if __name__ == "__main__":
    unittest.main()
