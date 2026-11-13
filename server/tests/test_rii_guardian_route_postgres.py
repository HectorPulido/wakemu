"""Persist a guardian defeat and the native return/Zaap journey in isolation."""
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import mission_transport, native_transports, transports
from wakfu_server.achievements import rii_guardian_battle, storage


def objective(identity, prerequisite=""):
    return {"d": identity, "ckc": prerequisite, "cke": "", "ckf": []}


class RiiGuardianRoutePostgresTests(PostgresCase):
    def test_defeat_persists_and_native_portal_and_zaap_finish_departure(self):
        account = self.store.register("rii-guardian-route", "test-password")["id"]
        character = self.store.create_character(account, "Rii Return")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        guardian = {
            "d": 5146,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjJ": [
                objective(10582),
                objective(10583, "IsAchievementObjectiveComplete(10582)"),
                objective(10584, "IsAchievementObjectiveComplete(10583)"),
            ],
            "cjK": [],
        }
        parent = {
            "d": 5160,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjU": 0,
            "getDuration": 0,
            "cjJ": [objective(10622), objective(10612)],
            "cjK": [],
        }
        departure = {
            "d": 5161,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "aHe": "IsAchievementActive(5146)",
            "cjJ": [objective(10624)],
            "cjK": [],
        }
        back = next(
            r
            for r in transports.CATALOG["routes"]
            if (r["interactive_element_id"], r["destination_id"]) == (34618, 4563)
        )
        actor_id = -998811
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES (%s,%s,%s,3)",
                ("f" * 64, Jsonb({}), b"fixture"),
            )
            for definition in (guardian, parent, departure):
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,%s,%s)",
                    ("f" * 64, definition["d"], Jsonb({"native": definition})),
                )
            origin = back["source_position"]
            db.execute(
                "UPDATE characters SET map_id=1387,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (origin["x"], origin["y"], origin["z"], character["id"]),
            )
            state = storage.load_locked(db, character["id"])
            state["running"] = [5146, 5160]
            state["tracking"] = [5146, 5160]
            state["objectives"] = [10582, 10583]
            storage.store(db, character["id"], state)
            storage.record_event(
                db,
                character["id"],
                f"rii-guardian-actor:{-actor_id}",
                {
                    "kind": "reconstructed_rii_guardian_actor",
                    "owner": character["id"],
                    "actor_id": actor_id,
                    "ref": 5458,
                },
            )
            for group_id, monster_id, reference in (
                (41, actor_id, 5458),
                (42, -998812, 5455),
            ):
                db.execute(
                    "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) "
                    "VALUES (1387,0,%s,%s,'available')",
                    (group_id, Jsonb([{"id": monster_id, "ref": reference}])),
                )
                db.execute(
                    "INSERT INTO combat_group_members(map_id,instance_id,group_id,monster_id) "
                    "VALUES (1387,0,%s,%s)",
                    (group_id, monster_id),
                )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status,fight_kind) VALUES ('finished','pve') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES (%s,%s,%s,0,%s)",
                (fight_id, character["id"], account, generation),
            )
            fight = SimpleNamespace(
                id=fight_id,
                phase="finished",
                winner=1,
                actors={
                    character["id"]: SimpleNamespace(team=0),
                    actor_id: SimpleNamespace(team=1),
                },
            )
            members = [
                {
                    "character_id": character["id"],
                    "account_id": account,
                    "session_generation": generation,
                }
            ]
        # A failure after the exact group's deletion must roll back quest,
        # reward and group changes together, so a later retry can succeed.
        original_retire = rii_guardian_battle._retire_lost_encounter

        def fail_after_retire(db, target):
            original_retire(db, target)
            raise ValueError("injected post-retirement failure")

        with patch.object(
            rii_guardian_battle, "_retire_lost_encounter", side_effect=fail_after_retire
        ):
            with self.assertRaisesRegex(ValueError, "injected post-retirement"):
                with self.store.connection() as db:
                    rii_guardian_battle.settle(
                        db, self.store, fight, members, [{"id": actor_id, "ref": 5458}]
                    )
        with self.store.connection() as db:
            self.assertIn(5146, storage.load_locked(db, character["id"])["running"])
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM combat_groups WHERE map_id=1387 AND instance_id=0 AND group_id=41"
                ).fetchone()
            )
            packets = rii_guardian_battle.settle(
                db, self.store, fight, members, [{"id": actor_id, "ref": 5458}]
            )
            self.assertEqual(packets, {})
            self.assertTrue(
                rii_guardian_battle.pending_cinematic(
                    db, self.store.character(account, character["id"], db)
                )
            )

        with self.reopen().connection() as db:
            progress = storage.load_locked(db, character["id"])
            self.assertIn(5146, progress["running"])
            source = self.store.character(account, character["id"], db)
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            returned, packets = rii_guardian_battle.finish_cinematic(
                self.store, account, generation, source
            )
        self.assertTrue(packets)
        with self.assertRaisesRegex(ValueError, "pending"):
            rii_guardian_battle.finish_cinematic(
                self.store, account, generation, returned
            )
        with self.reopen().connection() as db:
            progress = storage.load_locked(db, character["id"])
            self.assertIn(5146, progress["completed"])
            self.assertIn(10622, progress["objectives"])
            self.assertIn(5161, progress["running"])
            self.assertIn(5161, progress["tracking"])
            groups = db.execute(
                "SELECT group_id FROM combat_groups WHERE map_id=1387 AND instance_id=0 ORDER BY group_id"
            ).fetchall()
            self.assertEqual([row["group_id"] for row in groups], [42])
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            # Walk to the native Zaap using the normal owned location transition.
            zaap = native_transports.OBJECTS[34644]
            zaap_location = {
                "map_id": 1385,
                "instance_id": 0,
                "x": int(zaap["x"]),
                "y": int(zaap["y"]),
                "z": int(zaap["z"]),
            }
            at_zaap = self.store.transition_map(
                account, generation, character["id"], returned, zaap_location
            )
            destination = native_transports.resolve(
                at_zaap,
                struct.pack(">qq", 34644, 19249),
                known_ids={19249},
                waive_criteria=True,
            )
            saved, packets = mission_transport.transition(
                self.store, account, generation, at_zaap, destination, native_zaap=True
            )
        self.assertEqual(saved["map_id"], 527)
        self.assertIn(13422, [packet[0] for packet in packets])
        with self.reopen().connection() as db:
            progress = storage.load_locked(db, character["id"])
            self.assertIn(5161, progress["completed"])
            self.assertIn(10624, progress["objectives"])
            self.assertEqual(
                self.store.character(account, character["id"], db)["map_id"], 527
            )
            self.assertEqual(
                rii_guardian_battle.settle(
                    db, self.store, fight, members, [{"id": actor_id, "ref": 5458}]
                ),
                {},
            )


if __name__ == "__main__":
    unittest.main()
