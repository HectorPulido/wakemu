"""Aggregate quest sets retain native gates, rewards and follow-up eligibility."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import completed_achievement_sets as sets, storage
from wakfu_server import quest_npc


def native(identity, objective, *, achievement=False, criterion="", rewards=()):
    return dict(
        d=identity,
        native_class="aJM",
        aqb=achievement,
        cjI=criterion,
        aHe="GetRealLevel() >= 25 and IsAchievementComplete(2192)",
        cjU=0,
        cjL=0,
        getDuration=0,
        cjJ=[dict(d=objective, ckc="", cke="", ckf=[])],
        cjK=list(rewards),
    )


class CompletedAchievementSetProfileTests(unittest.TestCase):
    def test_reviewed_profile_and_fail_closed_declarations(self):
        document = deepcopy(sets.profile())
        self.assertEqual(len(sets.validate(document)["bindings"]), 2)
        for change in ("duplicate", "self", "boolean", "evidence", "revision"):
            bad = deepcopy(document)
            row = bad["bindings"][0]
            if change == "duplicate":
                row["all_completed"].append(row["all_completed"][0])
            elif change == "self":
                row["all_completed"].append(row["achievement_id"])
            elif change == "boolean":
                row["all_completed"][0] = True
            elif change == "evidence":
                row["evidence"] = ""
            else:
                bad["native_revision"] = "unknown"
            with self.subTest(change=change), self.assertRaises(ValueError):
                sets.validate(bad)

    def test_unrelated_producer_does_not_query_database(self):
        self.assertEqual(sets.settle(object(), object(), {}, completed=[5568]), [])


class CompletedAchievementSetPostgresTests(PostgresCase):
    def test_partial_legacy_sets_rollback_rewards_once_and_native_hunter_vi_followup(
        self,
    ):
        account = self.store.register("completed-set", "local-password")["id"]
        character = self.store.create_character(account, "Completed Set")
        stranger = self.store.register("other-completed-set", "local-password")["id"]
        document = deepcopy(sets.profile())
        first = document["bindings"][0]["all_completed"]
        all_hunts = document["bindings"][1]["all_completed"]
        definitions = {
            identity: native(identity, 100000 + identity) for identity in all_hunts
        }
        definitions[1707] = native(
            1707,
            3226,
            achievement=True,
            rewards=[
                dict(d=2994, aeV=2, ckk=False, ckl=[269]),
                dict(d=9420, aeV=5, ckk=False, ckl=[29725, 1]),
            ],
        )
        definitions[2873] = native(
            2873,
            5841,
            achievement=True,
            criterion="IsAchievementComplete(1707)",
            rewards=[
                dict(d=4456, aeV=2, ckk=False, ckl=[410]),
                dict(d=9449, aeV=5, ckk=False, ckl=[29759, 1]),
            ],
        )
        source = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "wakfu_server/maps/native_quest_conversation_contracts.json"
            ).read_text()
        )
        sixth = next(row for row in source["definitions"] if row["d"] == 2869)
        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    document["native_revision"],
                    Jsonb({"fixture": "native completed set"}),
                    b"native completed set fixture",
                    len(definitions),
                ),
            )
            for identity, definition in definitions.items():
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                    (
                        document["native_revision"],
                        identity,
                        Jsonb({"native": definition}),
                    ),
                )
            state = storage.load_locked(db, character["id"])
            state.update(
                completed=first[:-1],
                completion_dates={str(identity): 1000 for identity in first[:-1]},
            )
            storage.store(db, character["id"], state)
            with self.assertRaisesRegex(
                ValueError, "Missing owned achievement character"
            ):
                sets.recover(db, self.store, dict(character, account_id=stranger))
            self.assertEqual(
                sets.settle(db, self.store, character, completed=[first[-2]]), []
            )
            # Older owned server progress may lack a presentation date. The
            # native earning predicate reads completed membership, not dates.
            state["completed"] = list(first)
            storage.store(db, character["id"], state)
            with self.assertRaisesRegex(RuntimeError, "rollback aggregate"):
                with db.transaction():
                    self.assertTrue(
                        sets.settle(db, self.store, character, completed=[first[-1]])
                    )
                    raise RuntimeError("rollback aggregate")
            self.assertNotIn(
                1707, storage.load_locked(db, character["id"])["completed"]
            )
            packets = sets.recover(db, self.store, character)
            self.assertTrue(packets)
            state = storage.load_locked(db, character["id"])
            self.assertIn(1707, state["completed"])
            self.assertNotIn(2873, state["completed"])
            self.assertNotIn(2192, state["completed"])
            self.assertNotIn(str(first[-1]), state["completion_dates"])
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE character_id=%s AND reference=29725",
                    (character["id"],),
                ).fetchone()["quantity"],
                1,
            )
            self.assertEqual(sets.recover(db, self.store, character), [])
            row = dict(actor_id=-100001)
            publication = (
                dict(
                    placements=[
                        dict(row=row, quest_id=1695, running_roots={"2869": 2429})
                    ],
                    activation_links=[dict(after_quest=1719, start_quest=2869)],
                ),
                {2869: sixth},
                {},
            )
            self.assertTrue(
                quest_npc._followups(db, self.store, character, row, publication)
            )
            self.assertIn(2869, storage.load_locked(db, character["id"])["running"])
            # Finish the remaining source quests as an explicit isolated
            # database fixture; the aggregate still uses the real native plan.
            state = storage.load_locked(db, character["id"])
            state["running"] = []
            state["tracking"] = []
            state["completed"] = sorted(set(state["completed"]) | set(all_hunts))
            state["completion_dates"].update(
                {str(identity): 2000 for identity in all_hunts}
            )
            storage.store(db, character["id"], state)
            unknown = deepcopy(definitions[2873])
            unknown["cjI"] = "UnknownNativeAggregateCriterion()"
            db.execute(
                "UPDATE native_quest_metadata_definitions SET data=%s WHERE revision=%s AND definition_id=2873",
                (Jsonb({"native": unknown}), document["native_revision"]),
            )
            self.assertEqual(
                sets.settle(db, self.store, character, completed=[4733]), []
            )
            self.assertIn(4733, storage.load_locked(db, character["id"])["completed"])
            self.assertNotIn(
                2873, storage.load_locked(db, character["id"])["completed"]
            )
            db.execute(
                "UPDATE native_quest_metadata_definitions SET data=%s WHERE revision=%s AND definition_id=2873",
                (Jsonb({"native": definitions[2873]}), document["native_revision"]),
            )
            self.assertTrue(sets.settle(db, self.store, character, completed=[4733]))
            state = storage.load_locked(db, character["id"])
            self.assertIn(2873, state["completed"])
            self.assertTrue({3226, 5841} <= set(state["objectives"]))
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE character_id=%s AND reference=29759",
                    (character["id"],),
                ).fetchone()["quantity"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=ANY(%s) AND delivered_at IS NOT NULL",
                    (character["id"], [1707, 2873]),
                ).fetchone()["n"],
                4,
            )
            self.assertEqual(sets.recover(db, self.store, character), [])
        with self.store.connection() as db:
            self.assertEqual(sets.recover(db, self.store, character), [])
            self.assertEqual(
                len(
                    self.store.character(account, character["id"], db)[
                        "inventory_items"
                    ]
                ),
                2,
            )
