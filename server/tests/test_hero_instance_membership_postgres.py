"""Live company changes preserve instance progress and frozen reward receipts."""
import struct
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.characters import heroes


class HeroInstanceMembershipTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("instance-heroes", "test-password")["id"]
        self.main = self.store.create_character(self.account, "Instance Main")
        self.hero = self.store.create_character(self.account, "Instance Hero")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])

    def _add(self):
        return heroes.add(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )

    def _remove(self):
        return heroes.remove(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )

    def test_dungeon_add_remove_rejoin_preserves_progress_and_next_fight_guard(self):
        from wakfu_server import dungeon_runtime

        self._add()
        self._remove()
        foreign_account = self.store.register("instance-foreign", "test-password")["id"]
        foreign = self.store.create_character(foreign_account, "Instance Foreign")
        with self.store.connection() as db:
            party = db.execute(
                "SELECT p.* FROM player_parties p JOIN player_party_members m ON m.party_id=p.id WHERE m.character_id=%s",
                (self.main["id"],),
            ).fetchone()
            run = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,"
                "entry_map_id,entry_object_id,entry_destination_id,start_map_id) VALUES(%s,%s,%s,1,1,527,1,1,312) RETURNING *",
                (party["id"], party["revision"], self.main["id"]),
            ).fetchone()
            db.execute(
                "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) VALUES(%s,%s,%s,%s,%s,'leader')",
                (
                    run["instance_id"],
                    party["id"],
                    self.main["id"],
                    self.generation,
                    party["revision"],
                ),
            )
            progress = db.execute(
                "INSERT INTO dungeon_room_runs(instance_id,party_id,catalog_hash,rooms,current_room) VALUES(%s,%s,%s,%s,2) RETURNING *",
                (
                    run["instance_id"],
                    party["id"],
                    "a" * 64,
                    Jsonb([{"order": 1}, {"order": 2}]),
                ),
            ).fetchone()
            db.execute(
                "UPDATE characters SET map_id=312,instance_id=%s,x=4,y=2,z=0 WHERE id=%s",
                (run["instance_id"], self.main["id"]),
            )
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (foreign["id"], party["id"]),
            )
            db.execute(
                "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) VALUES(%s,%s,%s,'foreign-lease',%s,'member')",
                (run["instance_id"], party["id"], foreign["id"], party["revision"]),
            )
            unrelated = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (unrelated, foreign["id"], foreign_account),
            )
        self._add()
        joined = self.store.character(self.account, self.hero["id"])
        self.assertEqual(
            (joined["map_id"], joined["instance_id"], joined["x"], joined["y"]),
            (312, run["instance_id"], 4, 2),
        )
        config = {
            "topology": {
                "policy": "local_accessible_anchor_policy",
                "asset_map_id": 312,
                "completion_destination": {
                    "map_id": 527,
                    "x": 1,
                    "y": 2,
                    "z": 0,
                    "provenance": {"policy": "native_entry_approved_walkable_approach"},
                },
            }
        }
        with patch.object(
            dungeon_runtime, "configuration_for_instance", return_value=(None, config)
        ):
            self._remove()
        self.assertEqual(
            self.store.character(self.account, self.hero["id"])["instance_id"], 0
        )
        self._add()
        with self.store.connection() as db:
            self.assertEqual(
                progress,
                db.execute(
                    "SELECT * FROM dungeon_room_runs WHERE instance_id=%s",
                    (run["instance_id"],),
                ).fetchone(),
            )
            self.assertEqual(
                3,
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_instance_members WHERE instance_id=%s AND status='active'",
                    (run["instance_id"],),
                ).fetchone()["n"],
            )
            self.assertEqual(
                [foreign["id"]],
                [
                    row["character_id"]
                    for row in db.execute(
                        "SELECT character_id FROM combat_fight_participants WHERE fight_id=%s",
                        (unrelated,),
                    ).fetchall()
                ],
            )
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight, self.hero["id"], self.account),
            )
        with self.assertRaisesRegex(ValueError, "during combat"):
            self._remove()

    def test_rift_terminal_new_hero_can_exit_without_entering_reward_roster(self):
        from wakfu_server import generic_transports, rift_exit, rift_runtime

        catalog = {
            "map_id": 312,
            "level": 1,
            "objects": [{"id": 10, "map_id": 312, "type": "Teleporter"}],
        }
        foreign_account = self.store.register("rift-former", "test-password")["id"]
        foreign = self.store.create_character(foreign_account, "Former Fighter")
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            run = db.execute(
                "INSERT INTO rift_instances(wave_definition_id,owner_character_id,members,catalog,policy,seed,status,fight_id,ended_at) VALUES(1,%s,%s,%s,%s,'hero-terminal','won',%s,CURRENT_TIMESTAMP) RETURNING *",
                (
                    self.main["id"],
                    Jsonb([self.main["id"], foreign["id"]]),
                    Jsonb(catalog),
                    Jsonb({"max_members": 6}),
                    fight,
                ),
            ).fetchone()
            receipt = db.execute(
                "INSERT INTO rift_settlement_receipts(instance_id,fight_id,outcome,result) VALUES(%s,%s,'won',%s) RETURNING *",
                (run["instance_id"], fight, Jsonb({"completed_waves": 3})),
            ).fetchone()
            db.execute(
                "UPDATE characters SET map_id=312,instance_id=%s WHERE id=%s",
                (run["instance_id"], self.main["id"]),
            )
            unrelated = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (unrelated, foreign["id"], foreign_account),
            )
        self._add()
        heroes.switch_main(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )
        with self.store.connection() as db:
            replay = rift_runtime.settle(
                db,
                run["instance_id"],
                fight,
                outcome="won",
                turn=40,
                apply_rewards=lambda *args: self.fail("Reward replay must not run"),
            )
            self.assertEqual(receipt, replay)
            self.assertEqual(
                run["members"],
                db.execute(
                    "SELECT members FROM rift_instances WHERE instance_id=%s",
                    (run["instance_id"],),
                ).fetchone()["members"],
            )
        with patch.object(
            generic_transports,
            "resolve",
            return_value={
                "destination": {
                    "map_id": 527,
                    "instance_id": 0,
                    "x": 1,
                    "y": 2,
                    "z": 0,
                },
                "direction": 0,
            },
        ):
            result = rift_exit._exit(
                self.store,
                self.account,
                self.generation,
                self.hero["id"],
                struct.pack(">qiBi", 10, 20, 0, 2),
                allowed_accounts={self.account},
                source_allowed=lambda *args: True,
                fighting=lambda identity: False,
            )
        self.assertEqual(
            {self.main["id"], self.hero["id"]},
            {row["id"] for row in result["moved_members"]},
        )

    def test_rift_entered_updates_future_participants_and_uses_policy_cap(self):
        with self.store.connection() as db:
            run = db.execute(
                "INSERT INTO rift_instances(wave_definition_id,owner_character_id,members,catalog,policy,seed,status) VALUES(1,%s,%s,%s,%s,'hero-entered','entered') RETURNING *",
                (
                    self.main["id"],
                    Jsonb([self.main["id"]]),
                    Jsonb({"level": 1}),
                    Jsonb({"max_members": 2}),
                ),
            ).fetchone()
            db.execute(
                "UPDATE characters SET instance_id=%s WHERE id=%s",
                (run["instance_id"], self.main["id"]),
            )
        self._add()
        with self.store.connection() as db:
            current = db.execute(
                "SELECT * FROM rift_instances WHERE instance_id=%s",
                (run["instance_id"],),
            ).fetchone()
            self.assertEqual(
                set(current["members"]), {self.main["id"], self.hero["id"]}
            )
            self.assertEqual(current["wave"], run["wave"])
            self.assertEqual(current["completed_waves"], run["completed_waves"])
