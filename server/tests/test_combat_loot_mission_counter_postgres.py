"""Count only durable native delivery receipts for loot objectives."""

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase

from wakfu_server.achievements import mission_toolkit as toolkit, storage
from wakfu_server.achievements.combat_loot_events import settle_received


class CombatLootMissionCounterPostgresTests(PostgresCase):
    def test_delivered_receipts_increment_once_and_complete_at_threshold(self):
        account = self.store.register("combat-loot-counter", "isolated-loot-password")[
            "id"
        ]
        character = self.store.create_character(account, "Loot Counter")
        quest_id, objective_id, item_reference = 940001, 940011, 17851
        character.update(map_id=528, instance_id=0)
        definition = {
            "d": quest_id,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjJ": [{"d": objective_id, "ckc": "", "cke": "", "ckf": []}],
            "cjK": [],
            "cjU": 0,
            "cjL": 0,
            "getDuration": 0,
        }
        profile = {
            "version": 1,
            "id": "frigost-delivered-loot-counter-test",
            "evidence": [
                "A delivered drop receipt is the only accepted producer evidence."
            ],
            "bindings": [
                {
                    "id": "delivered-item-17851",
                    "quest_id": quest_id,
                    "objective_id": objective_id,
                    "event": {"kind": "combat_loot", "reference": item_reference},
                    "count": "quantity",
                    "count_threshold": 2,
                    "maps": [528],
                }
            ],
            "links": [],
            "activations": [
                {
                    "id": "accept-loot-counter-test",
                    "quest_id": quest_id,
                    "event": {"kind": "map_enter", "reference": 528},
                    "maps": [528],
                }
            ],
        }

        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            revision = "d" * 64
            db.execute(
                "INSERT INTO native_quest_metadata_releases"
                "(revision,source_sha256,source_export,definition_count)"
                "VALUES(%s,%s,%s,%s)",
                (
                    revision,
                    Jsonb({"fixture": "combat loot counter"}),
                    b"loot-counter",
                    1,
                ),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data)"
                "VALUES(%s,%s,%s)",
                (revision, quest_id, Jsonb({"native": definition})),
            )
            toolkit.install(db, profile, activate=True)
            toolkit.settle(db, self.store, character, "enter-528", "map_enter", 528)
            self.assertIn(quest_id, storage.load_locked(db, character["id"])["running"])

            def record_delivery():
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team)"
                    "VALUES(%s,%s,%s,0)",
                    (fight_id, character["id"], account),
                )
                db.execute(
                    "INSERT INTO fight_drop_awards(fight_id,character_id,account_id,generation,"
                    "policy_version,snapshot,snapshot_sha256) VALUES(%s,%s,%s,'loot-test',1,'{}',%s)",
                    (fight_id, character["id"], account, "0" * 64),
                )
                db.execute(
                    "INSERT INTO fight_drop_attempt_receipts(fight_id,character_id,"
                    "defeated_actor_id,monster_reference,drop_row_index,attempt_index,item_reference,"
                    "success,quantity,quantity_min,quantity_max,base_probability,raw_probability,"
                    "effective_probability,draw_numerator,quantity_draw_numerator,roll_count,"
                    "native_roll_max,native_min_prospection) "
                    "VALUES(%s,%s,-94001,2402,0,0,%s,true,1,1,1,1,1,1,0,0,1,100,0)",
                    (fight_id, character["id"], item_reference),
                )
                db.execute(
                    "INSERT INTO fight_drop_delivery_receipts(fight_id,character_id,"
                    "defeated_actor_id,drop_row_index,attempt_index,item_reference,awarded_quantity,"
                    "inventory_quantity,temporary_quantity) VALUES(%s,%s,-94001,0,0,%s,1,1,0)",
                    (fight_id, character["id"], item_reference),
                )
                return fight_id

            first_fight = record_delivery()
            self.assertEqual(
                settle_received(db, self.store, character, fight_id=first_fight), []
            )
            self.assertEqual(
                settle_received(db, self.store, character, fight_id=first_fight), []
            )
            self.assertEqual(
                db.execute(
                    "SELECT count FROM character_mission_objective_counts "
                    "WHERE character_id=%s AND objective_id=%s",
                    (character["id"], objective_id),
                ).fetchone()["count"],
                1,
            )
            self.assertNotIn(
                objective_id, storage.load_locked(db, character["id"])["objectives"]
            )

            second_fight = record_delivery()
            packets = settle_received(db, self.store, character, fight_id=second_fight)
            self.assertIn(13832, [opcode for opcode, _body in packets])
            state = storage.load_locked(db, character["id"])
            self.assertIn(objective_id, state["objectives"])
            self.assertIn(quest_id, state["completed"])
            self.assertEqual(
                db.execute(
                    "SELECT count FROM character_mission_objective_counts "
                    "WHERE character_id=%s AND objective_id=%s",
                    (character["id"], objective_id),
                ).fetchone()["count"],
                2,
            )
            completed_before_replay = storage.load_locked(db, character["id"])[
                "completed"
            ]
            self.assertEqual(
                settle_received(db, self.store, character, fight_id=second_fight), []
            )
            self.assertEqual(
                storage.load_locked(db, character["id"])["completed"],
                completed_before_replay,
            )
