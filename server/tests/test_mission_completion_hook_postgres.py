"""External mission adapters publish only durable completions to follow-ups."""

from copy import deepcopy

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase

from wakfu_server.achievements import mission_dependencies, mission_toolkit, storage
from wakfu_server.achievements.mission_progress import advance_objective


def native(identity, objective_id, *, criterion="", rewards=()):
    return {
        "d": identity,
        "native_class": "aJM",
        "aqb": False,
        "cjI": criterion,
        "cjJ": [{"d": objective_id, "ckc": "", "cke": "", "ckf": []}],
        "cjK": list(rewards),
        "cjU": 0,
        "cjL": 0,
        "getDuration": 0,
    }


class MissionCompletionHookPostgresTests(PostgresCase):
    def test_persisted_external_completion_unlocks_followup_and_failed_followup_keeps_source_reward(
        self,
    ):
        account = self.store.register("completion-hook", "isolated-test-password")["id"]
        character = self.store.create_character(account, "Completion Hook")
        source_id, source_objective = 920001, 920011
        follow_id, follow_objective = 920002, 920012
        ready_follow_id, ready_follow_objective = 920003, 920013
        reward = {"d": 920021, "aeV": 3, "ckl": [20008]}
        definitions = {
            source_id: native(source_id, source_objective, rewards=[reward]),
            follow_id: native(
                follow_id, follow_objective, criterion="UnknownNativeCriterion()"
            ),
            ready_follow_id: native(ready_follow_id, ready_follow_objective),
        }
        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            db.execute(
                "INSERT INTO native_emote_definitions(emote_id) VALUES(20008) ON CONFLICT DO NOTHING"
            )
            revision = "b" * 64
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    revision,
                    Jsonb({"fixture": "external completion hook"}),
                    b"completion hook",
                    len(definitions),
                ),
            )
            for identity, definition in definitions.items():
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                    (revision, identity, Jsonb({"native": definition})),
                )
            profile = {
                "version": 1,
                "id": "external-completion-followup",
                "evidence": [
                    "Synthetic integration evidence for a server-authored adapter."
                ],
                "bindings": [],
                "links": [],
                "activations": [
                    {
                        "id": "accept-follow-up-after-source",
                        "quest_id": follow_id,
                        "event": {"kind": "quest_completed", "reference": source_id},
                        "requires_completed": [source_id],
                    },
                    {
                        "id": "accept-valid-follow-up-after-source",
                        "quest_id": ready_follow_id,
                        "event": {"kind": "quest_completed", "reference": source_id},
                        "requires_completed": [source_id],
                    },
                ],
            }
            mission_toolkit.install(db, profile, activate=True)

            with self.assertRaisesRegex(
                ValueError, "Missing durable mission completion authority"
            ):
                mission_toolkit.settle_completions(
                    db, self.store, character, [source_id]
                )

            before = storage.load_locked(db, character["id"])
            planned_state = deepcopy(before)
            planned_state["running"] = [source_id]
            planned_state, intents, objectives, completed = advance_objective(
                planned_state,
                definitions[source_id],
                source_objective,
                character=character,
                store=self.store,
                now_ms=123456,
            )
            outcome = mission_dependencies.settle(
                db,
                self.store,
                character,
                before,
                (planned_state, intents, objectives, completed),
                definitions,
                (),
                now_ms=123456,
            )
            self.assertIn(source_id, outcome["state"]["completed"])
            self.assertNotIn(follow_id, outcome["state"]["running"])
            self.assertIn(ready_follow_id, outcome["state"]["running"])
            self.assertEqual(outcome["completed"], [source_id])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=%s",
                    (character["id"], source_id),
                ).fetchone()["n"],
                1,
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
