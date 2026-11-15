"""Real transactions cover profile activation, counters, rewards and conversion."""

from copy import deepcopy
import struct
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase

from wakfu_server.achievements import mission_toolkit as toolkit, storage


def objective(identity, variable=None, threshold=3):
    row = dict(d=identity, ckc="", cke="", ckf=[])
    if variable is not None:
        row["ckf"] = [
            dict(
                ckm=f'GetAchievementVariable("fixture-{variable}") >= {threshold}',
                ckn=[variable],
            )
        ]
    return row


def quest(identity, objectives, rewards=()):
    return dict(
        d=identity,
        native_class="aJM",
        aqb=False,
        cjI="",
        cjJ=objectives,
        cjK=list(rewards),
        cjU=0,
        getDuration=0,
    )


class MissionToolkitSettlementPostgresTests(PostgresCase):
    def test_non_rii_transaction_reward_replay_rollback_followup_and_old_mixed_breeds(
        self,
    ):
        account = self.store.register("toolkit-sql", "isolated-test-password")["id"]
        character = self.store.create_character(account, "Toolkit Sql")
        character.update(map_id=777, instance_id=0)
        first, parent, follow = 910001, 910002, 910003
        variable, follow_variable = 910071, 910073
        reward = dict(d=910021, aeV=3, ckl=[20008])
        native = {
            first: quest(first, [objective(910011, variable)], [reward]),
            parent: quest(parent, [objective(910012)]),
            follow: quest(follow, [objective(910013, follow_variable)]),
            5143: quest(
                5143,
                [
                    objective(i)
                    for i in (10574, 10575, 10576, 10608, 10609, 10610, 10611)
                ],
            ),
            5145: quest(
                5145,
                [
                    objective(10597, 756),
                    objective(10578, 757, 2),
                    objective(10579, 755),
                    objective(10620),
                ],
            ),
            5146: quest(5146, [objective(i) for i in (10582, 10583, 10584)]),
            5155: quest(
                5155,
                [
                    objective(10598, 759),
                    objective(10599, 758),
                    objective(10600, 760),
                    objective(10621),
                ],
            ),
            5156: quest(5156, [objective(10602)]),
            5160: quest(
                5160, [objective(i) for i in (10616, 10617, 10618, 10619, 10622)]
            ),
        }
        native[first]["cjI"] = "GetRealLevel() >= 7"

        def binding(
            label,
            kind,
            reference,
            quantity=False,
            quest_id=first,
            obj=910011,
            var=variable,
            maps=(777,),
        ):
            return dict(
                id=label,
                quest_id=quest_id,
                objective_id=obj,
                variable_id=var,
                event=dict(kind=kind, reference=reference),
                maps=list(maps),
                count="quantity" if quantity else "operation",
            )

        profile = dict(
            version=1,
            id="non-rii-sql-reviewed",
            evidence=[
                "Isolated synthetic native publication; actual SQL settlement and reward delivery."
            ],
            bindings=[
                binding("plant", "planting", 41001),
                binding("seed", "resource_harvest", 41002, True),
                binding(
                    "breed-one",
                    "monster_defeat",
                    5455,
                    True,
                    follow,
                    910013,
                    follow_variable,
                    (1385,),
                ),
                binding(
                    "breed-two",
                    "monster_defeat",
                    5456,
                    True,
                    follow,
                    910013,
                    follow_variable,
                    (1385,),
                ),
            ],
            links=[
                dict(parent_quest_id=parent, objective_id=910012, child_quest_id=first)
            ],
            activations=[
                dict(
                    id="arrive-first",
                    quest_id=first,
                    event=dict(kind="map_enter", reference=777),
                    maps=[777],
                ),
                dict(
                    id="arrive-parent",
                    quest_id=parent,
                    event=dict(kind="map_enter", reference=777),
                    maps=[777],
                ),
                dict(
                    id="follow-parent",
                    quest_id=follow,
                    event=dict(kind="quest_completed", reference=parent),
                    requires_completed=[first],
                ),
            ],
        )
        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            db.execute("UPDATE characters SET level=7 WHERE id=%s", (character["id"],))
            self.assertNotEqual(
                self.store.character(account, character["id"], db)["map_id"],
                character["map_id"],
            )
            db.execute(
                "INSERT INTO native_emote_definitions(emote_id) VALUES(20008) ON CONFLICT DO NOTHING"
            )
            revision = "a" * 64
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    revision,
                    Jsonb({"fixture": "isolated toolkit SQL"}),
                    b"isolated native fixtures",
                    len(native),
                ),
            )
            for identity, row in native.items():
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                    (revision, identity, Jsonb({"native": row})),
                )
            toolkit.install(db, profile, activate=True)
            toolkit.install_rii(db, activate=True)
            initial = toolkit.settle(
                db, self.store, character, "arrival-1", "map_enter", 777
            )
            self.assertTrue(any(op == 13312 for op, _ in initial))
            toolkit.settle(db, self.store, character, "plant-1", "planting", 41001, 17)
            self.assertEqual(
                storage.load_locked(db, character["id"])["variables"][str(variable)], 1
            )
            try:
                with db.transaction():
                    packets = toolkit.settle(
                        db,
                        self.store,
                        character,
                        "harvest-1",
                        "resource_harvest",
                        41002,
                        9,
                    )
                    self.assertTrue(any(op == 12266 for op, _ in packets))
                    self.assertIn(
                        follow, storage.load_locked(db, character["id"])["running"]
                    )
                    raise RuntimeError("abort committed producer operation")
            except RuntimeError as error:
                self.assertEqual(str(error), "abort committed producer operation")
            self.assertEqual(
                storage.load_locked(db, character["id"])["variables"][str(variable)], 1
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM account_emote_knowledge WHERE account_id=%s AND emote_id=20008",
                    (account,),
                ).fetchone()["n"],
                0,
            )
            packets = toolkit.settle(
                db, self.store, character, "harvest-1", "resource_harvest", 41002, 9
            )
            progressed = storage.load_locked(db, character["id"])
            self.assertEqual(progressed["variables"][str(variable)], 3)
            self.assertTrue({first, parent} <= set(progressed["completed"]))
            self.assertIn(follow, progressed["running"])
            facts = [
                (op, struct.unpack_from(">i", body, 8)[0])
                for op, body in packets
                if op in (13832, 13422)
            ]
            self.assertLess(facts.index((13422, first)), facts.index((13832, 910012)))
            self.assertEqual(
                toolkit.settle(
                    db, self.store, character, "harvest-1", "resource_harvest", 41002, 9
                ),
                [],
            )
        # Reopen the actual transaction to prove persisted state and delivery.
        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            self.assertEqual(
                toolkit.settle(
                    db, self.store, character, "harvest-1", "resource_harvest", 41002, 9
                ),
                [],
            )
            delivered = db.execute(
                "SELECT delivered_at FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=%s",
                (character["id"], first),
            ).fetchall()
            self.assertEqual(len(delivered), 1)
            self.assertIsNotNone(delivered[0]["delivered_at"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM account_emote_knowledge WHERE account_id=%s AND emote_id=20008",
                    (account,),
                ).fetchone()["n"],
                1,
            )
            current = storage.load_locked(db, character["id"])
            current["running"].append(5145)
            current["variables"]["755"] = 1
            storage.store(db, character["id"], current)
            character.update(map_id=1385)
            db.execute(
                "UPDATE characters SET map_id=1385 WHERE id=%s", (character["id"],)
            )
            storage.record_event(
                db,
                character["id"],
                "rii-wodent-victory:99",
                dict(kind="rii_wodent_victory", fight_id=99, count=3),
            )
            toolkit.settle_combat(
                db, self.store, character, fight_id=99, breeds=[5455, 5456, 5456]
            )
            current = storage.load_locked(db, character["id"])
            self.assertEqual(current["variables"]["755"], 1)
            self.assertEqual(current["variables"][str(follow_variable)], 3)
            self.assertIn(follow, current["completed"])
            self.assertEqual(
                toolkit.settle_combat(
                    db, self.store, character, fight_id=99, breeds=[5455, 5456, 5456]
                ),
                [],
            )
        toolkit._CACHE.clear()
