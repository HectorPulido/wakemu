"""Incarnam tutorial producers, owned fights and Rii exit on isolated Postgres."""
import struct
from types import SimpleNamespace
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server import intro_cinematic, mission_transport, rii_scenario
from wakfu_server.achievements import (
    incarnam_encounters,
    incarnam_resources,
    incarnam_tutorial,
    storage,
)
from wakfu_server.combat_group_store import PersistentGroups


class IncarnamRiiFlowPostgresTests(PostgresCase):
    def test_new_character_tutorial_producers_owned_fights_and_rii_intro(self):
        account = self.store.register("incarnam-rii-flow", "test-password")["id"]
        created = self.store.create_character(
            account, "Incarnam Rii Flow", tutorial=True
        )
        generation = self.store.begin_session(account)
        character = self.store.select_character(account, generation, created["id"])

        definitions = {}
        for identity, objective, _event in incarnam_tutorial.STAGES:
            definitions[identity] = {
                "d": identity,
                "native_class": "aJM",
                "aqb": False,
                "cjI": "",
                "cjU": 0,
                "getDuration": 0,
                "cjK": [],
                "cjJ": [{"d": objective, "ckc": "", "cke": "", "ckf": []}],
            }
        definitions[5160] = {
            "d": 5160,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjU": 0,
            "getDuration": 0,
            "cjK": [],
            "cjJ": [
                {"d": objective, "ckc": "", "cke": "", "ckf": []}
                for objective in (
                    10612,
                    10613,
                    10614,
                    10615,
                    10616,
                    10617,
                    10618,
                    10619,
                    10622,
                )
            ],
        }
        definitions[5146] = {
            "d": 5146,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjU": 0,
            "getDuration": 0,
            "cjK": [],
            "cjJ": [
                {"d": objective, "ckc": "", "cke": "", "ckf": []}
                for objective in (10582, 10583, 10584)
            ],
        }
        definitions[5144] = {
            "d": 5144,
            "native_class": "aJM",
            "aqb": True,
            "isVisible": True,
            "aHe": "GetRealLevel() < 30",
            "bwX": 5160,
            "cjI": "",
            "cjU": 0,
            "getDuration": 0,
            "cjK": [],
            "cjJ": [{"d": 10577, "ckc": "", "cke": "", "ckf": []}],
        }
        revision = "d" * 64
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases"
                "(revision,source_sha256,source_export,definition_count) VALUES (%s,%s,%s,%s)",
                (revision, Jsonb({}), b"incarnam-rii-flow", len(definitions)),
            )
            for identity, native in definitions.items():
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) "
                    "VALUES (%s,%s,%s)",
                    (revision, identity, Jsonb({"native": native})),
                )

        # The native intro callbacks authorize the normal private travel route.
        cinematic = intro_cinematic.IntroCinematic(
            intro_cinematic.ogrest_actor(created["id"])[0]
        )
        callback = lambda value: struct.pack(">i", value)
        cinematic.start()
        for event in (23908, 23909, 23910):
            cinematic.receive(callback(event), map_id=character["map_id"])
        self.assertEqual(
            cinematic.receive(callback(23912), map_id=character["map_id"]),
            ("enter_incarnam", 1361),
        )
        destination = {
            "map_id": 1361,
            "instance_id": intro_cinematic.private_instance_id(character["id"]),
            "x": 0,
            "y": 0,
            "z": 0,
        }
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            character, packets = mission_transport.transition(
                self.store,
                account,
                generation,
                character,
                {"direction": 0, "destination": destination},
                native_zaap=False,
            )
        self.assertEqual(
            (character["map_id"], character["instance_id"]),
            (1361, destination["instance_id"]),
        )
        with self.store.connection() as db:
            self.assertIn(5135, storage.load_locked(db, character["id"])["running"])

        groups = PersistentGroups(self.store)

        def finish_owned_wodent(stage):
            nonlocal character
            spawned = incarnam_encounters.ensure_spawn(self.store, groups, character)
            self.assertIsNotNone(spawned)
            available = groups.available(1361, character["instance_id"])
            group = next(
                group
                for group in available
                if any(
                    member["ref"] == incarnam_encounters.BREED
                    for member in group["members"]
                )
            )
            monster = next(
                member
                for member in group["members"]
                if member["ref"] == incarnam_encounters.BREED
            )
            action = struct.pack(">qq", monster["id"], incarnam_encounters.ACTION)
            with self.store.connection() as db:
                self.assertEqual(
                    incarnam_encounters.prepare(db, character, action, group)[
                        "target_id"
                    ],
                    monster["id"],
                )
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status,fight_kind) VALUES('finished','pve') RETURNING id"
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                    "VALUES (%s,%s,%s,0)",
                    (fight_id, character["id"], account),
                )
                fight = SimpleNamespace(
                    id=fight_id,
                    phase="finished",
                    winner=0,
                    actors={
                        character["id"]: SimpleNamespace(team=0),
                        monster["id"]: SimpleNamespace(team=1),
                    },
                )
                participants = [
                    {
                        "character_id": character["id"],
                        "account_id": account,
                        "session_generation": generation,
                        "withdrawn": False,
                    }
                ]
                result = incarnam_encounters.settle(
                    db,
                    self.store,
                    fight,
                    participants,
                    [monster],
                )
                if stage == 1:
                    self.assertTrue(result[character["id"]])
                else:
                    self.assertIn(
                        "incarnam-final-fight:won",
                        {
                            row["event_key"]
                            for row in db.execute(
                                "SELECT event_key FROM character_achievement_events WHERE character_id=%s",
                                (character["id"],),
                            ).fetchall()
                        },
                    )

        finish_owned_wodent(1)
        resource = {
            "resource_reference": 824,
            "map_id": 1361,
            "instance_id": character["instance_id"],
        }
        with self.store.connection() as db:
            self.assertTrue(
                incarnam_resources.harvested(
                    db,
                    self.store,
                    character,
                    resource,
                    {"action_id": 2266},
                    token="flow-wood",
                    product_reference=30939,
                )
            )
        with self.store.connection() as db:
            self.assertTrue(
                incarnam_resources.crafted(
                    db,
                    self.store,
                    character,
                    {
                        "table_uid": 34582,
                        "recipe_id": 9323,
                        "map_id": 1361,
                        "instance_id": character["instance_id"],
                    },
                    [{"reference": 30940}],
                    token="flow-key",
                )
            )
        # This represents the authenticated output of the real key recipe.
        # The gate then consumes that owned inventory unit through its normal payment path.
        from wakfu_server.achievements import rewards

        with self.store.connection() as db:
            rewards._item(db, self.store, character, 30940, 1)
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            character = self.store.transition_map(
                account,
                generation,
                character["id"],
                character,
                {
                    "map_id": 1361,
                    "instance_id": character["instance_id"],
                    "x": 12,
                    "y": -35,
                    "z": -13,
                },
            )
        gate = incarnam_resources.interact_gate(
            self.store,
            account,
            generation,
            character,
            struct.pack(">qHH", incarnam_resources.GATE, 0, 0),
            loaded=True,
            blocked=False,
        )
        character = gate["character"]
        self.assertTrue(gate["packets"])
        with self.store.connection() as db:
            self.assertIn(5139, storage.load_locked(db, character["id"])["running"])
        finish_owned_wodent(2)
        with self.store.connection() as db:
            self.assertTrue(incarnam_encounters.pending_final(db, character))

        route = {
            "direction": 0,
            "destination": {
                "map_id": 1385,
                "instance_id": 0,
                "x": 0,
                "y": 0,
                "z": 0,
            },
        }
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            character, packets = mission_transport.transition(
                self.store,
                account,
                generation,
                character,
                route,
                native_zaap=False,
                incarnam_exit=True,
            )
        self.assertEqual((character["map_id"], character["instance_id"]), (1385, 0))
        self.assertTrue(
            any(packet == rii_scenario.packet(rii_scenario.INTRO) for packet in packets)
        )
        with self.store.connection() as db:
            state = storage.load_locked(db, character["id"])
        self.assertIn(5160, state["running"])
        connection = SimpleNamespace(pending_rii_intro=character["id"])
        self.assertTrue(
            rii_scenario.finish_intro(
                connection,
                self.store,
                account,
                generation,
                character,
                in_combat=False,
            )
        )
        self.assertIsNone(connection.pending_rii_intro)
        with self.reopen().connection() as db:
            final = storage.load_locked(db, character["id"])
        self.assertIn(5139, final["completed"])
        self.assertIn(10568, final["objectives"])


if __name__ == "__main__":
    import unittest

    unittest.main()
